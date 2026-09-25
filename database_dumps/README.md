# Database dumps

Snapshots taken 2026-09-25 from the running dev stack (seed corpus + demo IOCs).

| Store | File | How it was made | How to restore |
|---|---|---|---|
| MongoDB | `mongodb/cti/*.bson` + `.metadata.json` | `mongodump --uri=mongodb://localhost:27017/cti` | `mongorestore --uri=<uri> --drop database_dumps/mongodb` |
| Neo4j | `neo4j/graph_dump.cypher` | `scripts/export_neo4j.py` (custom Cypher export — no APOC dependency, 87 nodes / 162 relationships) | `cypher-shell -u neo4j -p <password> < database_dumps/neo4j/graph_dump.cypher` |
| Redis | `redis/live_snapshot.json` | `redis-cli --scan` + `GET`/`TTL` per `ioc:*` key | Reference only — IOCs are time-bound by design (FR3/UC4), so restore by re-running the seed loader instead of replaying stale TTLs |
| Qdrant | `qdrant/threat_chunks.snapshot` | Qdrant's native snapshot API (`POST /collections/threat_chunks/snapshots`) | `PUT /collections/threat_chunks/snapshots/recover` with `{"location": "file:///qdrant/snapshots/threat_chunks.snapshot"}` (see `scripts/restore_databases.sh dumps`) |

**Recommended:** `./scripts/restore_databases.sh seed` — rebuilds all four stores deterministically from `backend/app/data.py` (the same path the app takes on first boot). This is faster, always reproducible, and gives Redis IOCs fresh TTLs instead of already-expired ones.

`./scripts/restore_databases.sh dumps` replays the exact snapshots above instead, if you specifically need this point-in-time state.
