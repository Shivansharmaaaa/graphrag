# Showing the four NoSQL databases live

This is how to show the examiner the databases themselves — running servers with real data, queried in their own tools — rather than the application or exported files. Allow about 5 minutes. Every query below was run against the demo data.

## 1. Start everything

```bash
docker compose up -d     # the four databases (already running if the app is up)
make dbui                # read-only web consoles for MongoDB and Redis
```

Then open four browser tabs:

| Database | Model | Console | Sign in |
|---|---|---|---|
| **Neo4j 5** | graph | http://localhost:7474 (Neo4j Browser, built in) | user `neo4j`, password `ctiplatform` |
| **MongoDB 7** | document | http://localhost:8081 (mongo-express) | none (read-only, this machine only) |
| **Redis 7** | key–value | http://localhost:8082 (Redis Commander) | none (read-only, this machine only) |
| **Qdrant 1.13** | vector | http://localhost:6333/dashboard (built in) | none |

To show they are real database servers, run `docker ps` in a terminal: four containers from the official `neo4j`, `mongo`, `redis` and `qdrant/qdrant` images, each listening on its standard port, with data in Docker volumes (`docker volume ls`). The JSON files in `database_dumps/` are only backups of these databases.

MongoDB Compass is also installed on this Mac: connect it to `mongodb://localhost:27017` for MongoDB's own desktop tool.

---

## 2. Neo4j — the threat graph

In Neo4j Browser, type each query in the top bar and press **Run** (or Ctrl/⌘ + Enter).

```cypher
CALL db.schema.visualization()
```
The live schema: 8 node labels and 16 relationship patterns. *"This is a property graph, not tables: relationships are stored data."*

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC
```
Indicator 15, Malware 13, Infrastructure 13, Report 12, Technique 10, ThreatActor 8, Campaign 8, Victim 8 — 87 nodes.

```cypher
MATCH p=(a:ThreatActor {id:'apt28'})-[:USES_INFRA]->(i:Infrastructure)<-[:USES_INFRA]-(b:ThreatActor)
OPTIONAL MATCH h=(i)-[:HOSTS]->(:Malware)
RETURN p, h
```
APT28 and Sandworm share the server 185.86.77.12, which hosted X-Agent and NotPetya. *"This multi-hop question is one pattern match; in SQL it would be several self-joins."*

```cypher
MATCH p=(m:Malware {id:'mimikatz'})<-[:USES]-(:ThreatActor) RETURN p
```
Five actors use Mimikatz — a hub node, which is why the system treats it as weak evidence of attribution.

```cypher
SHOW CONSTRAINTS
```
Uniqueness constraints on every label's id (and on Indicator `(type, value)`), which back the index seeks measured in the report.

Terminal alternative: `docker exec -it cti-neo4j cypher-shell -u neo4j -p ctiplatform`

---

## 3. MongoDB — the reports

In mongo-express: **cti** database → six collections (`reports`, `users`, `audit_log`, `ingest_jobs`, `stix_bundles`, `meta`).

- Open **reports** → **rpt-002**: core fields plus a nested `build_pipeline` object.
- Go back and open **rpt-004**: no `iocs` list, but `ics_protocols` and `outage_minutes` instead.
  *"Same collection, different shapes, no schema migration — that is why reports live in a document store."*
- Open **users**: passwords are stored as PBKDF2 hashes, never plain text.

Terminal alternative, with queries and indexes:

```bash
docker exec -it cti-mongo mongosh cti
```
```javascript
db.reports.find({ actors: "apt28" }, { title: 1, tlp: 1 })      // rpt-001 (AMBER), rpt-010 (WHITE)
db.reports.getIndexes().map(i => i.name)                         // _id_, actors_1, date_-1, tlp_1, iocs_1
db.reports.find({ iocs: "avsvmcloud.com" }).explain("executionStats").executionStats.totalDocsExamined   // 1: uses the index
```

---

## 4. Redis — the live IOC blocklist

In Redis Commander, expand **ioc → ip** and click **185.86.77.12**:

- the value is the blocklist entry (actor apt28, campaign dnc-2016, severity high);
- **TTL** is the number of seconds until Redis deletes the key by itself — click the key again and it has gone down.
  *"Expiry is a database feature: the blocklist cleans itself, with O(1) lookups."*
- `ioc → index` is a sorted set of every key scored by its expiry time, used for the "hot set" view.

Terminal alternative, for typing Redis commands:

```bash
docker exec -it cti-redis redis-cli
```
```
KEYS ioc:*                              # 10 live indicators plus ioc:index
GET  ioc:ip:185.86.77.12                # the JSON entry
TTL  ioc:ip:185.86.77.12                # seconds left, counting down
ZRANGE ioc:index 0 -1 WITHSCORES        # every key with its expiry time
```

To show a key expiring on the spot, run `make seed` first: three demo indicators get 90, 120 and 300-second TTLs (for example `TTL ioc:domain:b7c3e1a90f44d21c99aa.onion`), reach `-2` (gone), and the graph in Neo4j still has their `Indicator` nodes.

---

## 5. Qdrant — the vector index

In the Qdrant dashboard: **Collections** → **threat_chunks**: 25 points, 64-dimensional vectors, cosine distance.

- **Points** tab: each point is a passage of a report, with its payload (`report_id`, `title`, `tlp`, `actors`, `date_ts`, `text`).
- **Info** tab: the HNSW index settings (m = 16, ef_construct = 100) and payload indexes on `report_id`, `tlp`, `actors`, `date_ts`.
- **Visualize** tab → **RUN**: the 25 vectors projected onto a plane; passages from the same report sit close together.
  *"Search here is by meaning, not keywords, and the TLP payload filter is applied inside the search."*

Terminal alternative: `curl -s localhost:6333/collections/threat_chunks | python3 -m json.tool`

---

## 6. Tie it together

Open the CTI console (http://localhost:5173), ask *"Which threat actors share command-and-control infrastructure, and what malware was hosted there?"* and point out that the answer cites a Neo4j edge you just saw, a Qdrant passage, a MongoDB report and a Redis TTL — one question, four databases.

The consoles are read-only: they cannot change or delete data during the demo. `docker compose --profile dbui stop` closes them.
