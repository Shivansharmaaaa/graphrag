# Hosting the four databases on their official cloud services

The platform can run on each database vendor's own hosted service instead of local Docker containers. All four have free tiers that need no credit card at the time of writing:

| Store | Hosted service | Free tier | Sign up |
|---|---|---|---|
| Neo4j (graph) | **Neo4j AuraDB Free** | 1 instance, 200k nodes | https://console.neo4j.io |
| MongoDB (document) | **MongoDB Atlas M0** | 512 MB cluster | https://www.mongodb.com/cloud/atlas/register |
| Redis (key–value) | **Redis Cloud** | 30 MB database | https://redis.io/try-free/ |
| Qdrant (vector) | **Qdrant Cloud** | 1 GB cluster | https://cloud.qdrant.io |

The application (API, console, local LLM) keeps running on your computer and connects to the hosted databases over the internet. The project needs well under 1% of each free quota.

Credentials go into `.env.cloud`, which git ignores. Never paste them into `.env.example`, the README or a commit.

---

## 1. Create the four databases

Where a region is offered, pick the one nearest to you (for example Mumbai or Singapore), so queries stay fast.

### Neo4j AuraDB Free
1. Sign in at https://console.neo4j.io and choose **Create instance → AuraDB Free**.
2. **Download the credentials file when it is offered** — the password is shown only once.
3. Wait until the instance shows **Running**.
4. From the file: `NEO4J_URI` (starts with `neo4j+s://`), `NEO4J_USERNAME` (usually `neo4j`) and `NEO4J_PASSWORD`.

### MongoDB Atlas (M0)
1. Register, then **Create** a cluster and choose the **free** (M0) option.
2. **Database Access** → add a database user with a username and password (not your Atlas login).
3. **Network Access** → **Add IP address** → *Add current IP address*. If you will demonstrate from another network (college Wi-Fi), add that IP too, or temporarily allow `0.0.0.0/0` and remove it after the demo.
4. **Connect → Drivers → Python** → copy the `mongodb+srv://…` connection string and replace `<db_password>` with the user's password.

### Redis Cloud
1. Sign up and create a **free** database (30 MB).
2. Open the database: copy the **public endpoint** (`host:port`) and the **default user's password** (Security section, or the Connect dialog).
3. The connection URL is `redis://default:<password>@<host>:<port>/0`.

### Qdrant Cloud
1. Sign up and **Create** a **free** cluster.
2. Copy the cluster **URL** (ends in `:6333`).
3. Open the cluster's **API Keys** tab, create a key and copy it — it is shown only once.

---

## 2. Connect the platform

```bash
cp .env.cloud.example .env.cloud
```

Fill in `.env.cloud` with the values from step 1:

```
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=…
MONGO_URI=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGO_DB=cti
REDIS_URL=redis://default:<password>@redis-12345.c000.region.cloud.redislabs.com:12345/0
QDRANT_URL=https://xxxxxxxx-xxxx.region.cloud.qdrant.io:6333
QDRANT_API_KEY=…
```

Check all four connections (read-only, prints each server's hostname and version):

```bash
make cloud-check
```

Every line should say `OK … hosted`. Each failure prints a hint; the usual causes are an IP missing from Atlas **Network Access**, a paused AuraDB instance, or a mistyped password.

## 3. Load the data

```bash
make cloud-seed
```

This creates the schema (constraints and indexes) and loads the corpus into all four hosted databases: 87 graph nodes and 162 relationships, 12 reports, 25 vectors and 15 blocklist entries. It replaces whatever those databases contain, and takes about a minute over the internet.

## 4. Run the console against the hosted databases

```bash
docker compose stop api web     # free ports 8000 and 5173 (the stores keep running locally)
make cloud-api                  # terminal 1: API on :8000, using .env.cloud
make web                        # terminal 2: console on http://localhost:5173
```

**Operations** and the sidebar's store tooltips now show each database's cloud hostname (for example `87 nodes · xxxxxxxx.databases.neo4j.io`). To switch back to the local databases, stop `make cloud-api` and run `docker compose start api web`.

---

## 5. Showing the hosted databases

Each vendor's own web console shows the same data the platform uses:

| Database | Where to click | What to show |
|---|---|---|
| **Neo4j AuraDB** | console.neo4j.io → your instance → **Query** | `CALL db.schema.visualization()`; the APT28 shared-infrastructure query from `review3/DATABASE_TOUR.md`; **Explore** for an interactive graph |
| **MongoDB Atlas** | your cluster → **Browse Collections** (Data Explorer) | database `cti` → `reports` → rpt-002 and rpt-004, with different fields in the same collection; the **Indexes** tab |
| **Redis Cloud** | your database → **Redis Insight** (opens in the browser) | **Browser** → keys `ioc:*` → a key's value and its TTL counting down |
| **Qdrant Cloud** | your cluster → **Dashboard** | Collections → `threat_chunks`: 25 points, 64-dimensional, cosine; Points, Info and Visualize |

The queries in `review3/DATABASE_TOUR.md` work unchanged in these consoles.

## 6. Before a demo

- Free tiers pause or remove idle databases (an AuraDB Free instance pauses after a few days without use). The day before, open each console, resume anything paused, and run `make cloud-check`.
- If anything was removed, run `make cloud-seed` again. It also restores the short-lived blocklist entries used for the expiry demonstration.
- If you are demonstrating on a different network, add its IP in Atlas **Network Access**.
