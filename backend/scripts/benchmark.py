"""Scalability, indexing and load benchmarks (Review-III performance analysis).

The benchmark bulk-loads synthetic data and drops / creates indexes, so it only runs against
the throwaway stack in docker-compose.bench.yml:   make bench
Results go to ../review3/performance/benchmark_results.json (see --out).

Experiments
  scale   the seed corpus cloned 1-200x through the production seed loader; per-store query
          latency, GraphRAG retrieve-only latency and ingest throughput at each size
  load    API throughput and tail latency at 1-64 concurrent clients (largest scale)
  redis   blocklist GET latency and memory from 1k to 500k keys, full-keyspace SCAN for contrast
  mongo   report queries on 200k documents without and with the production indexes
  neo4j   property lookup on 100k nodes without and with a range index
  qdrant  HNSW vs exact k-NN (latency, recall@10), unfiltered and payload-filtered, 10k-100k points
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from qdrant_client import models as qm

from app import (blocklist, data, documents, extract, graph, graphrag, ingest, seed, stores,
                 vectors)
from app.config import BACKEND_DIR, PROJECT_DIR, settings
from app.embeddings import embedder

ANALYST = {"username": "bench", "role": "analyst", "clearance": "AMBER", "display": "bench"}
SHARED_MALWARE = {"mimikatz", "cobalt-strike"}  # commodity tools stay one node with many users
TLPS = ["WHITE", "GREEN", "AMBER", "RED"]
CORPUS_KEYS = ("ACTORS", "CAMPAIGNS", "MALWARE", "TECHNIQUES", "INFRASTRUCTURE", "VICTIMS",
               "INDICATORS", "MALWARE_HASHES", "RELATIONSHIPS", "VICTIM_RELS", "REPORTS")


# ================================================================== helpers
def stats(ms: list[float]) -> dict:
    v = sorted(ms)

    def q(p):
        return round(v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))], 3)
    return {"n": len(v), "mean": round(statistics.fmean(v), 3), "p50": q(50), "p95": q(95),
            "p99": q(99)}


def bench(fn, n: int, warmup: int = 3) -> dict:
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return stats(out)


def shuffled_cycle(xs, rng: random.Random):
    xs = list(xs)
    rng.shuffle(xs)
    return itertools.cycle(xs)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ip_of(i: int) -> str:
    return f"10.{i >> 16 & 255}.{i >> 8 & 255}.{i & 255}"


# ================================================================== scale: synthetic corpus
def scaled_corpus(scale: int) -> dict:
    """Clone the seed corpus `scale` times. Clone 0 is the original, so the Appendix-A questions
    still have their gold paths; clones get suffixed ids, fresh infrastructure values and one
    cross-clone USES_INFRA edge per actor. ATT&CK techniques and commodity tools are shared."""
    rng = random.Random(scale)
    out = {k: list(getattr(data, k)) for k in CORPUS_KEYS}
    infra_by_clone = [[i["id"] for i in data.INFRASTRUCTURE]]
    n_ip = 0
    for k in range(1, scale):
        sfx, ids, values = f"-c{k}", {}, {}

        def cid(x):
            return ids.get(x, x)

        def cval(v):
            nonlocal n_ip
            if v not in values:
                if v.replace(".", "").isdigit():
                    n_ip += 1
                    values[v] = f"198.{18 + (n_ip >> 16 & 1)}.{n_ip >> 8 & 255}.{n_ip & 255}"
                elif all(c in "0123456789abcdef" for c in v) and len(v) in (32, 40, 64):
                    values[v] = hashlib.md5(f"{v}{k}".encode()).hexdigest()
                else:
                    values[v] = f"c{k}-{v}"
            return values[v]

        for key, label in (("ACTORS", "ThreatActor"), ("CAMPAIGNS", "Campaign"),
                           ("MALWARE", "Malware"), ("VICTIMS", "Victim")):
            for row in getattr(data, key):
                if key == "MALWARE" and row["id"] in SHARED_MALWARE:
                    continue
                ids[row["id"]] = row["id"] + sfx
                clone = {**row, "id": row["id"] + sfx, "name": f"{row['name']} #{k}"}
                if key == "ACTORS":
                    clone["aliases"] = []
                out[key].append(clone)
        for row in data.INFRASTRUCTURE:
            ids[row["id"]] = row["id"] + sfx
            out["INFRASTRUCTURE"].append({**row, "id": row["id"] + sfx, "value": cval(row["value"])})
        infra_by_clone.append([row["id"] + sfx for row in data.INFRASTRUCTURE])
        out["MALWARE_HASHES"] += [(cid(m), cval(h)) for m, h in data.MALWARE_HASHES]
        out["INDICATORS"] += [{**i, "value": cval(i["value"]), "actor": cid(i.get("actor")),
                               "campaign": cid(i.get("campaign")), "ttl": max(i["ttl"], 86400)}
                              for i in data.INDICATORS]
        out["RELATIONSHIPS"] += [(la, cid(a), rel, lb, cid(b)) for la, a, rel, lb, b in data.RELATIONSHIPS]
        out["VICTIM_RELS"] += [(la, cid(a), rel, lb, cid(b)) for la, a, rel, lb, b in data.VICTIM_RELS]
        out["RELATIONSHIPS"] += [("ThreatActor", a["id"] + sfx, "USES_INFRA", "Infrastructure",
                                  rng.choice(infra_by_clone[rng.randrange(k)])) for a in data.ACTORS]
        out["REPORTS"] += [{**r, "id": r["id"] + sfx, "title": f"{r['title']} #{k}",
                            "actors": [cid(x) for x in r.get("actors", [])],
                            "campaigns": [cid(x) for x in r.get("campaigns", [])],
                            "malware": [cid(x) for x in r.get("malware", [])],
                            "iocs": [cval(v) for v in r.get("iocs", [])]} for r in data.REPORTS]
    return out


def load_corpus(corpus: dict) -> dict:
    """Load through the production seed loader (same Cypher, inserts and SET EX)."""
    for k, v in corpus.items():
        setattr(seed, k, v)
    t = {}
    t0 = time.perf_counter()
    graph_stats = seed.seed_neo4j()
    t["neo4j_s"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    seed.seed_mongo()
    t["mongodb_s"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    vec = vectors.rebuild_all(documents.all_reports_raw())
    t["qdrant_s"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    seed.seed_redis()
    t["redis_s"] = round(time.perf_counter() - t0, 2)
    extract.invalidate_gazetteer()
    return {"load_seconds": t, "nodes": graph_stats["nodes"],
            "relationships": graph_stats["relationships"], "reports": len(corpus["REPORTS"]),
            "chunks": vec["points"], "iocs": len(corpus["INDICATORS"])}


def measure_scale(corpus: dict, rng: random.Random) -> dict:
    actors = shuffled_cycle([a["id"] for a in corpus["ACTORS"]], rng)
    reports = [r["id"] for r in corpus["REPORTS"]]
    rep_it = shuffled_cycle(reports, rng)
    iocs = shuffled_cycle([(i["type"], i["value"]) for i in corpus["INDICATORS"]], rng)
    questions = itertools.cycle(data.DEMO_QUERIES)
    out: dict = {"neo4j": {}}
    for h in (1, 2, 3):
        out["neo4j"][f"neighbourhood_{h}hop"] = bench(lambda: graph.neighbourhood(next(actors), h), 30)
    out["neo4j"]["apt28_2hop_edges"] = len(graph.neighbourhood("apt28", 2)["edges"])
    out["neo4j"]["shared_infrastructure"] = bench(lambda: graph.shared_infrastructure(next(actors)), 30)
    out["neo4j"]["shortest_path"] = bench(lambda: graph.shortest_path(next(actors), next(actors), 4), 30)
    out["mongodb"] = {
        "list_by_actor": bench(lambda: documents.list_reports(ANALYST, actor=next(actors)), 50),
        "get_by_id": bench(lambda: documents.get_report(next(rep_it), ANALYST), 200),
        "hydrate_10": bench(lambda: documents.hydrate(rng.sample(reports, 10), ANALYST), 50),
    }
    out["qdrant"] = {"knn_k6_tlp_filter": bench(lambda: vectors.search(next(questions), ANALYST, k=6), 60)}
    out["redis"] = {"blocklist_get": bench(lambda: blocklist.lookup(*next(iocs)), 1000)}

    totals, edges, docs = [], [], []
    channels: dict[str, list[float]] = {c: [] for c in ("linking", "qdrant", "neo4j", "mongodb", "redis")}
    for q in data.DEMO_QUERIES:  # warm-up: Cypher plan compilation on first use
        graphrag.ask(q, ANALYST, max_hops=2, use_llm=False)
    for _ in range(3):
        for q in data.DEMO_QUERIES:
            r = graphrag.ask(q, ANALYST, max_hops=2, use_llm=False)
            totals.append(r["latency_ms"]["total"])
            for c in channels:
                channels[c].append(r["latency_ms"].get(c, 0.0))
            edges.append(len(r["evidence"]["graph"]["edges"]))
            docs.append(len(r["evidence"]["documents"]))
    out["graphrag_retrieve_only"] = {"total": stats(totals),
                                     "channels": {c: stats(v) for c, v in channels.items()},
                                     "max_evidence_edges": max(edges), "max_documents": max(docs)}

    per_report, steps = [], {s: [] for s in ingest.STEPS}
    for i in range(20):
        body = (f"APT28 reused Mimikatz and X-Agent against foreign ministries. The implant beaconed "
                f"to 192.0.2.{i + 1} and bench-{len(reports)}-{i}[.]example during the campaign.")
        t0 = time.perf_counter()
        plan = ingest.plan_from_text(f"Benchmark ingest {len(reports)}-{i}", body, tlp="GREEN")
        job = ingest.ingest("report", plan, "bench", {"publish_iocs": True, "ttl": 3600})
        per_report.append((time.perf_counter() - t0) * 1000)
        for s in ingest.STEPS:
            steps[s].append(job["steps"][s]["ms"])
    out["ingest"] = {"per_report_ms": stats(per_report),
                     "reports_per_s": round(1000 / statistics.fmean(per_report), 1),
                     "steps_ms": {s: stats(v) for s, v in steps.items()}}
    return out


def scale_experiment(scales: list[int]) -> dict:
    rows = []
    for s in scales:
        log(f"scale x{s}: loading")
        corpus = scaled_corpus(s)
        row = {"scale": s, **load_corpus(corpus)}
        log(f"scale x{s}: {row['nodes']} nodes, {row['reports']} reports, {row['chunks']} chunks — measuring")
        row.update(measure_scale(corpus, random.Random(s)))
        rows.append(row)
    return {"rows": rows}


# ================================================================== load: concurrent API clients
async def _drive(base: str, method: str, url: str, n: int, c: int, **kw) -> dict:
    sem, lat = asyncio.Semaphore(c), []
    async with httpx.AsyncClient(base_url=base, timeout=120,
                                 limits=httpx.Limits(max_connections=c)) as client:
        async def one():
            async with sem:
                t0 = time.perf_counter()
                r = await client.request(method, url, **kw)
                r.raise_for_status()
                lat.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        await asyncio.gather(*[one() for _ in range(n)])
        wall = time.perf_counter() - t0
    return {"concurrency": c, "requests": n, "throughput_rps": round(n / wall, 1), **stats(lat)}


def load_experiment(levels=(1, 4, 16, 64), port: int = 8099) -> dict:
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port),
                             "--log-level", "warning"], cwd=BACKEND_DIR, env=os.environ.copy())
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                if httpx.get(f"{base}/api/health", timeout=2).json()["startup"]["ok"]:
                    break
            except Exception:
                pass
            time.sleep(1)
        tok = httpx.post(f"{base}/api/auth/login",
                         json={"username": "analyst", "password": "analyst123"}).json()["token"]
        user_h = {"Authorization": f"Bearer {tok}"}
        endpoints = {
            "enforce_check": ("GET", "/api/enforce/check", 2000,
                              {"params": {"type": "ip", "value": "185.86.77.12"},
                               "headers": {"X-API-Key": settings.consumer_api_key}}),
            "graph_shared_infrastructure": ("GET", "/api/graph/shared-infrastructure", 400,
                                            {"params": {"actor": "apt28"}, "headers": user_h}),
            "graphrag_retrieve_only": ("POST", "/api/graphrag/ask", 96,
                                       {"json": {"question": data.DEMO_QUERIES[0], "use_llm": False},
                                        "headers": user_h}),
        }
        out = {}
        for name, (method, url, n, kw) in endpoints.items():
            out[name] = []
            for c in levels:
                log(f"load {name} c={c}")
                out[name].append(asyncio.run(_drive(base, method, url, n, c, **kw)))
        return out
    finally:
        proc.terminate()
        proc.wait(timeout=20)


# ================================================================== redis: key-count scaling
def redis_experiment(sizes=(1_000, 10_000, 100_000, 500_000)) -> dict:
    r = stores.redis_client
    r.flushdb()
    now, loaded, rng, rows = int(time.time()), 0, random.Random(5), []
    payload = json.dumps({"type": "ip", "actor": "apt28", "campaign": "dnc-2016", "severity": "high",
                          "ttl": 86400, "published_by": "bench", "published_at": now, "source": None})
    for n in sizes:
        log(f"redis {n} keys")
        t0 = time.perf_counter()
        pipe = r.pipeline(transaction=False)
        for i in range(loaded, n):
            k = f"ioc:ip:{ip_of(i)}"
            pipe.set(k, payload, ex=86400)
            pipe.zadd(blocklist.INDEX, {k: now + 86400})
            if i % 5000 == 4999:
                pipe.execute()
        pipe.execute()
        load_s = time.perf_counter() - t0
        added, loaded = n - loaded, n
        hits = itertools.cycle([ip_of(rng.randrange(n)) for _ in range(1000)])
        t0 = time.perf_counter()
        scanned = sum(1 for _ in r.scan_iter("ioc:ip:*", count=1000))
        scan_ms = (time.perf_counter() - t0) * 1000
        rows.append({
            "keys": n, "load_keys_per_s": round(added / load_s),
            "get_hit": bench(lambda: blocklist.lookup("ip", next(hits)), 2000),
            "get_miss": bench(lambda: blocklist.lookup("ip", f"203.0.113.{rng.randrange(1, 255)}"), 500),
            "zcount_live": bench(lambda: r.zcount(blocklist.INDEX, now, "+inf"), 200),
            "full_scan_ms": round(scan_ms, 1), "scanned": scanned,
            "used_memory_mb": round(r.info("memory")["used_memory"] / 2**20, 1),
        })
    return {"rows": rows}


# ================================================================== mongodb: index ablation
def _plan_stages(plan: dict) -> list[str]:
    stages = [plan.get("stage")]
    for key in ("inputStage", "outerStage", "innerStage"):
        if key in plan:
            stages += _plan_stages(plan[key])
    for sub in plan.get("inputStages", []):
        stages += _plan_stages(sub)
    return [s for s in stages if s]


def mongo_experiment(n: int = 200_000) -> dict:
    db = stores.mongo_db()
    col = db.bench_reports
    col.drop()
    rng = random.Random(11)
    actors = [f"actor-{i}" for i in range(800)]
    log(f"mongo inserting {n} docs")
    t0, batch = time.perf_counter(), []
    for i in range(n):
        batch.append({"_id": f"b-{i}", "title": f"Synthetic report {i}", "source": "bench",
                      "actors": rng.sample(actors, rng.randint(1, 3)),
                      "tlp": rng.choices(TLPS, weights=[3, 4, 2, 1])[0],
                      "date": f"{rng.randint(2010, 2026)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                      "iocs": [f"ioc-{rng.randrange(400_000)}" for _ in range(rng.randint(2, 5))]})
        if len(batch) == 10_000:
            col.insert_many(batch)
            batch = []
    if batch:
        col.insert_many(batch)
    insert_s = time.perf_counter() - t0
    a_it = shuffled_cycle(actors, rng)
    i_it = itertools.cycle([f"ioc-{rng.randrange(400_000)}" for _ in range(500)])
    queries = {
        "by_actor": lambda: (col.find({"actors": next(a_it)}, {"_id": 1}).limit(100)),
        "by_ioc": lambda: (col.find({"iocs": next(i_it)}, {"_id": 1})),
        "tlp_recent_50": lambda: (col.find({"tlp": {"$in": ["WHITE", "GREEN"]}}, {"_id": 1})
                                  .sort("date", -1).limit(50)),
    }

    def phase(names) -> dict:
        res = {}
        for q in names:
            cur_fn = queries[q]
            ex = cur_fn().explain()
            st = ex["executionStats"]
            res[q] = {"latency": bench(lambda: list(cur_fn()), 30),
                      "docs_examined": st["totalDocsExamined"], "keys_examined": st["totalKeysExamined"],
                      "returned": st["nReturned"], "server_ms": st["executionTimeMillis"],
                      "plan": _plan_stages(ex["queryPlanner"]["winningPlan"])}
        return res

    out = {"documents": n, "insert_docs_per_s": round(n / insert_s)}
    log("mongo: no secondary indexes")
    out["no_index"] = phase(queries)
    t0 = time.perf_counter()
    col.create_index("actors")
    col.create_index("iocs")
    col.create_index([("date", -1)])
    col.create_index("tlp")
    out["index_build_s"] = round(time.perf_counter() - t0, 2)
    log("mongo: production indexes")
    out["production_indexes"] = phase(queries)
    col.create_index([("tlp", 1), ("date", -1)])
    out["compound_tlp_date"] = phase(["tlp_recent_50"])
    cs = db.command("collStats", "bench_reports")
    out["data_mb"] = round(cs["size"] / 2**20, 1)
    out["index_mb"] = {k: round(v / 2**20, 2) for k, v in cs["indexSizes"].items()}
    col.drop()
    return out


# ================================================================== neo4j: index ablation
def _profile(p: dict) -> tuple[int, list[str]]:
    hits, ops = p.get("dbHits", 0), [p.get("operatorType", "").split("@")[0]]
    for ch in p.get("children", []):
        h, o = _profile(ch)
        hits, ops = hits + h, ops + o
    return hits, ops


def neo4j_experiment(n: int = 100_000) -> dict:
    rng = random.Random(13)
    with stores.neo4j_session() as s:
        s.run("DROP INDEX bench_host_value IF EXISTS").consume()
        s.run("MATCH (h:BenchHost) CALL (h) { DETACH DELETE h } IN TRANSACTIONS OF 10000 ROWS").consume()
        log(f"neo4j creating {n} nodes")
        t0 = time.perf_counter()
        s.run("""UNWIND range(0, $n - 1) AS i
                 CALL (i) { CREATE (:BenchHost {id: 'h-' + i,
                        value: '10.' + (i / 65536) + '.' + ((i / 256) % 256) + '.' + (i % 256)}) }
                 IN TRANSACTIONS OF 10000 ROWS""", n=n).consume()
        create_s = time.perf_counter() - t0
        vals = itertools.cycle([ip_of(rng.randrange(n)) for _ in range(500)])

        def lookup():
            s.run("MATCH (h:BenchHost {value: $v}) RETURN h.id", v=next(vals)).consume()

        def phase(reps):
            prof = s.run("PROFILE MATCH (h:BenchHost {value: $v}) RETURN h.id", v=next(vals)).consume().profile
            hits, ops = _profile(prof)
            return {"latency": bench(lookup, reps), "db_hits": hits, "operators": ops}

        out = {"nodes": n, "create_nodes_per_s": round(n / create_s)}
        log("neo4j: label scan")
        out["no_index"] = phase(30)
        t0 = time.perf_counter()
        s.run("CREATE INDEX bench_host_value IF NOT EXISTS FOR (h:BenchHost) ON (h.value)").consume()
        s.run("CALL db.awaitIndexes(300)").consume()
        out["index_build_s"] = round(time.perf_counter() - t0, 2)
        log("neo4j: index seek")
        out["range_index"] = phase(300)
        s.run("DROP INDEX bench_host_value IF EXISTS").consume()
        s.run("MATCH (h:BenchHost) CALL (h) { DETACH DELETE h } IN TRANSACTIONS OF 10000 ROWS").consume()
    return out


# ================================================================== qdrant: HNSW vs exact
def qdrant_experiment(sizes=(10_000, 50_000, 100_000), dim: int = 64) -> dict:
    q, name = stores.qdrant_client, "bench_vectors"
    if q.collection_exists(name):
        q.delete_collection(name)
    q.create_collection(name, vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
                        hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=100),
                        # build HNSW at any size so the comparison is HNSW vs exact, not plain vs exact
                        optimizers_config=qm.OptimizersConfigDiff(indexing_threshold=10))
    q.create_payload_index(name, "tlp", qm.PayloadSchemaType.KEYWORD)
    q.create_payload_index(name, "actor", qm.PayloadSchemaType.KEYWORD)
    gen = np.random.default_rng(7)
    centres = gen.normal(size=(200, dim))

    def sample(m):
        x = centres[gen.integers(200, size=m)] + 0.35 * gen.normal(size=(m, dim))
        return x / np.linalg.norm(x, axis=1, keepdims=True)

    rows, loaded = [], 0
    for n in sizes:
        log(f"qdrant {n} points")
        x = sample(n - loaded)
        pts = [qm.PointStruct(id=loaded + i, vector=x[i].tolist(),
                              payload={"tlp": TLPS[(loaded + i) % 4], "actor": f"actor-{(loaded + i) % 100}"})
               for i in range(len(x))]
        t0 = time.perf_counter()
        q.upload_points(name, points=pts, batch_size=1000, wait=True)
        upload_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 120:  # optimizer builds HNSW segments in the background
            info = q.get_collection(name)
            if info.status == qm.CollectionStatus.GREEN and (info.indexed_vectors_count or 0) >= n * 0.95:
                break
            time.sleep(0.5)
        index_s = time.perf_counter() - t0
        loaded = n
        queries = sample(100)
        flt = qm.Filter(must=[qm.FieldCondition(key="tlp", match=qm.MatchAny(any=["WHITE", "GREEN"]))])
        row = {"points": n, "upload_points_per_s": round(len(x) / upload_s),
               "index_build_s": round(index_s, 2),
               "indexed_vectors": info.indexed_vectors_count, "segments": info.segments_count}
        for label, f in (("unfiltered", None), ("tlp_filter", flt)):
            exact_ids, exact_ms = [], []
            for v in queries:
                t0 = time.perf_counter()
                res = q.query_points(name, query=v.tolist(), limit=10, query_filter=f,
                                     search_params=qm.SearchParams(exact=True)).points
                exact_ms.append((time.perf_counter() - t0) * 1000)
                exact_ids.append({p.id for p in res})
            row[label] = {"exact": stats(exact_ms)}
            for ef in (16, 64, 128):
                ms, rec = [], []
                for v, truth in zip(queries, exact_ids):
                    t0 = time.perf_counter()
                    res = q.query_points(name, query=v.tolist(), limit=10, query_filter=f,
                                         search_params=qm.SearchParams(hnsw_ef=ef)).points
                    ms.append((time.perf_counter() - t0) * 1000)
                    rec.append(len({p.id for p in res} & truth) / 10)
                row[label][f"hnsw_ef{ef}"] = {**stats(ms), "recall_at_10": round(statistics.fmean(rec), 4)}
        rows.append(row)
    q.delete_collection(name)
    return {"dim": dim, "rows": rows}


# ================================================================== entry point
def environment() -> dict:
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ""
    with stores.neo4j_session() as s:
        neo = s.run("CALL dbms.components() YIELD versions RETURN versions[0] AS v").single()["v"]
    return {
        "date": time.strftime("%Y-%m-%d"), "python": platform.python_version(),
        "host": sh(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor(),
        "host_memory_gb": round(int(sh(["sysctl", "-n", "hw.memsize"]) or 0) / 2**30, 1),
        "docker_vm": sh(["docker", "info", "--format", "{{.NCPU}} vCPU, {{.MemTotal}} bytes"]),
        "neo4j": neo, "mongodb": stores.mongo_client.server_info()["version"],
        "redis": stores.redis_client.info("server")["redis_version"],
        "qdrant": httpx.get(f"http://{settings.qdrant_host}:{settings.qdrant_port}/").json().get("version"),
        "embedder": f"{embedder.backend} ({vectors.COLLECTION})",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="scale,load,redis,mongo,neo4j,qdrant")
    ap.add_argument("--scales", default="1,10,50,100,200")
    ap.add_argument("--out", default=str(PROJECT_DIR / "review3" / "performance" / "benchmark_results.json"))
    ap.add_argument("--quick", action="store_true", help="tiny sizes, to check the harness itself")
    args = ap.parse_args()
    quick = args.quick
    if os.environ.get("CTI_BENCH") != "1" or settings.neo4j_uri.endswith(":7687"):
        sys.exit("refusing to run: the benchmark wipes and bulk-loads the stores. Use `make bench`, "
                 "which runs it against the throwaway stack in docker-compose.bench.yml.")
    stores.connect()
    stores.wait_for_stores(120)
    if stores.qdrant_mode != "server":
        sys.exit("Qdrant server not reachable (embedded mode would not be a fair benchmark)")
    stores.ensure_schema()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # merge, so `--only redis` refreshes one experiment without dropping the others
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    results["environment"] = environment()
    experiments = {
        "scale": lambda: scale_experiment([int(s) for s in ("1,2" if quick else args.scales).split(",")]),
        "load": lambda: load_experiment((1, 4) if quick else (1, 4, 16, 64)),
        "redis": lambda: redis_experiment((1_000, 5_000) if quick else (1_000, 10_000, 100_000, 500_000)),
        "mongo": lambda: mongo_experiment(5_000 if quick else 200_000),
        "neo4j": lambda: neo4j_experiment(5_000 if quick else 100_000),
        "qdrant": lambda: qdrant_experiment((2_000, 5_000) if quick else (10_000, 50_000, 100_000)),
    }
    for name in args.only.split(","):
        t0 = time.perf_counter()
        results[name] = experiments[name]()
        results[name]["experiment_s"] = round(time.perf_counter() - t0, 1)
        out_path.write_text(json.dumps(results, indent=2))  # keep partial results if a later one fails
        log(f"{name} done in {results[name]['experiment_s']} s")
    log(f"wrote {out_path}")


if __name__ == "__main__":
    main()
