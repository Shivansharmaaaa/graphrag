"""GraphRAG orchestrator (FR5, FR7, FR10, NFR4, Section 7.1).

Four-channel retrieval → context pack with citation keys → local LLM → groundedness gate → audit.

Citation keys in the context pack:
  [G#]        a typed graph edge from Neo4j
  [C#]        a Qdrant chunk (point id + report_id)
  [R:<id>]    a MongoDB report (_id)
  [I#]        a live / absent Redis IOC state
"""
from __future__ import annotations

import re
import time
import uuid

import httpx

from app import blocklist, documents, extract, graph, stores, vectors
from app.config import settings
from app.metrics import record, timed
from app.security import can_read, max_tlp, norm_tlp

TAG_RE = re.compile(r"\[(G\d+|C\d+|I\d+|R:[\w.\-]+)\]")
REFUSAL = "Insufficient evidence in the CTI stores to answer this question."
SHARE_WORDS = ("share", "shared", "overlap", "infrastructure", "c2", "command-and-control",
               "command and control", "domain", "domains", " ip")
TOOL_WORDS = ("use", "uses", "using", "tool", "tooling", "besides")
VERBS = {"USES": "uses", "USES_INFRA": "uses infrastructure", "HOSTS": "hosts",
         "ATTRIBUTED_TO_CAMPAIGN": "is attributed to campaign", "USES_MALWARE": "used malware",
         "EMPLOYS": "employs technique", "IMPLEMENTS": "implements technique",
         "HAS_IOC": "has indicator", "OBSERVED_AS": "is observed as indicator",
         "TARGETS": "targets", "MENTIONED_IN": "is mentioned in report",
         "SHARES_UNIT": "shares a parent unit with"}


# ================================================================== retrieval
def _retrieve(question: str, user: dict, max_hops: int, k: int, t: dict) -> dict:
    q_low = question.lower()
    with timed("linking", t):
        linked = [e for e in extract.link_entities(question) if e["label"] != "Report"]
        q_iocs = extract.extract_iocs(question)

    # channel 1 — Qdrant k-NN (TLP filtered in the payload filter)
    vs = vectors.search(question, user, k=k, with_map=True, sink=t)
    chunks = vs["hits"]

    # channel 2 — Neo4j expansion from linked entities (fallback: actors in top chunks)
    seeds = [e["id"] for e in linked if e["label"] != "Indicator"]
    seed_source = "entity-linking"
    if not seeds:
        seeds = list(dict.fromkeys(a for c in chunks[:3] for a in c.get("actors", [])))
        seed_source = "vector-hits"
    for i in q_iocs:
        seeds += [n["id"] for n in graph.search(i["value"], 3)]
    sub = graph.subgraph_for_entities(seeds, hops=max_hops, sink=t)

    actors = [e["id"] for e in linked if e["label"] == "ThreatActor"]
    tools = [e["id"] for e in linked if e["label"] == "Malware"]
    findings = {"shared_infra": [], "tool_users": []}
    if any(w in f" {q_low}" for w in SHARE_WORDS):
        for a in actors or [None]:
            findings["shared_infra"] += graph.shared_infrastructure(a, sink=t)
    if tools and any(w in q_low for w in TOOL_WORDS):
        for m in tools:
            findings["tool_users"].append(graph.tool_users(m, sink=t))
    hubs = graph.hub_ids()

    # make templated findings citable as edges too
    extra_edges = []
    for row in findings["shared_infra"]:
        extra_edges += [(row["actor"], "USES_INFRA", row["infra_id"]),
                        (row["other"], "USES_INFRA", row["infra_id"])]
    for tu in findings["tool_users"]:
        extra_edges += [(u["actor"], "USES", tu["malware_id"]) for u in tu["users"]]
    names = {n["id"]: n for n in sub["nodes"]}
    missing = {x for e in extra_edges for x in (e[0], e[2])} - set(names)
    for nid in missing:
        n = graph.get_node(nid)
        if n:
            names[nid] = n
    edge_set = {(e["source"], e["type"], e["target"]) for e in sub["edges"]}
    edges = list(sub["edges"]) + [{"source": s, "type": r, "target": d, "props": {}}
                                  for s, r, d in extra_edges if (s, r, d) not in edge_set]

    # TLP: drop Report nodes (and their edges) the analyst may not read
    hidden = {nid for nid, n in names.items()
              if n["label"] == "Report" and not can_read(user, n["props"].get("tlp"))}
    edges = [e for e in edges if e["source"] not in hidden and e["target"] not in hidden]

    # rank edges: templated findings, then edges touching seeds, then USES_INFRA/HOSTS/MENTIONED_IN
    pri = {"USES_INFRA": 0, "HOSTS": 0, "MENTIONED_IN": 1, "SHARES_UNIT": 1}
    extra_keys = set(extra_edges)
    seed_set = set(seeds)

    def rank(e):
        return ((e["source"], e["type"], e["target"]) not in extra_keys,
                not (e["source"] in seed_set or e["target"] in seed_set),
                pri.get(e["type"], 2))
    edges = sorted({(e["source"], e["type"], e["target"]): e for e in edges}.values(), key=rank)[:60]

    # channel 3 — MongoDB hydration: chunk report_ids ∪ graph Report nodes, only if a Report node exists
    # priority: reports backing templated graph findings → vector hits → other MENTIONED_IN edges
    rep_ids = []
    readable_nodes = {nid for nid, n in names.items() if n["label"] == "Report" and nid not in hidden}
    for row in findings["shared_infra"]:
        # TLP: never surface a report id the analyst may not read
        row["reports"] = [x for x in row.get("reports", []) if x not in hidden and
                          (x in readable_nodes or x not in names)]
        rep_ids += row["reports"][:1]
    rep_ids += [c["report_id"] for c in chunks]
    rep_ids += [e["target"] for e in edges if e["type"] == "MENTIONED_IN"]
    rep_ids = list(dict.fromkeys(rep_ids))
    with timed("neo4j", t):
        with_node = graph.existing_report_ids(rep_ids)
    orphan = [r for r in rep_ids if r not in with_node]
    docs, withheld = documents.hydrate([r for r in rep_ids if r in with_node][:10], user, sink=t)
    order = {r: i for i, r in enumerate(rep_ids)}
    docs.sort(key=lambda d: order.get(d["_id"], 99))

    # channel 4 — Redis live IOC state (never a Mongo fallback — NFR3)
    ioc_values = [i["value"] for i in q_iocs]
    ioc_values += [names[x]["props"].get("value") for e in edges for x in (e["source"], e["target"])
                   if x in names and names[x]["label"] in ("Infrastructure", "Indicator")]
    for d in docs[:4]:
        ioc_values += d.get("iocs", [])[:6]
    ioc_values = [v for v in dict.fromkeys(ioc_values) if v][:25]
    redis_ok = True
    try:
        with timed("redis", t):
            iocs = blocklist.lookup_many(ioc_values)
    except Exception:  # NFR8: read path degrades gracefully when Redis is down
        redis_ok = False
        iocs = [{"value": v, "type": blocklist.infer_type(v), "state": "unknown (redis down)",
                 "ttl_remaining": None} for v in ioc_values]

    return {"linked": linked, "q_iocs": q_iocs, "seeds": seeds, "seed_source": seed_source,
            "chunks": chunks, "map": vs["map"], "nodes": names, "edges": edges,
            "findings": findings, "hubs": hubs, "docs": docs, "withheld": withheld,
            "orphan_chunks": orphan, "iocs": iocs, "redis_ok": redis_ok}


# ================================================================== context pack
def _nm(nodes: dict, nid: str) -> str:
    n = nodes.get(nid)
    return f"{n['name']} ({n['label']})" if n else nid


def build_context(r: dict) -> dict:
    facts, fact_index = [], {}
    for i, e in enumerate(r["edges"], start=1):
        gid = f"G{i}"
        fact_index[(e["source"], e["type"], e["target"])] = gid
        facts.append({"cid": gid, "source": e["source"], "type": e["type"], "target": e["target"],
                      "text": f"{_nm(r['nodes'], e['source'])} -[{e['type']}]-> "
                              f"{_nm(r['nodes'], e['target'])}"})
    chunks = [{"cid": f"C{i}", **c} for i, c in enumerate(r["chunks"], start=1)]
    iocs = [{"cid": f"I{i}", **x} for i, x in enumerate(r["iocs"], start=1)]
    hub_notes = [f"{_nm(r['nodes'], h)} is used by {n} actors — a commodity hub and weak "
                 f"attribution feature; pair it with victim sector or C2 context."
                 for h, n in r["hubs"].items()
                 if h in r["nodes"] or any(h == e["target"] for e in r["edges"])]
    return {"facts": facts, "fact_index": fact_index, "chunks": chunks, "iocs": iocs,
            "hub_notes": hub_notes}


def _ioc_line(x: dict) -> str:
    if x["state"] == "live":
        return (f"{x['value']} ({x['type']}) is LIVE on the blocklist, severity {x.get('severity')}, "
                f"TTL {_fmt_ttl(x['ttl_remaining'])} remaining")
    if x["state"] == "not-in-blocklist":
        return f"{x['value']} ({x['type']}) is NOT in the hot blocklist (expired or never published)"
    return f"{x['value']} ({x['type']}) state unknown: blocklist store unavailable"


def _fmt_ttl(s: int | None) -> str:
    if not s or s <= 0:
        return "0s"
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    return (f"{d}d {h}h" if d else f"{h}h {m}m" if h else f"{m}m {sec}s" if m else f"{sec}s")


def render_prompt(question: str, ctx: dict, docs: list[dict]) -> str:
    lines = ["GRAPH FACTS (Neo4j):"]
    lines += [f"[{f['cid']}] {f['text']}" for f in ctx["facts"]] or ["(none)"]
    lines.append("\nREPORT PASSAGES (Qdrant):")
    lines += [f"[{c['cid']}] (report {c['report_id']}, \"{c['title']}\", score {c['score']}) {c['text']}"
              for c in ctx["chunks"]] or ["(none)"]
    lines.append("\nSOURCE DOCUMENTS (MongoDB):")
    for d in docs:
        extra = {k: d[k] for k in documents.variable_fields(d)}
        lines.append(f"[R:{d['_id']}] \"{d.get('title')}\" ({d.get('date')}, TLP:{d.get('tlp')}) "
                     f"actors={d.get('actors', [])} {extra if extra else ''}\n    {d.get('body', '')[:700]}")
    if not docs:
        lines.append("(none)")
    lines.append("\nLIVE IOC STATE (Redis):")
    lines += [f"[{x['cid']}] {_ioc_line(x)}" for x in ctx["iocs"]] or ["(none)"]
    if ctx["hub_notes"]:
        lines.append("\nCAUTIONS:")
        lines += [f"- {h}" for h in ctx["hub_notes"]]
    lines.append(f"\nQUESTION: {question}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a cyber threat intelligence analyst assistant inside a SOC.
Answer ONLY from the evidence provided (graph facts, report passages, source documents, IOC state).
Rules:
1. Every sentence MUST end with one or more citation tags copied exactly from the evidence,
   e.g. [G3], [C1], [R:rpt-002], [I2]. A sentence without a tag will be deleted.
2. Never invent actors, relationships, indicators or dates that are not in the evidence.
3. If a tool is flagged as a commodity hub, say explicitly that it is weak attribution and pair
   it with victim sector or C2 context.
4. When indicators are mentioned, state whether they are live on the blocklist or not.
5. If the evidence does not answer the question, reply exactly:
   "Insufficient evidence in the CTI stores to answer this question."
6. Do not produce exploit code, payloads or offensive instructions.
Write 3-8 concise sentences of plain prose (no markdown headings)."""


def call_llm(prompt: str, t: dict) -> str:
    with timed("llm", t):
        r = httpx.post(
            f"{settings.ollama_url}/api/chat",
            json={"model": settings.ollama_model, "stream": False,
                  "options": {"temperature": 0.1, "num_ctx": 8192},
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": prompt}]},
            timeout=settings.llm_timeout_s,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


# ================================================================== retrieve-only answer
def extractive_answer(r: dict, ctx: dict) -> str:
    """Deterministic evidence rendering when the LLM is down or disabled (Risk table)."""
    fi, nodes, out = ctx["fact_index"], r["nodes"], []
    readable = {d["_id"] for d in r["docs"]}

    def tag(*keys):
        return " ".join(f"[{fi[k]}]" for k in keys if k in fi)

    seen_pairs = set()
    for row in r["findings"]["shared_infra"][:8]:
        pair = (frozenset((row["actor"], row["other"])), row["infra_id"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        hosted = f", which hosted {', '.join(row['hosted_malware'])}" if row["hosted_malware"] else ""
        out.append(f"{row['actor_name']} and {row['other_name']} both use {row['kind']} {row['infra']}"
                   f"{hosted} {tag((row['actor'], 'USES_INFRA', row['infra_id']), (row['other'], 'USES_INFRA', row['infra_id']))}"
                   + (f" [R:{rdocs[0]}]" if (rdocs := [x for x in row.get("reports", []) if x in readable]) else "")
                   + ".")
    for tu in r["findings"]["tool_users"]:
        names = [u["actor_name"] for u in tu["users"]]
        tags = tag(*[(u["actor"], "USES", tu["malware_id"]) for u in tu["users"]])
        out.append(f"{tu['users'][0]['malware'] if tu['users'] else tu['malware_id']} is used by "
                   f"{', '.join(names)} {tags}.")
        if tu["commodity_hub"]:
            out.append(f"Because {len(names)} unrelated actors use it, it is a commodity tool and a weak "
                       f"attribution signal; pair it with victim sector or C2 context {tags}.")
    # facts touching the linked entities (campaigns, tooling, infrastructure) — after templated findings
    seeds = set(r["seeds"])
    seed_facts = [f for f in ctx["facts"] if (f["source"] in seeds or f["target"] in seeds)
                  and f["type"] not in ("MENTIONED_IN",)]
    used = {c for line in out for c in TAG_RE.findall(line)}
    prio = {"ATTRIBUTED_TO_CAMPAIGN": 0, "SHARES_UNIT": 1, "USES": 2, "TARGETS": 3, "USES_INFRA": 4}
    seed_facts.sort(key=lambda f: prio.get(f["type"], 5))
    for f in [f for f in seed_facts if f["cid"] not in used][: (6 if out else 8)]:
        out.append(f"{_nm(nodes, f['source']).split(' (')[0]} {VERBS.get(f['type'], f['type'])} "
                   f"{_nm(nodes, f['target']).split(' (')[0]} [{f['cid']}].")
    if not out:
        for f in ctx["facts"][:6]:
            out.append(f"{_nm(nodes, f['source']).split(' (')[0]} {VERBS.get(f['type'], f['type'])} "
                       f"{_nm(nodes, f['target']).split(' (')[0]} [{f['cid']}].")
    for c in [c for c in ctx["chunks"] if c["score"] >= 0.2][:3]:
        first = re.split(r"(?<=[.!?])\s+", c["text"])[0]
        out.append(f"Report \"{c['title']}\" states: {first.rstrip('.')} [{c['cid']}] [R:{c['report_id']}].")
    for x in ctx["iocs"][:6]:
        out.append(f"{_ioc_line(x)} [{x['cid']}].")
    return " ".join(out) if out else REFUSAL


# ================================================================== groundedness gate
_MULTI_TAG = re.compile(r"\[((?:[GCI]\d+|R:[\w.\-]+)(?:\s*[,;]\s*(?:[GCI]\d+|R:[\w.\-]+))+)\]")


def normalise_tags(text: str) -> str:
    """LLMs often write [G1, G2] or [R:rpt-001; C3] — expand to one tag per bracket."""
    return _MULTI_TAG.sub(lambda m: " ".join(f"[{t.strip()}]" for t in re.split(r"[,;]", m.group(1))), text)


def split_sentences(text: str) -> list[str]:
    text = normalise_tags(text)
    # move citation tags that follow the full stop in front of it: "foo. [G1]" -> "foo [G1]."
    text = re.sub(r"([.!?])\s*((?:\[[^\]]+\]\s*)+)", lambda m: " " + m.group(2).strip() + m.group(1) + " ", text)
    parts = []
    for line in text.splitlines():
        line = line.strip(" -*•\t")
        if line:
            parts += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", line) if s.strip()]
    return parts


def enforce_grounding(answer: str, ctx: dict, docs: list[dict]) -> dict:
    valid = {f["cid"] for f in ctx["facts"]} | {c["cid"] for c in ctx["chunks"]} | \
            {x["cid"] for x in ctx["iocs"]} | {f"R:{d['_id']}" for d in docs} | \
            {f"R:{c['report_id']}" for c in ctx["chunks"]}
    if answer.strip().startswith(REFUSAL[:30]):
        return {"answer": REFUSAL, "kept": [], "dropped": [], "coverage": 0.0, "refused": True,
                "citations": []}
    kept, dropped, cites = [], [], []
    for s in split_sentences(answer):
        tags = [t for t in TAG_RE.findall(s) if t in valid]
        if tags:
            s = TAG_RE.sub(lambda m: m.group(0) if m.group(1) in valid else "", s)
            kept.append(re.sub(r"\s+([.!?])", r"\1", re.sub(r"\s{2,}", " ", s)).strip())
            cites += tags
        else:
            dropped.append(s)
    total = len(kept) + len(dropped)
    coverage = round(len(kept) / total, 3) if total else 0.0
    refused = not kept or coverage < settings.min_citation_coverage
    return {"answer": REFUSAL if refused else " ".join(kept), "kept": kept, "dropped": dropped,
            "coverage": coverage, "refused": refused, "citations": list(dict.fromkeys(cites))}


# ================================================================== entry point
def ask(question: str, user: dict, max_hops: int = 2, k: int | None = None,
        use_llm: bool = True) -> dict:
    t0 = time.perf_counter()
    t: dict = {}
    k = k or settings.vector_top_k
    r = _retrieve(question, user, max_hops, k, t)
    ctx = build_context(r)
    prompt = render_prompt(question, ctx, r["docs"])

    mode, llm_error, raw = "retrieve-only", None, None
    if use_llm:
        try:
            raw = call_llm(prompt, t)
            mode = "llm"
        except Exception as e:  # NFR8 / risk: LLM down → retrieve-only still answers
            llm_error = str(e)[:200]
    if raw is None:
        raw = extractive_answer(r, ctx)
    gate = enforce_grounding(raw, ctx, r["docs"])
    if gate["refused"] and mode == "llm":
        # LLM ignored the citation contract — fall back to deterministic evidence rendering
        fallback = enforce_grounding(extractive_answer(r, ctx), ctx, r["docs"])
        if not fallback["refused"]:
            gate, mode = fallback, "retrieve-only (llm answer failed grounding)"

    cited_reports = {c[2:] for c in gate["citations"] if c.startswith("R:")}
    cited_reports |= {c["report_id"] for c in ctx["chunks"] if c["cid"] in gate["citations"]}
    doc_tlp = {d["_id"]: d.get("tlp") for d in r["docs"]}
    doc_tlp.update({c["report_id"]: c.get("tlp") for c in ctx["chunks"]})
    answer_tlp = max_tlp([doc_tlp.get(x) for x in cited_reports] or ["WHITE"])

    total_ms = round((time.perf_counter() - t0) * 1000, 1)
    record("graphrag", total_ms)
    t["total"] = total_ms

    used_nodes = {e["source"] for e in r["edges"]} | {e["target"] for e in r["edges"]}
    result = {
        "id": uuid.uuid4().hex[:12], "question": question, "mode": mode, "llm_error": llm_error,
        "llm_model": settings.ollama_model if mode == "llm" else None,
        "answer": gate["answer"], "raw_answer": raw, "refused": gate["refused"],
        "dropped_sentences": gate["dropped"], "citation_coverage": gate["coverage"],
        "citations": gate["citations"], "answer_tlp": answer_tlp,
        "linked_entities": r["linked"], "seeds": r["seeds"], "seed_source": r["seed_source"],
        "evidence": {
            "graph": {"nodes": [r["nodes"][n] for n in used_nodes if n in r["nodes"]],
                      "edges": [{**e, "cid": ctx["fact_index"][(e["source"], e["type"], e["target"])]}
                                for e in r["edges"]]},
            "facts": ctx["facts"],
            "chunks": [{k2: v for k2, v in c.items()} for c in ctx["chunks"]],
            "similarity_map": r["map"],
            "documents": [{"_id": d["_id"], "title": d.get("title"), "date": d.get("date"),
                           "tlp": d.get("tlp"), "source": d.get("source"),
                           "actors": d.get("actors", []), "variable_fields": documents.variable_fields(d)}
                          for d in r["docs"]],
            "withheld_by_tlp": len(r["withheld"]),
            "orphan_chunks_refused": r["orphan_chunks"],
            "iocs": ctx["iocs"], "redis_available": r["redis_ok"],
            "hub_notes": ctx["hub_notes"],
            "findings": r["findings"],
        },
        "latency_ms": t,
        "params": {"max_hops": max_hops, "k": k, "use_llm": use_llm},
    }
    save_audit(result, user)
    return result


# ================================================================== audit / replay (FR10)
def save_audit(res: dict, user: dict) -> None:
    ev = res["evidence"]
    stores.mongo_db().audit_log.insert_one({
        "_id": res["id"], "ts": int(time.time()), "user": user["username"],
        "clearance": user["clearance"], "question": res["question"], "params": res["params"],
        "mode": res["mode"], "llm_model": res["llm_model"], "answer": res["answer"],
        "raw_answer": res["raw_answer"], "dropped_sentences": res["dropped_sentences"],
        "citation_coverage": res["citation_coverage"], "citations": res["citations"],
        "refused": res["refused"], "answer_tlp": res["answer_tlp"],
        "linked_entities": [e["id"] for e in res["linked_entities"]],
        "hops": [{"cid": e["cid"], "source": e["source"], "type": e["type"], "target": e["target"]}
                 for e in ev["graph"]["edges"]],
        "chunks": [{"cid": c["cid"], "point_id": c["point_id"], "report_id": c["report_id"],
                    "score": c["score"]} for c in ev["chunks"]],
        "documents": [{"_id": d["_id"], "tlp": d["tlp"]} for d in ev["documents"]],
        "iocs": [{"cid": x["cid"], "key": x.get("key"), "value": x["value"], "state": x["state"],
                  "ttl_remaining": x.get("ttl_remaining")} for x in ev["iocs"]],
        "latency_ms": res["latency_ms"],
    })


def list_audit(user: dict, limit: int = 50) -> list[dict]:
    q = {} if user["role"] == "admin" else {"user": user["username"]}
    return list(stores.mongo_db().audit_log.find(
        q, {"question": 1, "ts": 1, "user": 1, "mode": 1, "citation_coverage": 1, "refused": 1,
            "answer_tlp": 1, "latency_ms.total": 1}).sort("ts", -1).limit(limit))


def get_audit(audit_id: str, user: dict) -> dict | None:
    doc = stores.mongo_db().audit_log.find_one({"_id": audit_id})
    if not doc or (user["role"] != "admin" and doc["user"] != user["username"]):
        return None
    if not can_read(user, doc.get("answer_tlp")):
        return None
    return doc


def replay(audit_id: str, user: dict) -> dict | None:
    """Re-verify every artefact of a past answer against the stores that produced it."""
    doc = get_audit(audit_id, user)
    if not doc:
        return None
    hop_ok = graph.edges_exist(doc["hops"])
    pts = {p["point_id"]: p for p in vectors.get_points([c["point_id"] for c in doc["chunks"]])}
    doc_ids = [d["_id"] for d in doc["documents"]]
    present_docs = {d["_id"] for d in stores.mongo_db().reports.find({"_id": {"$in": doc_ids}}, {"_id": 1})}
    report_nodes = graph.existing_report_ids(doc_ids)
    try:
        now = {x["value"]: x for x in blocklist.lookup_many([i["value"] for i in doc["iocs"]])}
        redis_ok = True
    except Exception:
        now, redis_ok = {}, False
    return {
        "audit_id": audit_id, "question": doc["question"], "answer": doc["answer"],
        "hops": [{**h, "still_exists": ok} for h, ok in zip(doc["hops"], hop_ok)],
        "chunks": [{**c, "still_exists": c["point_id"] in pts and
                    pts[c["point_id"]]["report_id"] == c["report_id"]} for c in doc["chunks"]],
        "documents": [{**d, "in_mongodb": d["_id"] in present_docs,
                       "has_report_node": d["_id"] in report_nodes} for d in doc["documents"]],
        "iocs": [{**i, "state_now": now.get(i["value"], {}).get("state", "unknown"),
                  "ttl_now": now.get(i["value"], {}).get("ttl_remaining"),
                  "changed": now.get(i["value"], {}).get("state") != i["state"]}
                 for i in doc["iocs"]],
        "redis_available": redis_ok,
        "summary": {
            "hops_verified": f"{sum(hop_ok)}/{len(hop_ok)}",
            "chunks_verified": f"{sum(1 for c in doc['chunks'] if c['point_id'] in pts)}/{len(doc['chunks'])}",
            "documents_verified": f"{len(present_docs & report_nodes)}/{len(doc_ids)}",
            "ioc_state_changes": sum(1 for i in doc["iocs"]
                                     if now.get(i["value"], {}).get("state") != i["state"]),
        },
    }
