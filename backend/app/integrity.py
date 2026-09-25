"""Cross-model integrity rules (Section 8.5) — used by the ops console and evaluation."""
from __future__ import annotations

import time

from app import stores, vectors


def check() -> dict:
    db = stores.mongo_db()
    mongo_ids = {d["_id"] for d in db.reports.find({}, {"_id": 1})}
    with stores.neo4j_session() as s:
        node_ids = {r["id"] for r in s.run("MATCH (r:Report) RETURN r.id AS id")}
        indicator_vals = {r["v"] for r in s.run("MATCH (i:Indicator) RETURN i.value AS v")}
    doc_iocs = {v for d in db.reports.find({}, {"iocs": 1}) for v in d.get("iocs", [])}
    qdrant_reports = vectors.report_ids_in_index()
    r = stores.redis_client
    live_keys = r.zrangebyscore("ioc:index", int(time.time()), "+inf")
    redis_vals = {k.split(":", 2)[2] for k in live_keys}

    rules = [
        {"rule": "Every MongoDB _id has a Report node",
         "violations": sorted(mongo_ids - node_ids)},
        {"rule": "Every Report node has a MongoDB document",
         "violations": sorted(node_ids - mongo_ids)},
        {"rule": "Every Qdrant point.report_id exists in MongoDB",
         "violations": sorted(qdrant_reports - mongo_ids)},
        {"rule": "Redis IOCs traceable to an Indicator node or a document iocs[] (informational — operators may publish new IOCs, FR12)",
         "violations": sorted(redis_vals - indicator_vals - doc_iocs)},
        {"rule": "Every MongoDB report has chunks in Qdrant (informational)",
         "violations": sorted(mongo_ids - qdrant_reports)},
    ]
    for x in rules:
        x["ok"] = not x["violations"]
    return {"ok": all(x["ok"] for x in rules[:3]), "rules": rules,
            "counts": {"mongodb_reports": len(mongo_ids), "report_nodes": len(node_ids),
                       "qdrant_reports": len(qdrant_reports), "redis_live": len(redis_vals)}}
