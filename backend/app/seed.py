"""Initial public-knowledge corpus loader (FR8).

Order follows the ingest contract (Section 7.3): Neo4j → MongoDB → Qdrant → Redis.
Every step is idempotent (MERGE / replace_one / delete+upsert / SET EX).
"""
from __future__ import annotations

import time

from app import blocklist, documents, stores, vectors
from app.data import (ACTORS, CAMPAIGNS, INDICATORS, INFRASTRUCTURE, MALWARE,
                      MALWARE_HASHES, RELATIONSHIPS, REPORTS, TECHNIQUES, VICTIM_RELS,
                      VICTIMS)
from app.security import ensure_default_users


def is_seeded() -> bool:
    try:
        return stores.mongo_db().reports.estimated_document_count() > 0
    except Exception:
        return False


def seed_all(force: bool = False) -> dict:
    if is_seeded() and not force:
        return {"skipped": True}
    t0 = time.time()
    stats = {
        "neo4j": seed_neo4j(),
        "mongodb": seed_mongo(),
        "qdrant": vectors.rebuild_all(documents.all_reports_raw()),
        "redis": seed_redis(),
    }
    ensure_default_users()
    stats["seconds"] = round(time.time() - t0, 2)
    stores.mongo_db().meta.update_one({"_id": "seed"}, {"$set": {"at": int(time.time()), **{
        k: v for k, v in stats.items() if k != "seconds"}}}, upsert=True)
    return stats


def seed_neo4j() -> dict:
    with stores.neo4j_session() as s:
        s.run("MATCH (n) DETACH DELETE n")
        s.run("""UNWIND $rows AS r MERGE (n:ThreatActor {id:r.id})
                 SET n.name=r.name, n.aliases=r.aliases, n.origin=r.origin, n.sponsor=r.sponsor,
                     n.motivation=r.motivation, n.sophistication=r.sophistication""", rows=ACTORS)
        s.run("""UNWIND $rows AS r MERGE (n:Campaign {id:r.id})
                 SET n.name=r.name, n.year=r.year, n.target_sector=r.target_sector,
                     n.summary=r.summary""", rows=CAMPAIGNS)
        s.run("""UNWIND $rows AS r MERGE (n:Malware {id:r.id})
                 SET n.name=r.name, n.family=r.family, n.kind=r.kind""", rows=MALWARE)
        s.run("""UNWIND $rows AS r MERGE (n:Technique {id:r.id})
                 SET n.name=r.name, n.tactic=r.tactic""", rows=TECHNIQUES)
        s.run("""UNWIND $rows AS r MERGE (n:Infrastructure {id:r.id})
                 SET n.value=r.value, n.kind=r.kind, n.notes=r.notes""", rows=INFRASTRUCTURE)
        s.run("""UNWIND $rows AS r MERGE (n:Victim {id:r.id})
                 SET n.name=r.name, n.sector=r.sector, n.country=r.country""", rows=VICTIMS)
        # Indicator nodes (historical fact — independent of Redis TTL)
        s.run("""UNWIND $rows AS r MERGE (n:Indicator {type:r.type, value:r.value})
                 SET n.id='ioc:'+r.type+':'+r.value, n.severity=r.severity""", rows=INDICATORS)
        for la, a, rel, lb, b in RELATIONSHIPS + VICTIM_RELS:
            s.run(f"MATCH (a:{la} {{id:$a}}), (b:{lb} {{id:$b}}) MERGE (a)-[:{rel}]->(b)", a=a, b=b)
        # Infrastructure -[:OBSERVED_AS]-> Indicator (same network value)
        s.run("""MATCH (i:Infrastructure), (x:Indicator) WHERE i.value = x.value
                 MERGE (i)-[:OBSERVED_AS]->(x)""")
        # Malware -[:HAS_IOC]-> Indicator (file hashes)
        s.run("""UNWIND $rows AS r MATCH (m:Malware {id:r[0]}), (x:Indicator {value:r[1]})
                 MERGE (m)-[:HAS_IOC]->(x)""", rows=[list(x) for x in MALWARE_HASHES])
        s.run("""UNWIND $rows AS r MERGE (n:Report {id:r.id})
                 SET n.title=r.title, n.source=r.source, n.date=r.date, n.tlp=r.tlp""",
              rows=[{k: r[k] for k in ("id", "title", "source", "date", "tlp")} for r in REPORTS])
        for r in REPORTS:
            for key, label in (("actors", "ThreatActor"), ("campaigns", "Campaign"),
                               ("malware", "Malware")):
                s.run(f"""UNWIND $ids AS eid MATCH (x:{label} {{id:eid}}), (rep:Report {{id:$rid}})
                          MERGE (x)-[:MENTIONED_IN]->(rep)""", ids=r.get(key, []), rid=r["id"])
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    return {"nodes": nodes, "relationships": rels}


def seed_mongo() -> dict:
    col = stores.mongo_db().reports
    col.delete_many({})
    now = int(time.time())
    for r in REPORTS:
        doc = {k: v for k, v in r.items() if k != "id"}
        doc["_id"] = r["id"]
        doc["ingested_at"] = now
        doc["ingested_by"] = "seed"
        col.insert_one(doc)
    return {"reports": len(REPORTS)}


def seed_redis() -> dict:
    r = stores.redis_client
    for k in r.scan_iter("ioc:*"):
        r.delete(k)
    for ind in INDICATORS:
        blocklist.publish(ind["type"], ind["value"], ind["ttl"], ind["severity"],
                          ind.get("actor"), ind.get("campaign"), published_by="seed")
    return {"iocs": len(INDICATORS)}


if __name__ == "__main__":
    import json

    stores.connect()
    stores.wait_for_stores(60)
    stores.ensure_schema()
    print(json.dumps(seed_all(force=True), indent=2))
