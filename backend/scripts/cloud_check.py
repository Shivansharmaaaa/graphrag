"""Check the hosted databases configured in .env.cloud. Read-only: nothing is written.

    make cloud-check
"""
from __future__ import annotations

import sys

import httpx

from app import stores
from app.config import settings

HINTS = {
    "neo4j": "AuraDB: check NEO4J_URI (neo4j+s://…) and the password from the credentials file; "
             "a Free instance pauses after a few idle days — resume it in console.neo4j.io",
    "mongodb": "Atlas: add this computer's IP under Network Access, and check the user and password "
               "inside MONGO_URI (Database Access)",
    "redis": "Redis Cloud: REDIS_URL must be redis://default:<password>@<public endpoint>",
    "qdrant": "Qdrant Cloud: QDRANT_URL is the cluster URL ending in :6333, QDRANT_API_KEY a key "
              "created under the cluster's API Keys",
}


def versions() -> dict[str, str]:
    out = {}
    try:
        with stores.neo4j_session() as s:
            r = s.run("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS v, edition LIMIT 1").single()
            out["neo4j"] = f"Neo4j {r['v']} ({r['edition']})"
    except Exception:
        pass
    try:
        out["mongodb"] = f"MongoDB {stores.mongo_client.server_info()['version']}"
    except Exception:
        pass
    try:
        out["redis"] = f"Redis {stores.redis_client.info('server')['redis_version']}"
    except Exception:
        pass
    try:
        base = settings.qdrant_url or f"http://{settings.qdrant_host}:{settings.qdrant_port}"
        headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}
        out["qdrant"] = f"Qdrant {httpx.get(base, headers=headers, timeout=10).json().get('version')}"
    except Exception:
        pass
    return out


def main() -> int:
    stores.connect()
    health = stores.health()
    ver = versions()
    failed = 0
    for store in ("neo4j", "mongodb", "redis", "qdrant"):
        h = health[store]
        where = "hosted" if stores._remote(store) else "LOCAL"
        if where == "LOCAL":
            failed += 1
            print(f"  FAIL  {store:8} still points at {h['host']} — set it in .env.cloud\n        → {HINTS[store]}")
            continue
        if h["ok"]:
            print(f"  OK    {store:8} {where:6} {h['host']}  ·  {ver.get(store, '?')}  ·  {h['detail'].split(' · ')[0]}"
                  f"  ·  {h['latency_ms']} ms")
        else:
            failed += 1
            print(f"  FAIL  {store:8} {where:6} {h['host']}  ·  {h['detail'][:120]}\n        → {HINTS[store]}")
    if stores.qdrant_mode != "server":
        failed += 1
        print("  FAIL  qdrant fell back to the embedded local store — QDRANT_URL / QDRANT_API_KEY not accepted")
    print("\nall four hosted databases reachable" if not failed else f"\n{failed} problem(s) — see the hints above")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
