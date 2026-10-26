"""Connections to the four NoSQL engines + the local LLM.

Always access clients through the module (``from app import stores; stores.redis_client``)
— never ``from app.stores import redis_client`` — because they are created in ``connect()``.
The Neo4j, MongoDB and Redis clients are thread-safe pools. The Qdrant REST client is not
safe to share between FastAPI's worker threads (a socket can be closed under another
thread's read), so ``stores.qdrant_client`` resolves to one client per thread.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from urllib.parse import urlparse

import httpx
from neo4j import GraphDatabase
from pymongo import ASCENDING, DESCENDING, MongoClient
from qdrant_client import QdrantClient
from redis import Redis

from app.config import DATA_DIR, settings

neo4j_driver = None
mongo_client: MongoClient | None = None
redis_client: Redis | None = None
qdrant_mode = "server"
_qdrant_shared: QdrantClient | None = None  # embedded mode: one client owns the storage dir
_qdrant_local = threading.local()
_qdrant_clients: list[QdrantClient] = []
_qdrant_gen = 0  # bumped by connect()/close() so threads drop clients from a previous connect
_qdrant_lock = threading.Lock()


def _new_qdrant() -> QdrantClient:
    if settings.qdrant_url:  # hosted cluster: HTTPS + API key
        # Qdrant Cloud runs newer servers (1.20) than the pinned client; the REST calls used here
        # (collections, upsert, filtered query, scroll, payload indexes) are stable across them
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=10,
                            check_compatibility=False)
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=5)


def host_of(store: str) -> str:
    """Where a store lives (hostname only, never credentials) — shown on the health page."""
    url = {"neo4j": settings.neo4j_uri, "mongodb": settings.mongo_uri, "redis": settings.redis_url,
           "qdrant": settings.qdrant_url or f"http://{settings.qdrant_host}:{settings.qdrant_port}"}[store]
    return urlparse(url).hostname or url


def _remote(store: str) -> bool:
    return host_of(store) not in ("localhost", "127.0.0.1", "neo4j", "mongo", "redis", "qdrant")


def _qdrant() -> QdrantClient | None:
    if _qdrant_shared is not None or not _qdrant_clients:
        return _qdrant_shared
    gen, client = getattr(_qdrant_local, "client", (None, None))
    if gen != _qdrant_gen:
        client = _new_qdrant()
        _qdrant_local.client = (_qdrant_gen, client)
        with _qdrant_lock:
            _qdrant_clients.append(client)
    return client


def __getattr__(name: str):  # PEP 562: `stores.qdrant_client` is per thread
    if name == "qdrant_client":
        return _qdrant()
    raise AttributeError(name)


def connect() -> None:
    global neo4j_driver, mongo_client, redis_client, qdrant_mode, _qdrant_shared, _qdrant_gen
    neo4j_driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=5,
        # "constraint already exists" etc. arrive as INFORMATION notices on every start
        notifications_min_severity="WARNING",
    )
    # hosted databases sit across the internet: allow for the round trip and the TLS handshake
    mongo_client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000 if _remote("mongodb") else 4000)
    wait = 5 if _remote("redis") else 2
    redis_client = Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=wait, socket_connect_timeout=wait
    )
    _qdrant_gen += 1
    try:
        probe = _new_qdrant()
        probe.get_collections()
        qdrant_mode, _qdrant_shared = "server", None
        _qdrant_local.client = (_qdrant_gen, probe)
        with _qdrant_lock:
            _qdrant_clients.append(probe)
    except Exception:
        # Fallback so a laptop without the Qdrant container can still run the platform.
        qdrant_mode, _qdrant_shared = "embedded", QdrantClient(path=str(DATA_DIR / "qdrant"))


def close() -> None:
    global neo4j_driver, mongo_client, redis_client, _qdrant_shared, _qdrant_gen
    with _qdrant_lock:
        clients, _qdrant_clients[:] = list(_qdrant_clients), []
    for c in (neo4j_driver, mongo_client, redis_client, _qdrant_shared, *clients):
        try:
            if c:
                c.close()
        except Exception:
            pass
    neo4j_driver = mongo_client = redis_client = _qdrant_shared = None
    _qdrant_gen += 1


def ensure_schema() -> None:
    """Versioned schema objects (NFR5): graph constraints + document indexes."""
    stmts = [
        f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        for label in ("ThreatActor", "Campaign", "Malware", "Infrastructure",
                      "Technique", "Victim", "Report")
    ] + [
        "CREATE CONSTRAINT indicator_key IF NOT EXISTS FOR (n:Indicator) REQUIRE (n.type, n.value) IS UNIQUE",
        "CREATE INDEX infra_value IF NOT EXISTS FOR (n:Infrastructure) ON (n.value)",
        "CREATE INDEX indicator_value IF NOT EXISTS FOR (n:Indicator) ON (n.value)",
        "CREATE INDEX indicator_id IF NOT EXISTS FOR (n:Indicator) ON (n.id)",
    ]
    with neo4j_session() as s:
        for stmt in stmts:
            try:
                s.run(stmt).consume()
            except Exception as e:  # e.g. an edition-specific constraint — log, don't block startup
                print(f"[schema] skipped: {stmt[:60]}… ({str(e)[:80]})")
    db = mongo_db()
    # Section 8.2 — indexes: _id (implicit), actors, date, tlp. No unique constraint on nested keys.
    db.reports.create_index([("actors", ASCENDING)])
    db.reports.create_index([("date", DESCENDING)])
    db.reports.create_index([("tlp", ASCENDING)])
    db.reports.create_index([("iocs", ASCENDING)])
    db.audit_log.create_index([("ts", DESCENDING)])
    db.ingest_jobs.create_index([("created_at", DESCENDING)])
    db.users.create_index([("username", ASCENDING)], unique=True)
    db.meta.update_one({"_id": "schema"}, {"$set": {"version": 2}}, upsert=True)


def wait_for_stores(timeout: int = 90) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = health()
        if all(v.get("ok") for k, v in last.items() if k != "llm"):
            return last
        time.sleep(2)
    return last


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 2)


def health() -> dict:
    """FR9 — liveness of every store and the LLM, with round-trip latency."""
    out = {k: {"ok": False, "detail": "", "latency_ms": None}
           for k in ("neo4j", "mongodb", "redis", "qdrant", "llm")}
    try:
        t0 = time.perf_counter()
        with neo4j_driver.session() as s:
            n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        out["neo4j"] = {"ok": True, "detail": f"{n} nodes", "latency_ms": _ms(t0)}
    except Exception as e:
        out["neo4j"]["detail"] = str(e).split("\n")[0][:180]
    try:
        t0 = time.perf_counter()
        mongo_client.admin.command("ping")
        n = mongo_client[settings.mongo_db]["reports"].estimated_document_count()
        out["mongodb"] = {"ok": True, "detail": f"{n} reports", "latency_ms": _ms(t0)}
    except Exception as e:
        out["mongodb"]["detail"] = str(e)[:180]
    try:
        t0 = time.perf_counter()
        pong = redis_client.ping()
        lat = _ms(t0)
        n = redis_client.zcount("ioc:index", int(time.time()), "+inf")
        out["redis"] = {"ok": bool(pong), "detail": f"{n} live IOCs", "latency_ms": lat}
    except Exception as e:
        out["redis"]["detail"] = str(e)[:180]
    try:
        t0 = time.perf_counter()
        names = [c.name for c in _qdrant().get_collections().collections]
        detail = f"{qdrant_mode}: {', '.join(names) or 'empty'}"
        if settings.qdrant_collection in names:
            cnt = _qdrant().count(settings.qdrant_collection).count
            detail += f" ({cnt} chunks)"
        out["qdrant"] = {"ok": True, "detail": detail, "latency_ms": _ms(t0)}
    except Exception as e:
        out["qdrant"]["detail"] = str(e)[:180]
    try:
        t0 = time.perf_counter()
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=1.5)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        # exact tag: "llama3.2:3b" must not be satisfied by "llama3.2:1b"; an untagged name means :latest
        want = settings.ollama_model if ":" in settings.ollama_model else f"{settings.ollama_model}:latest"
        has = want in models
        out["llm"] = {
            "ok": r.status_code == 200 and has,
            "detail": (f"ollama · {settings.ollama_model}" if has
                       else f"ollama up, model '{settings.ollama_model}' not pulled"),
            "latency_ms": _ms(t0),
        }
    except Exception:
        out["llm"]["detail"] = f"ollama unreachable at {settings.ollama_url} (retrieve-only mode)"
    for store in ("neo4j", "mongodb", "redis", "qdrant"):
        out[store]["host"] = host_of(store)
        if out[store]["ok"]:
            out[store]["detail"] += f" · {out[store]['host']}"
    return out


@contextmanager
def neo4j_session():
    session = neo4j_driver.session()
    try:
        yield session
    finally:
        session.close()


def mongo_db():
    return mongo_client[settings.mongo_db]
