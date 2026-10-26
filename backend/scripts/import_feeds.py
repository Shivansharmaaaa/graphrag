"""Load real, public threat intelligence into all four stores, on top of the seed corpus.

    make import-feeds          # local databases
    make cloud-import-feeds    # hosted databases (.env.cloud)

Sources (public, no account or key needed):
  * MITRE ATT&CK Enterprise (STIX 2.1): groups, software, techniques and campaigns, the
    relationships between them, and ATT&CK's own descriptions as report text
  * abuse.ch Feodo Tracker: botnet command-and-control IPs (QakBot, Emotet, Dridex, TrickBot …)
  * Emerging Threats: compromised-host IP list

Neo4j gets the nodes and edges (ATT&CK groups and software merge onto the seed nodes of the
same name), MongoDB one report per group, per campaign and per feed, Qdrant the re-embedded
chunks of every report, and Redis the feed IPs with a TTL. Idempotent: run it again to refresh.
`make seed` wipes the stores, so run this again after it. Restart the API afterwards: the
embedder is refitted on the larger corpus.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

import httpx
from pymongo import ReplaceOne

from app import blocklist, documents, stores, vectors
from app.config import BACKEND_DIR

FEEDS = {
    "attack": "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
              "enterprise-attack/enterprise-attack.json",
    "feodo": "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
    "feodo_all": "https://feodotracker.abuse.ch/downloads/ipblocklist_aggressive.csv",
    "et": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
}
CACHE = BACKEND_DIR / "data" / "feeds"
FEODO_SINCE = "2025-01-01"   # older Feodo C2 entries stay out of the blocklist
BATCH = 2000                 # rows per Neo4j UNWIND
REDIS_OPS_PER_S = 80         # Redis Cloud's free plan allows 100 operations a second

# ATT&CK campaigns that are the seed corpus's own campaigns under another name
SEED_CAMPAIGNS = {"C0024": "solarwinds", "C0057": "3cx", "C0025": "industroyer"}

# Single-word names that are also ordinary words ("Net", "Silence", "Wiper"). The node keeps
# the name, but questions link to it only by its ATT&CK id, so "the .net domain" or
# "a wiper attack" does not pull in an unrelated group or tool.
GENERIC = set("""
armageddon axiom buckeye chimera cicada cleaver dragonfly equation inception karma leviathan
mantis mirage play rattlesnake reaper sidewinder silence snake strider swallowtail tick
agenda anchor apostle aurora avenger cannon carbon chaos crimson embargo emissary epic
explosive ferocious flame gazer havoc james kevin lucifer mango meteor milan mosquito ninja
octopus page pandora pony prestige proton reaver rover royal samurai scorpion shark solar
soldier spark trinity wiper denis medusa viper photo calendar biscuit backspace canopy
arp covenant empire expand net ping reg responder ruler sliver tor defacement
""".split())


# ------------------------------------------------------------------ download
def fetch(name: str, refresh: bool) -> bytes:
    path = CACHE / FEEDS[name].rsplit("/", 1)[1]
    if refresh or not path.exists() or time.time() - path.stat().st_mtime > 86400:
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"  downloading {FEEDS[name]}")
        r = httpx.get(FEEDS[name], timeout=300, follow_redirects=True)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path.read_bytes()


# ------------------------------------------------------------------ text helpers
_LINK = re.compile(r"\[([^\]]+)\]\(https?://[^)]*\)")
_CITATION = re.compile(r"\s*\(Citation:[^)]*\)")


def clean(text: str | None) -> str:
    text = _CITATION.sub("", _LINK.sub(r"\1", text or ""))
    return re.sub(r"\s+", " ", text.replace("<code>", "").replace("</code>", "")).strip()


def weak(form: str) -> bool:
    """A surface form too ordinary to link on: a common word, or a short lowercase utility."""
    return form.lower() in GENERIC or (form.isalpha() and form.islower() and len(form) <= 5)


def listing(names: list[str], limit: int = 40) -> str:
    names = sorted(set(names), key=str.lower)
    more = f" and {len(names) - limit} more" if len(names) > limit else ""
    return ", ".join(names[:limit]) + more


# ------------------------------------------------------------------ MITRE ATT&CK
def parse_attack(raw: bytes) -> dict:
    bundle = json.loads(raw)
    objs = {o["id"]: o for o in bundle["objects"]
            if not o.get("revoked") and not o.get("x_mitre_deprecated")}
    version = next((o.get("x_mitre_version") for o in objs.values() if o["type"] == "x-mitre-collection"), "")

    def ext(o):
        ref = next((r for r in o.get("external_references", []) if r.get("source_name") == "mitre-attack"), {})
        return ref.get("external_id"), ref.get("url")

    parent = {r["source_ref"]: r["target_ref"] for r in objs.values()
              if r["type"] == "relationship" and r["relationship_type"] == "subtechnique-of"}
    rels = [r for r in objs.values() if r["type"] == "relationship"
            and r["source_ref"] in objs and r["target_ref"] in objs]
    return {"objs": objs, "rels": rels, "parent": parent, "ext": ext, "version": version}


def existing_names() -> dict[str, dict[str, str]]:
    """label -> {lower-case name or alias: graph id}, for merging ATT&CK onto the seed graph."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    with stores.neo4j_session() as s:
        for r in s.run("""MATCH (n) WHERE n:ThreatActor OR n:Malware OR n:Campaign
                          RETURN labels(n)[0] AS label, n.id AS id, n.name AS name,
                                 coalesce(n.aliases, []) AS aliases, properties(n)["mitre_id"] AS mitre"""):
            for form in [r["name"], *r["aliases"]]:
                if form:
                    out[r["label"]].setdefault(form.lower(), r["id"])
            if r["mitre"]:
                out[r["label"]][r["mitre"].lower()] = r["id"]
    return out


def attack_graph(a: dict) -> dict:
    objs, ext = a["objs"], a["ext"]
    known = existing_names()
    ids: dict[str, str] = {}              # STIX id -> graph id
    nodes: dict[str, list[dict]] = defaultdict(list)
    seed_aliases: dict[str, list[str]] = {}
    with stores.neo4j_session() as s:
        for r in s.run("MATCH (n) WHERE n:ThreatActor OR n:Malware OR n:Campaign "
                       "RETURN n.id AS id, coalesce(n.aliases, []) AS aliases"):
            seed_aliases[r["id"]] = r["aliases"]

    claimed: set[tuple[str, str]] = set()
    kinds = {"intrusion-set": "ThreatActor", "malware": "Malware", "tool": "Malware", "campaign": "Campaign"}
    for o in objs.values():
        label = kinds.get(o["type"])
        if not label:
            continue
        xid, url = ext(o)
        forms = [o["name"], *o.get("aliases", []), *o.get("x_mitre_aliases", [])]
        gid = SEED_CAMPAIGNS.get(xid) or next((known[label][f.lower()] for f in forms
                                               if f.lower() in known[label]), None) or xid
        if (label, gid) in claimed:      # two ATT&CK objects matched one seed node: keep the first
            gid = xid
        claimed.add((label, gid))
        ids[o["id"]] = gid
        aliases = [f for f in dict.fromkeys(seed_aliases.get(gid, []) + forms[1:])
                   if f != o["name"] and not weak(f)]
        row = {"id": gid, "name": o["name"], "aliases": aliases, "mitre_id": xid, "url": url,
               "linkable": not weak(o["name"]), "modified": o.get("modified", "")[:10]}
        if label == "Malware":
            row["kind"] = o["type"]
            row["platforms"] = o.get("x_mitre_platforms", [])
        if label == "Campaign":
            row["year"] = int(o["first_seen"][:4]) if o.get("first_seen") else None
            row["summary"] = clean(o.get("description")).split(". ")[0][:300]
        nodes[label].append(row)

    for o in objs.values():
        if o["type"] == "attack-pattern" and not o.get("x_mitre_is_subtechnique"):
            xid, url = ext(o)
            ids[o["id"]] = xid
            tactics = [p["phase_name"] for p in o.get("kill_chain_phases", [])]
            nodes["Technique"].append({"id": xid, "name": o["name"], "tactic": tactics[0] if tactics else None,
                                       "tactics": tactics, "url": url, "linkable": not weak(o["name"])})
    for sub, par in a["parent"].items():
        if par in ids:
            ids[sub] = ids[par]          # sub-techniques count as their parent technique

    edges: dict[tuple, set] = defaultdict(set)
    for r in a["rels"]:
        src, dst = objs[r["source_ref"]], objs[r["target_ref"]]
        if r["source_ref"] not in ids or r["target_ref"] not in ids:
            continue
        s, d, rt = ids[r["source_ref"]], ids[r["target_ref"]], r["relationship_type"]
        st, dt = src["type"], dst["type"]
        if rt == "uses" and st == "intrusion-set" and dt in ("malware", "tool"):
            edges[("ThreatActor", "USES", "Malware")].add((s, d))
        elif rt == "uses" and st == "intrusion-set" and dt == "attack-pattern":
            edges[("ThreatActor", "EMPLOYS", "Technique")].add((s, d))
        elif rt == "uses" and st == "campaign" and dt in ("malware", "tool"):
            edges[("Campaign", "USES_MALWARE", "Malware")].add((s, d))
        elif rt == "uses" and st == "campaign" and dt == "attack-pattern":
            edges[("Campaign", "EMPLOYS", "Technique")].add((s, d))
        elif rt == "uses" and st in ("malware", "tool") and dt == "attack-pattern":
            edges[("Malware", "IMPLEMENTS", "Technique")].add((s, d))
        elif rt == "attributed-to" and st == "campaign" and dt == "intrusion-set":
            edges[("ThreatActor", "ATTRIBUTED_TO_CAMPAIGN", "Campaign")].add((d, s))
    return {"ids": ids, "nodes": nodes, "edges": edges}


def attack_reports(a: dict, g: dict) -> list[dict]:
    """One MongoDB report per group and per campaign, written from ATT&CK's own text."""
    objs, ext, ids = a["objs"], a["ext"], g["ids"]
    out_rel: dict[str, list[dict]] = defaultdict(list)
    attributed: dict[str, list[str]] = defaultdict(list)
    for r in a["rels"]:
        out_rel[r["source_ref"]].append(r)
        if r["relationship_type"] == "attributed-to":
            attributed[r["target_ref"]].append(r["source_ref"])
    source = f"MITRE ATT&CK Enterprise v{a['version']}" if a["version"] else "MITRE ATT&CK Enterprise"
    reports = []
    for o in objs.values():
        if o["type"] not in ("intrusion-set", "campaign"):
            continue
        xid, url = ext(o)
        name = o["name"]
        uses = [(r, objs[r["target_ref"]]) for r in out_rel[o["id"]] if r["relationship_type"] == "uses"]
        software = [t for _, t in uses if t["type"] in ("malware", "tool")]
        techniques = {ids[t["id"]]: objs.get(a["parent"].get(t["id"]), t)["name"]
                      for _, t in uses if t["type"] == "attack-pattern" and t["id"] in ids}
        notes = [clean(r.get("description")) for r, t in uses if t["type"] in ("malware", "tool")]
        notes = [n for n in notes if len(n) > 40][:12]
        if o["type"] == "intrusion-set":
            campaigns = [objs[c] for c in attributed[o["id"]]]
            aka = [x for x in o.get("aliases", []) if x != name]
            parts = [f"{name} ({xid}) is a threat group tracked by MITRE ATT&CK"
                     + (f", also known as {listing(aka, 12)}." if aka else "."), clean(o.get("description"))]
            if campaigns:
                parts.append(f"ATT&CK attributes these campaigns to {name}: {listing([c['name'] for c in campaigns])}.")
            actors, camp_ids = [ids[o["id"]]], [ids[c["id"]] for c in campaigns]
        else:
            groups = [objs[r["target_ref"]] for r in out_rel[o["id"]] if r["relationship_type"] == "attributed-to"]
            when = f", active from {o.get('first_seen', '')[:7]} to {o.get('last_seen', '')[:7]}" if o.get("first_seen") else ""
            parts = [f"{name} ({xid}) is a campaign tracked by MITRE ATT&CK{when}."]
            if groups:
                parts.append(f"ATT&CK attributes it to {listing([x['name'] for x in groups])}.")
            parts.append(clean(o.get("description")))
            actors, camp_ids = [ids[x["id"]] for x in groups], [ids[o["id"]]]
        if software:
            parts.append(f"Software used by {name}: {listing([t['name'] for t in software])}.")
        parts += notes
        if techniques:
            top = [f"{n} ({t})" for t, n in sorted(techniques.items())]
            parts.append(f"ATT&CK records {len(techniques)} techniques for {name}, including {listing(top, 30)}.")
        reports.append({
            "_id": f"attack-{xid}", "title": f"{name} ({xid}): MITRE ATT&CK {'group' if o['type'] == 'intrusion-set' else 'campaign'} profile",
            "source": source, "date": (o.get("modified") or o.get("created", ""))[:10], "tlp": "WHITE",
            "confidence": "high", "actors": actors, "campaigns": camp_ids,
            "malware": list(dict.fromkeys(ids[t["id"]] for t in software)), "iocs": [],
            "body": " ".join(p for p in parts if p),
            "attack": {"id": xid, "url": url, "type": o["type"]},
        })
    return reports


# ------------------------------------------------------------------ IP feeds
def parse_ip_feeds(feodo: bytes, feodo_all: bytes, et: bytes) -> list[dict]:
    """Blocklist entries with severity and TTL from each feed's own status and recency."""
    out: dict[str, dict] = {}
    for e in json.loads(feodo):        # the recommended list: servers active recently
        out[e["ip_address"]] = {
            "ip": e["ip_address"], "port": e.get("port"), "malware": e.get("malware"),
            "status": e.get("status"), "as_name": e.get("as_name"), "country": e.get("country"),
            "first_seen": (e.get("first_seen") or "")[:10], "last_online": e.get("last_online"),
            "source": "abuse.ch Feodo Tracker",
            "severity": "critical" if e.get("status") == "online" else "high",
            "ttl": 7 * 86400 if e.get("status") == "online" else 3 * 86400}
    rows = csv.reader(line for line in io.StringIO(feodo_all.decode()) if not line.startswith("#"))
    for r in rows:
        if len(r) < 6 or r[0] == "first_seen_utc" or r[1] in out or r[4] < FEODO_SINCE:
            continue
        out[r[1]] = {"ip": r[1], "port": int(r[2]) if r[2].isdigit() else None, "malware": r[5],
                     "status": r[3], "first_seen": r[0][:10], "last_online": r[4],
                     "source": "abuse.ch Feodo Tracker", "severity": "medium", "ttl": 2 * 86400}
    for line in et.decode().splitlines():
        ip = line.strip()
        if ip and not ip.startswith("#") and ip not in out:
            try:
                blocklist.normalise("ip", ip)
            except ValueError:
                continue
            out[ip] = {"ip": ip, "source": "Emerging Threats compromised hosts",
                       "severity": "medium", "ttl": 86400}
    return list(out.values())


def feed_reports(entries: list[dict], malware_ids: dict[str, str], attack: dict) -> list[dict]:
    today = date.today().isoformat()
    feodo = [e for e in entries if e["source"].startswith("abuse.ch")]
    et = [e for e in entries if e["source"].startswith("Emerging")]
    fams = Counter(e["malware"] for e in feodo)
    first_sentence = {}
    for o in attack["objs"].values():
        if o["type"] in ("malware", "tool") and o["name"] in fams:
            first_sentence[o["name"]] = clean(o.get("description")).split(". ")[0].rstrip(".") + "."
    body = [f"abuse.ch Feodo Tracker lists command-and-control servers of banking-trojan and loader "
            f"botnets. This snapshot, taken {today}, holds {len(feodo)} C2 servers last online on or after "
            f"{FEODO_SINCE}: " + ", ".join(f"{m} {n}" for m, n in fams.most_common()) + "."]
    body += [first_sentence[m] for m, _ in fams.most_common() if m in first_sentence]
    for e in sorted(feodo, key=lambda e: e.get("last_online") or "", reverse=True):
        where = ", ".join(x for x in (e.get("as_name"), e.get("country")) if x)
        body.append(f"{e['ip']}:{e.get('port')} served {e['malware']} C2{f' ({where})' if where else ''}, "
                    f"first seen {e['first_seen']}, last online {e['last_online']}, status {e['status']}.")
    reports = [{
        "_id": "feed-feodo", "title": f"abuse.ch Feodo Tracker: botnet C2 servers ({today})",
        "source": "abuse.ch Feodo Tracker", "date": today, "tlp": "WHITE", "confidence": "high",
        "actors": [], "campaigns": [], "iocs": [e["ip"] for e in feodo],
        "malware": [malware_ids[m] for m in fams if m in malware_ids],
        "body": " ".join(body), "feed": {"url": FEEDS["feodo"], "entries": len(feodo)},
    }]
    if et:
        reports.append({
            "_id": "feed-et-compromised", "title": f"Emerging Threats: compromised hosts ({today})",
            "source": "Emerging Threats (Proofpoint)", "date": today, "tlp": "WHITE", "confidence": "medium",
            "actors": [], "campaigns": [], "malware": [], "iocs": [e["ip"] for e in et],
            "body": (f"The Emerging Threats compromised-host list, fetched {today}, names {len(et)} IP addresses "
                     "of hosts seen compromised and taking part in attacks such as scanning, brute forcing "
                     "and spam. They are published to the blocklist for 24 hours and refreshed from the feed. "
                     f"Examples: {', '.join(e['ip'] for e in et[:20])}."),
            "feed": {"url": FEEDS["et"], "entries": len(et)},
        })
    return reports


# ------------------------------------------------------------------ writers
def _batches(rows: list, n: int = BATCH):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def write_graph(g: dict, entries: list[dict], reports: list[dict], malware_ids: dict[str, str]) -> dict:
    with stores.neo4j_session() as s:
        for rows in _batches(g["nodes"]["ThreatActor"]):
            s.run("""UNWIND $rows AS r MERGE (n:ThreatActor {id:r.id})
                     SET n.name = coalesce(n.name, r.name), n.aliases = r.aliases, n.mitre_id = r.mitre_id,
                         n.url = r.url, n.linkable = coalesce(n.linkable, r.linkable),
                         n.source = coalesce(n.source, 'MITRE ATT&CK')""", rows=rows).consume()
        for rows in _batches(g["nodes"]["Malware"]):
            s.run("""UNWIND $rows AS r MERGE (n:Malware {id:r.id})
                     SET n.name = coalesce(n.name, r.name), n.aliases = r.aliases, n.mitre_id = r.mitre_id,
                         n.url = r.url, n.kind = coalesce(n.kind, r.kind), n.platforms = r.platforms,
                         n.linkable = coalesce(n.linkable, r.linkable),
                         n.source = coalesce(n.source, 'MITRE ATT&CK')""", rows=rows).consume()
        for rows in _batches(g["nodes"]["Campaign"]):
            s.run("""UNWIND $rows AS r MERGE (n:Campaign {id:r.id})
                     SET n.name = coalesce(n.name, r.name), n.aliases = r.aliases, n.mitre_id = r.mitre_id,
                         n.url = r.url, n.year = coalesce(n.year, r.year), n.summary = coalesce(n.summary, r.summary),
                         n.linkable = coalesce(n.linkable, r.linkable),
                         n.source = coalesce(n.source, 'MITRE ATT&CK')""", rows=rows).consume()
        for rows in _batches(g["nodes"]["Technique"]):
            s.run("""UNWIND $rows AS r MERGE (n:Technique {id:r.id})
                     SET n.name = coalesce(n.name, r.name), n.tactic = coalesce(n.tactic, r.tactic),
                         n.tactics = r.tactics, n.url = r.url, n.linkable = coalesce(n.linkable, r.linkable)""",
                  rows=rows).consume()
        for (la, rel, lb), pairs in g["edges"].items():
            for rows in _batches([{"a": x, "b": y} for x, y in sorted(pairs)]):
                s.run(f"""UNWIND $rows AS r MATCH (a:{la} {{id:r.a}}), (b:{lb} {{id:r.b}})
                          MERGE (a)-[:{rel}]->(b)""", rows=rows).consume()

        # feed IPs: an Indicator each (history that outlives the Redis TTL); Feodo C2s also as
        # Infrastructure that HOSTS its malware family
        s.run("""UNWIND $rows AS r MERGE (n:Indicator {type:'ip', value:r.ip})
                 SET n.id = 'ioc:ip:' + r.ip, n.severity = r.severity, n.source = r.source""",
              rows=entries).consume()
        c2 = [{**e, "infra": "infra-c2-" + e["ip"].replace(".", "-"),
               "mal": malware_ids.get(e["malware"]),
               "notes": f"{e['source']}: {e['malware']} C2 on port {e.get('port')}, first seen {e['first_seen']}, "
                        f"last online {e['last_online']}"}
              for e in entries if e.get("malware")]
        s.run("""UNWIND $rows AS r MERGE (i:Infrastructure {id:r.infra})
                 SET i.value = r.ip, i.kind = 'c2-ip', i.notes = r.notes, i.source = r.source
                 WITH i, r MATCH (x:Indicator {type:'ip', value:r.ip}) MERGE (i)-[:OBSERVED_AS]->(x)
                 WITH i, r MATCH (m:Malware {id:r.mal}) MERGE (i)-[:HOSTS]->(m)""", rows=c2).consume()

        s.run("""UNWIND $rows AS r MERGE (n:Report {id:r.id})
                 SET n.title = r.title, n.source = r.source, n.date = r.date, n.tlp = r.tlp""",
              rows=[{"id": r["_id"], **{k: r[k] for k in ("title", "source", "date", "tlp")}} for r in reports]).consume()
        for key, label in (("actors", "ThreatActor"), ("campaigns", "Campaign"), ("malware", "Malware")):
            rows = [{"e": e, "r": r["_id"]} for r in reports for e in r.get(key, [])]
            for chunk in _batches(rows):
                s.run(f"""UNWIND $rows AS x MATCH (e:{label} {{id:x.e}}), (rep:Report {{id:x.r}})
                          MERGE (e)-[:MENTIONED_IN]->(rep)""", rows=chunk).consume()
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    return {"nodes": nodes, "relationships": rels}


def write_reports(reports: list[dict]) -> int:
    now = int(time.time())
    ops = [ReplaceOne({"_id": r["_id"]}, {**r, "ingested_at": now, "ingested_by": "import-feeds"}, upsert=True)
           for r in reports]
    stores.mongo_db().reports.bulk_write(ops, ordered=False)
    return len(ops)


def write_blocklist(entries: list[dict]) -> int:
    """Same key layout as blocklist.publish(), pipelined and paced for the hosted free plan."""
    r = stores.redis_client
    per_batch = REDIS_OPS_PER_S // 2      # two commands per entry
    for rows in _batches(entries, per_batch):
        t0, now = time.time(), int(time.time())
        pipe = r.pipeline(transaction=False)
        for e in rows:
            k = blocklist.key("ip", e["ip"])
            payload = {"value": e["ip"], "type": "ip", "actor": None, "campaign": None,
                       "severity": e["severity"], "ttl": e["ttl"], "published_by": "import-feeds",
                       "published_at": now, "source": e["source"], "malware": e.get("malware")}
            pipe.set(k, json.dumps(payload), ex=e["ttl"])
            pipe.zadd(blocklist.INDEX, {k: now + e["ttl"]})
        pipe.execute()
        time.sleep(max(0.0, 1.0 - (time.time() - t0)))
    return len(entries)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download the feeds even if cached today")
    args = ap.parse_args()

    t0 = time.time()
    print("1/5 feeds")
    attack = parse_attack(fetch("attack", args.refresh))
    entries = parse_ip_feeds(fetch("feodo", args.refresh), fetch("feodo_all", args.refresh),
                             fetch("et", args.refresh))
    stores.connect()
    stores.ensure_schema()

    print(f"2/5 Neo4j      ATT&CK {attack['version']}: mapping onto the existing graph")
    g = attack_graph(attack)
    malware_ids = {}
    for row in g["nodes"]["Malware"]:
        for form in [row["name"], *row["aliases"]]:
            malware_ids.setdefault(form, row["id"])
    reports = attack_reports(attack, g) + feed_reports(entries, malware_ids, attack)
    graph = write_graph(g, entries, reports, malware_ids)
    print(f"    {', '.join(f'{len(v)} {k}' for k, v in g['nodes'].items())}; "
          f"{sum(len(v) for v in g['edges'].values())} ATT&CK relationships; "
          f"graph now {graph['nodes']} nodes, {graph['relationships']} relationships")

    print(f"3/5 MongoDB    {write_reports(reports)} reports upserted")
    print(f"4/5 Redis      {write_blocklist(entries)} feed IPs on the blocklist "
          f"({Counter(e['source'] for e in entries).most_common()})")
    print("5/5 Qdrant     refitting the embedder and re-indexing every report")
    q = vectors.rebuild_all(documents.all_reports_raw())
    print(f"    {q['points']} chunks")
    stores.mongo_db().meta.update_one({"_id": "feeds"}, {"$set": {
        "at": datetime.now(timezone.utc), "attack_version": attack["version"], "reports": len(reports),
        "blocklist": len(entries), "graph": graph, "points": q["points"]}}, upsert=True)
    stores.close()
    print(f"done in {time.time() - t0:.0f} s — restart the API so it loads the refitted embedder")


if __name__ == "__main__":
    main()
