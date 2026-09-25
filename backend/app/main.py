"""GraphRAG CTI Platform — TLP-aware API (orchestration layer, Section 7)."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app import (blocklist, documents, graph, graphrag, ingest, integrity, metrics, seed,
                 stores, vectors)
from app.config import settings
from app.data import DEMO_QUERIES
from app.embeddings import embedder
from app.security import (authenticate, consumer_key, create_token, current_user,
                          ensure_default_users, require_role)

log = logging.getLogger("cti")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
STARTUP: dict = {"ok": False, "detail": "starting"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    stores.connect()
    h = stores.wait_for_stores(90)
    try:
        stores.ensure_schema()
        ensure_default_users()
        loaded = embedder.load()
        if settings.auto_seed and not seed.is_seeded():
            log.info("empty stores — loading initial corpus (FR8)")
            log.info("seed: %s", seed.seed_all(force=True))
        elif not loaded or not vectors.collection_exists():
            log.info("embedder/collection missing — rebuilding vector index from MongoDB")
            vectors.rebuild_all(documents.all_reports_raw())
        blocklist.purge_expired_index()
        STARTUP.update(ok=True, detail="ready")
    except Exception as e:  # keep the API up so /api/health can explain what is wrong
        log.exception("startup failed")
        STARTUP.update(ok=False, detail=f"{type(e).__name__}: {e}"[:300], health=h)
    yield
    stores.close()


app = FastAPI(title="GraphRAG CTI Platform", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


def _bad(e: Exception, code: int = 400):
    raise HTTPException(code, str(e))


# ================================================================== auth
class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "invalid credentials")
    return {"token": create_token(user), "user": user}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return user


# ================================================================== health / SLO (FR9)
@app.get("/api/health")
def health():
    h = stores.health()
    return {"startup": STARTUP, "stores": h, "latency": metrics.summary(),
            "read_path_ok": all(h[s]["ok"] for s in ("neo4j", "mongodb", "qdrant")),
            "enforcement_path_ok": h["redis"]["ok"]}


@app.get("/api/meta")
def meta(user: dict = Depends(current_user)):
    return {"demo_queries": DEMO_QUERIES, "graph": graph.stats(),
            "embedder": {"backend": embedder.backend, "dim": embedder.dim},
            "llm_model": settings.ollama_model, "max_hops": settings.max_hops}


# ================================================================== graph (FR2)
@app.get("/api/graph/search")
def graph_search(q: str = "", label: str | None = None, limit: int = Query(20, le=200),
                 user: dict = Depends(current_user)):
    return graph.search(q, limit, label)


@app.get("/api/graph/overview")
def graph_overview(limit: int = 400, include_reports: bool = False,
                   user: dict = Depends(current_user)):
    return graph.overview(limit, include_reports)


@app.get("/api/graph/node/{node_id}")
def graph_node(node_id: str, hops: int = Query(1, ge=1, le=3), user: dict = Depends(current_user)):
    n = graph.get_node(node_id)
    if not n:
        raise HTTPException(404, "node not found")
    return {"node": n, "subgraph": graph.neighbourhood(node_id, hops)}


@app.get("/api/graph/shared-infrastructure")
def q_shared_infra(actor: str | None = None, user: dict = Depends(current_user)):
    return graph.shared_infrastructure(actor)


@app.get("/api/graph/shared-tooling")
def q_shared_tooling(malware: str | None = None, actor: str | None = None,
                     user: dict = Depends(current_user)):
    return graph.shared_tooling(malware, actor)


@app.get("/api/graph/tool-users/{malware_id}")
def q_tool_users(malware_id: str, user: dict = Depends(current_user)):
    return graph.tool_users(malware_id)


@app.get("/api/graph/common-victims")
def q_common_victims(actor: str | None = None, user: dict = Depends(current_user)):
    return graph.common_victims(actor)


@app.get("/api/graph/path")
def q_path(src: str, dst: str, max_len: int = 4, user: dict = Depends(current_user)):
    return graph.shortest_path(src, dst, max_len)


@app.get("/api/graph/indicator/{value}")
def q_indicator_history(value: str, user: dict = Depends(current_user)):
    """UC4: historical HAS_IOC / OBSERVED_AS presence + citing documents, regardless of TTL."""
    return {"graph": graph.indicator_history(value),
            "documents": documents.reports_mentioning_ioc(value, user)}


# ================================================================== documents (FR6, FR11)
@app.get("/api/reports")
def reports(actor: str | None = None, tlp: str | None = None, q: str | None = None,
            user: dict = Depends(current_user)):
    return documents.list_reports(user, actor, tlp, q)


@app.get("/api/reports/{report_id}")
def report(report_id: str, user: dict = Depends(current_user)):
    doc, status = documents.get_report(report_id, user)
    if status == "not_found":
        raise HTTPException(404, "report not found")
    if status == "forbidden":
        return JSONResponse(status_code=403, content={
            "detail": f"TLP:{doc['tlp']} exceeds your clearance TLP:{user['clearance']}",
            "report": doc})
    return doc


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: str, user: dict = Depends(require_role("admin"))):
    return ingest.delete_report(report_id)


# ================================================================== blocklist (FR3, FR12)
class PublishIn(BaseModel):
    type: Literal["ip", "domain", "hash", "url"]
    value: str
    ttl: int = Field(86400, gt=0, le=90 * 86400, description="seconds")
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    actor: str | None = None
    campaign: str | None = None


@app.get("/api/blocklist")
def blocklist_list(user: dict = Depends(current_user)):
    try:
        return blocklist.hot_set()
    except Exception as e:
        _bad(e, 503)


@app.get("/api/blocklist/{ioc_type}/{value:path}")
def blocklist_get(ioc_type: str, value: str, user: dict = Depends(current_user)):
    try:
        return blocklist.lookup(ioc_type, value)
    except ValueError as e:
        _bad(e)
    except Exception as e:
        _bad(e, 503)


@app.post("/api/blocklist")
def blocklist_publish(body: PublishIn, user: dict = Depends(require_role("lead"))):
    try:
        return blocklist.publish(body.type, body.value, body.ttl, body.severity, body.actor,
                                 body.campaign, published_by=user["username"])
    except ValueError as e:
        _bad(e)


@app.delete("/api/blocklist/{ioc_type}/{value:path}")
def blocklist_revoke(ioc_type: str, value: str, user: dict = Depends(require_role("lead"))):
    try:
        return {"revoked": blocklist.revoke(ioc_type, value)}
    except ValueError as e:
        _bad(e)


# ---- enforcement consumers (firewall / EDR / SIEM): Redis only, fail closed (NFR3, NFR8)
@app.get("/api/enforce/check")
def enforce_check(type: str, value: str, _: str = Depends(consumer_key)):
    try:
        r = blocklist.lookup(type, value)
        return {"blocked": r["blocked"], "ttl_remaining": r["ttl_remaining"],
                "severity": r.get("severity")}
    except ValueError as e:
        _bad(e)
    except Exception:
        return JSONResponse(status_code=503, content={
            "blocked": True, "fail_closed": True,
            "detail": "blocklist unavailable — failing closed"})


@app.get("/api/enforce/export")
def enforce_export(format: Literal["json", "txt"] = "json", _: str = Depends(consumer_key)):
    try:
        rows = blocklist.export_hot_set()
    except Exception:
        return JSONResponse(status_code=503, content={"fail_closed": True,
                                                      "detail": "blocklist unavailable"})
    if format == "txt":
        return PlainTextResponse("\n".join(f"{r['type']},{r['value']}" for r in rows))
    return rows


# ================================================================== semantic search (FR4)
class SearchIn(BaseModel):
    query: str = Field(min_length=2)
    k: int = Field(8, ge=1, le=30)
    actors: list[str] | None = None
    tlp: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None


@app.post("/api/search/semantic")
def semantic(body: SearchIn, user: dict = Depends(current_user)):
    return vectors.search(body.query, user, body.k, body.actors, body.tlp, body.date_from,
                          body.date_to, with_map=True)


# ================================================================== GraphRAG (FR5, FR7, FR10)
class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    max_hops: int = Field(2, ge=1, le=3)
    k: int = Field(6, ge=1, le=20)
    use_llm: bool = True


@app.post("/api/graphrag/ask")
def ask(body: AskIn, user: dict = Depends(current_user)):
    return graphrag.ask(body.question, user, body.max_hops, body.k, body.use_llm)


@app.get("/api/audit")
def audit_list(user: dict = Depends(current_user)):
    return graphrag.list_audit(user)


@app.get("/api/audit/{audit_id}")
def audit_get(audit_id: str, user: dict = Depends(current_user)):
    doc = graphrag.get_audit(audit_id, user)
    if not doc:
        raise HTTPException(404, "audit entry not found or not visible to you")
    return doc


@app.post("/api/audit/{audit_id}/replay")
def audit_replay(audit_id: str, user: dict = Depends(current_user)):
    res = graphrag.replay(audit_id, user)
    if not res:
        raise HTTPException(404, "audit entry not found or not visible to you")
    return res


# ================================================================== ingest (FR1, FR8)
class ReportIn(BaseModel):
    title: str = Field(min_length=3)
    body: str = Field(min_length=20)
    source: str = "analyst"
    date: str | None = None
    tlp: Literal["WHITE", "CLEAR", "GREEN", "AMBER", "RED"] = "AMBER"
    confidence: str = "medium"
    actors: list[str] | None = None
    extra: dict | None = Field(None, description="report-specific nested fields")
    publish_iocs: bool = False
    ttl: int = Field(86400, gt=0)


@app.post("/api/ingest/report")
def ingest_report(body: ReportIn, user: dict = Depends(require_role("lead"))):
    try:
        plan = ingest.plan_from_text(body.title, body.body, body.source, body.date, body.tlp,
                                     body.confidence, body.extra, body.actors)
    except ValueError as e:
        _bad(e)
    return ingest.ingest("report", plan, user["username"],
                         {"publish_iocs": body.publish_iocs, "ttl": body.ttl})


class StixIn(BaseModel):
    bundle: dict
    default_tlp: str = "AMBER"
    publish_iocs: bool = False
    ttl: int = Field(86400, gt=0)


@app.post("/api/ingest/stix")
def ingest_stix(body: StixIn, user: dict = Depends(require_role("lead"))):
    try:
        plan = ingest.plan_from_stix(body.bundle, body.default_tlp)
    except (ValueError, KeyError) as e:
        _bad(e)
    return ingest.ingest("stix", plan, user["username"],
                         {"publish_iocs": body.publish_iocs, "ttl": body.ttl})


@app.post("/api/ingest/stix/upload")
async def ingest_stix_file(file: UploadFile = File(...), publish_iocs: bool = False,
                           user: dict = Depends(require_role("lead"))):
    try:
        bundle = json.loads(await file.read())
        plan = ingest.plan_from_stix(bundle)
    except (ValueError, KeyError) as e:
        _bad(e)
    return ingest.ingest("stix", plan, user["username"], {"publish_iocs": publish_iocs})


@app.get("/api/ingest/jobs")
def ingest_jobs(user: dict = Depends(current_user)):
    return ingest.list_jobs()


@app.post("/api/ingest/jobs/{job_id}/retry")
def ingest_retry(job_id: str, user: dict = Depends(require_role("lead"))):
    try:
        return ingest.run_job(job_id)
    except KeyError:
        raise HTTPException(404, "job not found")


# ================================================================== admin / operator
@app.get("/api/admin/integrity")
def admin_integrity(user: dict = Depends(current_user)):
    return integrity.check()


@app.post("/api/admin/seed")
def admin_seed(user: dict = Depends(require_role("admin"))):
    return seed.seed_all(force=True)


@app.post("/api/admin/reindex")
def admin_reindex(user: dict = Depends(require_role("admin"))):
    return vectors.rebuild_all(documents.all_reports_raw())
