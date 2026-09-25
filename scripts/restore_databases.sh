#!/usr/bin/env bash
# Rebuild all four NoSQL stores from database_dumps/.
# Two paths, pick the one you need:
#   ./scripts/restore_databases.sh seed     — fast, deterministic, always works (recommended)
#   ./scripts/restore_databases.sh dumps    — restores the exact snapshots in database_dumps/
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-seed}"

echo "== restoring stores (mode: $MODE) =="

if [ "$MODE" = "seed" ]; then
  # The simplest reproducible path: run the app's own deterministic seed loader,
  # which rebuilds Neo4j, MongoDB, Qdrant and Redis from backend/app/data.py.
  ( cd backend && ../.venv/bin/python3 -m app.seed )
  echo "done — stores rebuilt from backend/app/data.py (the seed corpus)."
  exit 0
fi

if [ "$MODE" = "dumps" ]; then
  # MongoDB
  echo "-- mongodb --"
  mongorestore --uri="${MONGO_URI:-mongodb://localhost:27017}" \
    --drop database_dumps/mongodb

  # Neo4j — replay the Cypher export (idempotent MERGE statements)
  echo "-- neo4j --"
  docker exec -i cti-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-ctiplatform}" \
    < database_dumps/neo4j/graph_dump.cypher

  # Qdrant — recover the collection from its native snapshot
  echo "-- qdrant --"
  docker cp database_dumps/qdrant/threat_chunks.snapshot cti-qdrant:/qdrant/snapshots/threat_chunks.snapshot
  curl -s -X PUT "http://localhost:6333/collections/threat_chunks/snapshots/recover" \
    -H 'Content-Type: application/json' \
    -d '{"location": "file:///qdrant/snapshots/threat_chunks.snapshot"}'

  # Redis — IOC TTLs are inherently time-bound, so the live_snapshot.json is a
  # reference only; re-publish through the app's own seed_redis() for fresh TTLs.
  echo "-- redis (re-seeding fresh TTLs, live_snapshot.json is reference-only) --"
  ( cd backend && ../.venv/bin/python3 -c "from app import stores, seed; stores.connect(); print(seed.seed_redis())" )

  echo "done — stores restored from database_dumps/."
  exit 0
fi

echo "unknown mode: $MODE (use 'seed' or 'dumps')" >&2
exit 1
