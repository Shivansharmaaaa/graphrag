"""MongoDB report store (FR6, FR11, Section 8.2) — schema-flexible system of record."""
from __future__ import annotations

from app import stores
from app.metrics import timed
from app.security import allowed_tlps, can_read, norm_tlp

CORE_FIELDS = ["_id", "title", "source", "date", "tlp", "confidence", "body",
               "actors", "campaigns", "malware", "iocs"]
LIST_PROJECTION = {"body": 0, "stix": 0}


def _col():
    return stores.mongo_db().reports


def variable_fields(doc: dict) -> list[str]:
    """Report-specific nested keys — the evidence for the document model (Figure 4)."""
    return [k for k in doc if k not in CORE_FIELDS and k not in ("id", "ingest_job", "ingested_at",
                                                                  "ingested_by", "stix")]


def list_reports(user: dict, actor: str | None = None, tlp: str | None = None,
                 q: str | None = None, limit: int = 100) -> dict:
    filt: dict = {"tlp": {"$in": allowed_tlps(user["clearance"])}}
    if actor:
        filt["actors"] = actor
    if tlp:
        filt["tlp"] = norm_tlp(tlp) if norm_tlp(tlp) in allowed_tlps(user["clearance"]) else "__none__"
    if q:
        filt["$or"] = [{"title": {"$regex": q, "$options": "i"}},
                       {"body": {"$regex": q, "$options": "i"}}]
    with timed("mongodb"):
        docs = list(_col().find(filt, LIST_PROJECTION).sort("date", -1).limit(limit))
    for d in docs:
        d["variable_fields"] = variable_fields(d)
    hidden = _col().count_documents({"tlp": {"$nin": allowed_tlps(user["clearance"])}})
    return {"reports": docs, "hidden_by_tlp": hidden}


def get_report(report_id: str, user: dict) -> tuple[dict | None, str]:
    """Returns (doc, status) where status is ok | not_found | forbidden."""
    with timed("mongodb"):
        doc = _col().find_one({"_id": report_id})
    if not doc:
        return None, "not_found"
    if not can_read(user, doc.get("tlp")):
        return {"_id": doc["_id"], "tlp": doc.get("tlp"), "title": "[withheld by TLP policy]"}, "forbidden"
    doc["variable_fields"] = variable_fields(doc)
    return doc, "ok"


def hydrate(report_ids: list[str], user: dict, sink: dict | None = None) -> tuple[list[dict], list[str]]:
    """GraphRAG document channel. Returns (readable docs, ids withheld by TLP)."""
    if not report_ids:
        return [], []
    with timed("mongodb", sink):
        docs = list(_col().find({"_id": {"$in": list(dict.fromkeys(report_ids))}}, {"stix": 0}))
    ok, withheld = [], []
    for d in docs:
        if can_read(user, d.get("tlp")):
            ok.append(d)
        else:
            withheld.append(d["_id"])
    return ok, withheld


def reports_mentioning_ioc(value: str, user: dict) -> list[dict]:
    with timed("mongodb"):
        docs = list(_col().find({"iocs": value, "tlp": {"$in": allowed_tlps(user["clearance"])}},
                                {"title": 1, "date": 1, "tlp": 1}))
    return docs


def upsert_report(doc: dict) -> None:
    with timed("mongodb"):
        _col().replace_one({"_id": doc["_id"]}, doc, upsert=True)


def delete_report(report_id: str) -> bool:
    return _col().delete_one({"_id": report_id}).deleted_count == 1


def all_reports_raw() -> list[dict]:
    return list(_col().find({}, {"stix": 0}))
