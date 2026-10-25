"""Ingest pipeline (FR1, FR8, Section 7.3).

A single ingest job writes Neo4j → MongoDB → Qdrant → (optionally) Redis in that order,
records every step in ``ingest_jobs`` (the ingest log), and is idempotent on retry.
There is no distributed two-phase commit: a failed fan-out is retried from the log.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
import uuid

from app import blocklist, documents, extract, graph, stores, vectors
from app.security import norm_tlp

STEPS = ["neo4j", "mongodb", "qdrant", "redis"]

TLP_MARKINGS = {
    "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9": "WHITE",
    "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da": "GREEN",
    "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82": "AMBER",
    "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed": "RED",
    # TLP 2.0 extension ids
    "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487": "WHITE",
    "marking-definition--bab4a63c-aed9-4cf5-a766-dfca5abac2bb": "GREEN",
    "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421": "AMBER",
    "marking-definition--939a9414-2ddd-4d32-a0cd-375ea402b003": "AMBER",
    "marking-definition--e828b379-4e03-4974-9ac4-e53a884c97c1": "RED",
}
PATTERN_RE = re.compile(
    r"\[\s*(ipv4-addr|ipv6-addr|domain-name|url|file:hashes\.'?(?:SHA-256|SHA-1|MD5)'?)"
    r"(?::value)?\s*=\s*'([^']+)'\s*\]", re.I)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or uuid.uuid4().hex[:8]


def report_id_for(seed: str) -> str:
    return "rpt-" + hashlib.sha1(seed.encode()).hexdigest()[:10]


def _empty_plan() -> dict:
    return {"nodes": [], "edges": [], "reports": [], "indicators": [], "bundle": None}


# ================================================================== free text
def plan_from_text(title: str, body: str, source: str = "analyst", date: str | None = None,
                   tlp: str = "AMBER", confidence: str = "medium", extra: dict | None = None,
                   actors: list[str] | None = None, report_id: str | None = None) -> dict:
    if not title.strip() or not body.strip():
        raise ValueError("title and body are required")
    linked = extract.link_entities(title + " " + body)
    by_label = lambda lab: sorted({e["id"] for e in linked if e["label"] == lab})  # noqa: E731
    iocs = extract.extract_iocs(body)
    refs = extract.extract_refs(body)
    doc = {
        "_id": report_id or report_id_for(title + body[:200]),
        "title": title.strip(), "source": source, "date": date or dt.date.today().isoformat(),
        "tlp": norm_tlp(tlp), "confidence": confidence, "body": body.strip(),
        "actors": sorted(set(by_label("ThreatActor")) | set(actors or [])),
        "campaigns": by_label("Campaign"), "malware": by_label("Malware"),
        "iocs": [i["value"] for i in iocs],
    }
    if refs["mitre"] or by_label("Technique"):
        doc["mitre"] = sorted(set(refs["mitre"]) | set(by_label("Technique")))
    if refs["cve"]:
        doc["cve"] = refs["cve"]
    for k, v in (extra or {}).items():  # report-specific nested fields (schema-on-read)
        if k not in doc and not k.startswith("$"):
            doc[k] = v
    plan = _empty_plan()
    plan["reports"].append(doc)
    plan["indicators"] = [{**i, "severity": "medium"} for i in iocs]
    plan["linked"] = linked
    return plan


# ================================================================== STIX 2.1
def _tlp_of(obj: dict, markings: dict) -> str | None:
    for ref in obj.get("object_marking_refs", []):
        if ref in TLP_MARKINGS:
            return TLP_MARKINGS[ref]
        if ref in markings:
            return markings[ref]
    return None


def _parse_pattern(pattern: str) -> tuple[str, str] | None:
    m = PATTERN_RE.search(pattern or "")
    if not m:
        return None
    kind, value = m.group(1).lower(), m.group(2)
    if kind.startswith("ipv"):
        return "ip", value
    if kind == "domain-name":
        return "domain", value.lower()
    if kind == "url":
        return "url", value
    return "hash", value.lower()


def _ext_id(obj: dict, source: str = "mitre-attack") -> str | None:
    for r in obj.get("external_references", []):
        if r.get("source_name") == source and r.get("external_id"):
            return r["external_id"]
    return None


REL_MAP = {
    # (stix rel, src label, dst label) -> (our rel, reverse?)
    ("uses", "ThreatActor", "Malware"): ("USES", False),
    ("uses", "Campaign", "Malware"): ("USES_MALWARE", False),
    ("uses", "ThreatActor", "Technique"): ("EMPLOYS", False),
    ("uses", "Campaign", "Technique"): ("EMPLOYS", False),
    ("uses", "Malware", "Technique"): ("IMPLEMENTS", False),
    ("uses", "ThreatActor", "Infrastructure"): ("USES_INFRA", False),
    ("uses", "Campaign", "Infrastructure"): ("USES_INFRA", False),
    ("attributed-to", "Campaign", "ThreatActor"): ("ATTRIBUTED_TO_CAMPAIGN", True),
    ("targets", "ThreatActor", "Victim"): ("TARGETS", False),
    ("targets", "Campaign", "Victim"): ("TARGETS", False),
    ("hosts", "Infrastructure", "Malware"): ("HOSTS", False),
    ("indicates", "Indicator", "Malware"): ("HAS_IOC", True),
    ("indicates", "Indicator", "Infrastructure"): ("OBSERVED_AS", True),
    ("based-on", "Indicator", "Infrastructure"): ("OBSERVED_AS", True),
    ("related-to", "ThreatActor", "ThreatActor"): ("SHARES_UNIT", False),
}


def plan_from_stix(bundle: dict, default_tlp: str = "AMBER") -> dict:
    if bundle.get("type") != "bundle" or not isinstance(bundle.get("objects"), list):
        raise ValueError("expected a STIX 2.1 bundle: {type: 'bundle', objects: [...]}")
    objs = {o["id"]: o for o in bundle["objects"] if isinstance(o, dict) and "id" in o}
    markings = {}
    for o in objs.values():
        if o.get("type") == "marking-definition":
            name = (o.get("name") or json.dumps(o.get("definition", {}))).upper()
            for t in ("WHITE", "CLEAR", "GREEN", "AMBER", "RED"):
                if t in name:
                    markings[o["id"]] = norm_tlp(t)
                    break
    targets = {r.get("target_ref") for r in objs.values()
               if r.get("type") == "relationship" and r.get("relationship_type") == "targets"}
    plan = _empty_plan()
    plan["bundle"] = {"_id": bundle.get("id") or f"bundle--{uuid.uuid4()}", "bundle": bundle}
    idmap: dict[str, tuple[str, str]] = {}  # stix id -> (label, our id)
    ind_by_stix: dict[str, dict] = {}

    def add(label: str, stix_id: str, props: dict):
        existing = extract.resolve_name(label, props.get("name") or props.get("value") or "")
        props["id"] = existing or props.get("id") or slug(props.get("name") or props.get("value"))
        idmap[stix_id] = (label, props["id"])
        plan["nodes"].append({"label": label, "props": props})

    for sid, o in objs.items():
        t = o.get("type")
        if t in ("threat-actor", "intrusion-set"):
            add("ThreatActor", sid, {
                "name": o.get("name"), "aliases": o.get("aliases", []),
                "origin": o.get("country") or o.get("x_origin"),
                "motivation": o.get("primary_motivation"),
                "sophistication": o.get("sophistication"),
                "sponsor": o.get("x_sponsor")})
        elif t == "campaign":
            add("Campaign", sid, {
                "name": o.get("name"), "summary": o.get("description"),
                "year": int(o["first_seen"][:4]) if o.get("first_seen") else None,
                "target_sector": o.get("x_target_sector")})
        elif t in ("malware", "tool"):
            add("Malware", sid, {
                "name": o.get("name"),
                "family": (o.get("aliases") or [o.get("name")])[0],
                "kind": "tool" if t == "tool" else ((o.get("malware_types") or ["malware"])[0])})
        elif t == "attack-pattern":
            tech_id = _ext_id(o) or slug(o.get("name"))
            idmap[sid] = ("Technique", tech_id)
            phases = o.get("kill_chain_phases") or [{}]
            plan["nodes"].append({"label": "Technique", "props": {
                "id": tech_id, "name": o.get("name"), "tactic": phases[0].get("phase_name")}})
        elif t == "infrastructure":
            add("Infrastructure", sid, {
                "name": None, "value": o.get("name"),
                "kind": (o.get("infrastructure_types") or ["unknown"])[0],
                "notes": o.get("description")})
        elif t == "identity" and sid in targets:
            add("Victim", sid, {"name": o.get("name"),
                                "sector": (o.get("sectors") or ["unknown"])[0],
                                "country": o.get("x_country")})
        elif t == "indicator":
            parsed = _parse_pattern(o.get("pattern", ""))
            if not parsed:
                continue
            itype, value = parsed
            ind = {"type": itype, "value": value, "severity": o.get("x_severity") or
                   ("high" if (o.get("confidence") or 0) >= 70 else "medium")}
            if o.get("valid_until"):
                try:
                    until = dt.datetime.fromisoformat(o["valid_until"].replace("Z", "+00:00"))
                    ind["ttl"] = int(until.timestamp() - time.time())
                except ValueError:
                    pass
            ind_by_stix[sid] = ind
            idmap[sid] = ("Indicator", f"ioc:{itype}:{value}")
            plan["indicators"].append(ind)
            if itype != "url":
                plan["nodes"].append({"label": "Indicator", "props": dict(ind)})

    for o in objs.values():
        if o.get("type") != "relationship":
            continue
        s, d = idmap.get(o.get("source_ref")), idmap.get(o.get("target_ref"))
        if not s or not d:
            continue
        m = REL_MAP.get((o.get("relationship_type"), s[0], d[0]))
        if not m:
            continue
        rel, rev = m
        a, b = (d, s) if rev else (s, d)
        plan["edges"].append({"src_label": a[0], "src": a[1], "rel": rel,
                              "dst_label": b[0], "dst": b[1]})

    reports = [o for o in objs.values() if o.get("type") == "report"]
    creators = {o["id"]: o.get("name") for o in objs.values() if o.get("type") == "identity"}

    def refs_of(ref_ids):
        out = {"ThreatActor": set(), "Campaign": set(), "Malware": set(), "iocs": set(),
               "Technique": set()}
        for r in ref_ids:
            if r in idmap:
                lab, i = idmap[r]
                if lab == "Indicator":
                    out["iocs"].add(ind_by_stix[r]["value"])
                elif lab in out:
                    out[lab].add(i)
        return out

    if not reports:  # a bundle without a report SDO still becomes a citable document
        desc = [f"{o.get('type')}: {o.get('name', '')} — {o.get('description', '')}".strip(" —")
                for o in objs.values() if o.get("type") not in ("relationship", "marking-definition")]
        reports = [{"id": plan["bundle"]["_id"], "name": f"STIX bundle {plan['bundle']['_id'][-12:]}",
                    "description": "\n".join(desc), "object_refs": list(objs)}]
    for rep in reports:
        r = refs_of(rep.get("object_refs", []))
        body = rep.get("description") or rep.get("name", "")
        doc = {
            "_id": report_id_for(rep["id"]), "title": rep.get("name", "Untitled STIX report"),
            "source": creators.get(rep.get("created_by_ref"), "STIX 2.1"),
            "date": (rep.get("published") or rep.get("created") or dt.date.today().isoformat())[:10],
            "tlp": _tlp_of(rep, markings) or norm_tlp(default_tlp),
            "confidence": str(rep.get("confidence", "medium")),
            "body": body, "actors": sorted(r["ThreatActor"]), "campaigns": sorted(r["Campaign"]),
            "malware": sorted(r["Malware"]), "iocs": sorted(r["iocs"]),
            "stix": rep, "stix_bundle_id": plan["bundle"]["_id"],
        }
        if r["Technique"]:
            doc["mitre"] = sorted(r["Technique"])
        if rep.get("report_types"):
            doc["report_types"] = rep["report_types"]
        # free-text linking catches entities the bundle only mentions in prose
        for e in extract.link_entities(body):
            key = {"ThreatActor": "actors", "Campaign": "campaigns", "Malware": "malware"}.get(e["label"])
            if key and e["id"] not in doc[key]:
                doc[key].append(e["id"])
        plan["reports"].append(doc)
    return plan


# ================================================================== execution
def _step_neo4j(plan: dict) -> dict:
    with stores.neo4j_session() as s:
        for n in plan["nodes"]:
            graph.merge_node(s, n["label"], n["props"])
        for e in plan["edges"]:
            graph.merge_edge(s, e["src_label"], e["src"], e["rel"], e["dst_label"], e["dst"])
        for doc in plan["reports"]:
            graph.merge_node(s, "Report", {"id": doc["_id"], "title": doc["title"],
                                           "source": doc["source"], "date": doc["date"],
                                           "tlp": doc["tlp"]})
            for key, label in (("actors", "ThreatActor"), ("campaigns", "Campaign"),
                               ("malware", "Malware")):
                s.run(f"""UNWIND $ids AS eid MATCH (x:{label} {{id:eid}}), (r:Report {{id:$rid}})
                          MERGE (x)-[:MENTIONED_IN]->(r)""", ids=doc.get(key, []), rid=doc["_id"])
        # link only this plan's values: a whole-graph join here grows with every ingest
        values = sorted({n["props"].get("value") for n in plan["nodes"]
                         if n["label"] in ("Infrastructure", "Indicator") and n["props"].get("value")})
        s.run("""UNWIND $values AS v MATCH (i:Infrastructure {value: v}), (x:Indicator {value: v})
                 MERGE (i)-[:OBSERVED_AS]->(x)""", values=values)
    if plan["nodes"]:  # only new graph entities change what linking can match
        extract.invalidate_gazetteer()
    return {"nodes": len(plan["nodes"]), "edges": len(plan["edges"]), "reports": len(plan["reports"])}


def _step_mongo(plan: dict, user: str) -> dict:
    now = int(time.time())
    for doc in plan["reports"]:
        documents.upsert_report({**doc, "ingested_at": now, "ingested_by": user})
    if plan.get("bundle"):
        stores.mongo_db().stix_bundles.replace_one(
            {"_id": plan["bundle"]["_id"]}, {**plan["bundle"], "ingested_at": now}, upsert=True)
    return {"reports": len(plan["reports"])}


def _step_qdrant(plan: dict) -> dict:
    ids = [d["_id"] for d in plan["reports"]]
    present = graph.existing_report_ids(ids)
    missing = set(ids) - present
    if missing:  # integrity rule: never index a document without its Report node
        raise RuntimeError(f"Report node missing for {sorted(missing)}")
    return {"chunks": sum(vectors.index_report(d) for d in plan["reports"])}


def _step_redis(plan: dict, opts: dict, user: str) -> dict:
    if not opts.get("publish_iocs"):
        return {"published": 0, "skipped": "publish_iocs not requested"}
    n = 0
    report = plan["reports"][0] if plan["reports"] else {}
    for ind in plan["indicators"]:
        ttl = int(ind.get("ttl") or opts.get("ttl") or 86400)
        if ttl <= 0:
            continue  # STIX valid_until already in the past
        blocklist.publish(ind["type"], ind["value"], ttl, ind.get("severity", "medium"),
                          actor=(report.get("actors") or [None])[0],
                          campaign=(report.get("campaigns") or [None])[0],
                          published_by=user, source=report.get("_id"))
        n += 1
    return {"published": n}


def create_job(kind: str, plan: dict, user: str, opts: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    stores.mongo_db().ingest_jobs.insert_one({
        "_id": job_id, "kind": kind, "created_at": int(time.time()), "user": user,
        "status": "pending", "opts": opts,
        "steps": {s: {"status": "pending"} for s in STEPS},
        "report_ids": [d["_id"] for d in plan["reports"]],
        "plan": json.loads(json.dumps(plan, default=str)),
    })
    return job_id


def run_job(job_id: str) -> dict:
    col = stores.mongo_db().ingest_jobs
    job = col.find_one({"_id": job_id})
    if not job:
        raise KeyError(job_id)
    plan, opts, user = job["plan"], job.get("opts", {}), job["user"]
    col.update_one({"_id": job_id}, {"$set": {"status": "running", "error": None},
                                     "$inc": {"attempts": 1}})
    for step in STEPS:
        if job["steps"][step]["status"] == "ok":
            continue  # retry resumes from the first step that did not complete
        t0 = time.perf_counter()
        try:
            if step == "neo4j":
                res = _step_neo4j(plan)
            elif step == "mongodb":
                res = _step_mongo(plan, user)
            elif step == "qdrant":
                res = _step_qdrant(plan)
            else:
                res = _step_redis(plan, opts, user)
            job["steps"][step] = {"status": "ok", "result": res,
                                  "ms": round((time.perf_counter() - t0) * 1000, 1)}
            col.update_one({"_id": job_id}, {"$set": {f"steps.{step}": job["steps"][step]}})
        except Exception as e:  # noqa: BLE001
            job["steps"][step] = {"status": "failed", "error": str(e)[:400]}
            col.update_one({"_id": job_id}, {"$set": {f"steps.{step}": job["steps"][step],
                                                      "status": "failed", "error": str(e)[:400]}})
            return col.find_one({"_id": job_id}, {"plan": 0})
    col.update_one({"_id": job_id}, {"$set": {"status": "ok", "finished_at": int(time.time())}})
    return col.find_one({"_id": job_id}, {"plan": 0})


def ingest(kind: str, plan: dict, user: str, opts: dict) -> dict:
    job = run_job(create_job(kind, plan, user, opts))
    job["linked"] = plan.get("linked", [])
    job["preview"] = [{k: d.get(k) for k in ("_id", "title", "tlp", "actors", "campaigns",
                                              "malware", "iocs")} for d in plan["reports"]]
    return job


def list_jobs(limit: int = 50) -> list[dict]:
    return list(stores.mongo_db().ingest_jobs.find({}, {"plan": 0})
                .sort("created_at", -1).limit(limit))


def delete_report(report_id: str) -> dict:
    """Section 8.5: deleting a report removes its chunks and detaches MENTIONED_IN edges."""
    vectors.delete_report_chunks(report_id)
    with stores.neo4j_session() as s:
        s.run("MATCH (r:Report {id:$id}) DETACH DELETE r", id=report_id)
    return {"deleted": documents.delete_report(report_id)}
