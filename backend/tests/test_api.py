"""Integration tests: the real API against the four live stores (docker compose up -d).

Run with ``make test-integration`` (or ``pytest -m integration``). The LLM is not required:
GraphRAG is exercised in retrieve-only mode. Everything a test writes is removed afterwards,
so the suite can run against a seeded dev stack without changing the demo corpus.
"""
import uuid

import pytest

from app import blocklist, ingest, stores
from app.config import settings

pytestmark = pytest.mark.integration

GOLD_Q = "Which threat actors share command-and-control infrastructure, and what malware was hosted there?"
TEST_IP = "203.0.113.77"  # TEST-NET-3, never a real indicator
PASSWORDS = {"analyst": "analyst123", "junior": "junior123", "lead": "lead123", "admin": "admin123"}


@pytest.fixture(scope="module")
def created():
    return {"audit": [], "jobs": [], "reports": []}


@pytest.fixture(scope="module")
def client(created):
    stores.connect()
    h = stores.health()
    stores.close()
    down = [s for s in ("neo4j", "mongodb", "redis") if not h[s]["ok"]]
    if down:
        pytest.skip(f"live stores not reachable: {', '.join(down)} (run docker compose up -d)")
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c
        # clean up while the app still holds its store connections
        db = stores.mongo_db()
        for rid in created["reports"]:
            ingest.delete_report(rid)
        db.audit_log.delete_many({"_id": {"$in": created["audit"]}})
        db.ingest_jobs.delete_many({"_id": {"$in": created["jobs"]}})
        blocklist.revoke("ip", TEST_IP)


@pytest.fixture(scope="module")
def auth(client):
    tokens = {}

    def headers(user: str) -> dict:
        if user not in tokens:
            r = client.post("/api/auth/login", json={"username": user, "password": PASSWORDS[user]})
            assert r.status_code == 200, r.text
            tokens[user] = r.json()["token"]
        return {"Authorization": f"Bearer {tokens[user]}"}
    return headers


def ask(client, auth, created, user: str, question: str = GOLD_Q, **kw) -> dict:
    r = client.post("/api/graphrag/ask", headers=auth(user),
                    json={"question": question, "use_llm": False, **kw})
    assert r.status_code == 200, r.text
    created["audit"].append(r.json()["id"])
    return r.json()


# ---------------------------------------------------------------- health (FR9)
def test_health_reports_all_stores(client):
    h = client.get("/api/health").json()
    assert h["startup"]["ok"], h["startup"]
    assert h["read_path_ok"] and h["enforcement_path_ok"]


# ---------------------------------------------------------------- auth + TLP (FR11)
def test_login_and_token_required(client):
    assert client.post("/api/auth/login", json={"username": "analyst", "password": "x"}).status_code == 401
    assert client.get("/api/reports").status_code == 401


def test_tlp_hides_amber_from_green_clearance(client, auth):
    assert client.get("/api/reports/rpt-001", headers=auth("analyst")).status_code == 200
    r = client.get("/api/reports/rpt-001", headers=auth("junior"))
    assert r.status_code == 403 and r.json()["report"]["title"] == "[withheld by TLP policy]"
    listed = client.get("/api/reports", headers=auth("junior")).json()
    assert listed["reports"] and {d["tlp"] for d in listed["reports"]} <= {"WHITE", "GREEN"}
    assert listed["hidden_by_tlp"] > 0


def test_semantic_search_respects_clearance(client, auth):
    r = client.post("/api/search/semantic", headers=auth("junior"),
                    json={"query": "spearphishing against political organisations", "k": 10})
    assert r.status_code == 200
    assert r.json()["hits"] and {h["tlp"] for h in r.json()["hits"]} <= {"WHITE", "GREEN"}


def test_role_gates(client, auth):
    body = {"type": "ip", "value": TEST_IP, "ttl": 60}
    assert client.post("/api/blocklist", headers=auth("analyst"), json=body).status_code == 403
    assert client.post("/api/admin/reindex", headers=auth("lead")).status_code == 403


# ---------------------------------------------------------------- graph (FR2)
def test_shared_infrastructure_apt28_sandworm(client, auth):
    rows = client.get("/api/graph/shared-infrastructure", params={"actor": "apt28"},
                      headers=auth("analyst")).json()
    row = next(r for r in rows if r["other"] == "sandworm")
    assert row["infra_id"] == "infra-vps-185" and "rpt-001" in row["reports"]


def test_shortest_path_between_actors(client, auth):
    p = client.get("/api/graph/path", params={"src": "apt28", "dst": "sandworm"},
                   headers=auth("analyst")).json()
    assert {"apt28", "sandworm"} <= {n["id"] for n in p["nodes"]}


# ---------------------------------------------------------------- blocklist (FR3, FR12, NFR3, NFR8)
def test_publish_enforce_revoke(client, auth):
    consumer = {"X-API-Key": settings.consumer_api_key}
    r = client.post("/api/blocklist", headers=auth("lead"),
                    json={"type": "ip", "value": TEST_IP, "ttl": 120, "severity": "high"})
    assert r.status_code == 200 and r.json()["key"] == f"ioc:ip:{TEST_IP}"
    chk = client.get("/api/enforce/check", params={"type": "ip", "value": TEST_IP}, headers=consumer).json()
    assert chk["blocked"] and 0 < chk["ttl_remaining"] <= 120 and chk["severity"] == "high"
    export = client.get("/api/enforce/export", params={"format": "txt"}, headers=consumer).text
    assert f"ip,{TEST_IP}" in export.splitlines()
    assert client.delete(f"/api/blocklist/ip/{TEST_IP}", headers=auth("lead")).json() == {"revoked": True}
    chk = client.get("/api/enforce/check", params={"type": "ip", "value": TEST_IP}, headers=consumer).json()
    assert not chk["blocked"]


def test_enforcement_requires_consumer_key(client):
    r = client.get("/api/enforce/check", params={"type": "ip", "value": TEST_IP},
                   headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_enforcement_fails_closed_when_redis_is_down(client, monkeypatch):
    def down(*_a, **_k):
        raise ConnectionError("redis unavailable")
    monkeypatch.setattr(blocklist, "lookup", down)
    r = client.get("/api/enforce/check", params={"type": "ip", "value": TEST_IP},
                   headers={"X-API-Key": settings.consumer_api_key})
    assert r.status_code == 503 and r.json()["blocked"] is True and r.json()["fail_closed"]


# ---------------------------------------------------------------- GraphRAG (FR5, FR7, NFR4)
def test_graphrag_retrieve_only_recalls_gold_path(client, auth, created):
    res = ask(client, auth, created, "analyst")
    assert res["mode"] == "retrieve-only" and not res["refused"]
    edges = {(e["source"], e["type"], e["target"]) for e in res["evidence"]["graph"]["edges"]}
    assert {("apt28", "USES_INFRA", "infra-vps-185"), ("sandworm", "USES_INFRA", "infra-vps-185")} <= edges
    assert "rpt-001" in {d["_id"] for d in res["evidence"]["documents"]}
    assert res["citation_coverage"] >= settings.min_citation_coverage and res["citations"]


def test_graphrag_context_respects_tlp(client, auth, created):
    res = ask(client, auth, created, "junior")
    assert {d["tlp"] for d in res["evidence"]["documents"]} <= {"WHITE", "GREEN"}
    assert "rpt-001" not in {d["_id"] for d in res["evidence"]["documents"]}
    assert res["answer_tlp"] in ("WHITE", "GREEN")


def test_graphrag_degrades_when_llm_is_unreachable(client, auth, created, monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")
    r = client.post("/api/graphrag/ask", headers=auth("analyst"),
                    json={"question": "Why is Mimikatz a weak attribution signal?", "use_llm": True})
    created["audit"].append(r.json()["id"])
    assert r.status_code == 200
    assert r.json()["mode"] == "retrieve-only" and r.json()["llm_error"]
    assert r.json()["evidence"]["hub_notes"]  # commodity-hub caution survives the fallback


# ---------------------------------------------------------------- audit + replay (FR10)
def test_audit_replay_reverifies_every_hop(client, auth, created):
    res = ask(client, auth, created, "analyst", max_hops=1)
    assert client.get(f"/api/audit/{res['id']}", headers=auth("junior")).status_code == 404
    rep = client.post(f"/api/audit/{res['id']}/replay", headers=auth("analyst")).json()
    verified, total = map(int, rep["summary"]["hops_verified"].split("/"))
    assert total > 0 and verified == total
    assert all(c["still_exists"] for c in rep["chunks"])


# ---------------------------------------------------------------- ingest fan-out + integrity (FR1, Sec 8.5)
def test_free_text_ingest_fans_out_and_delete_cascades(client, auth, created):
    title = f"Integration test report {uuid.uuid4().hex[:8]}"
    r = client.post("/api/ingest/report", headers=auth("lead"), json={
        "title": title, "tlp": "GREEN",
        "body": "APT28 reused Mimikatz and beaconed to 198.51.100[.]77 against a foreign ministry."})
    job = r.json()
    created["jobs"].append(job["_id"])
    created["reports"] += job["report_ids"]
    assert job["status"] == "ok" and all(s["status"] == "ok" for s in job["steps"].values())
    rid = job["report_ids"][0]
    doc = client.get(f"/api/reports/{rid}", headers=auth("junior")).json()
    assert doc["actors"] == ["apt28"] and doc["iocs"] == ["198.51.100.77"]
    assert client.get("/api/admin/integrity", headers=auth("analyst")).json()["ok"]

    assert client.delete(f"/api/reports/{rid}", headers=auth("lead")).status_code == 403
    assert client.delete(f"/api/reports/{rid}", headers=auth("admin")).json() == {"deleted": True}
    created["reports"].remove(rid)
    assert client.get(f"/api/reports/{rid}", headers=auth("admin")).status_code == 404
    assert client.get("/api/admin/integrity", headers=auth("analyst")).json()["ok"]
