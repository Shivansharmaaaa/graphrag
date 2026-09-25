"""Qdrant vector channel (FR4, Section 8.4).

Collection ``threat_chunks`` · cosine · HNSW.
Payload: {id, report_id, title, source, date, date_ts, chunk_index, text, actors[], campaigns[], tlp}
``tlp`` and ``date_ts`` are added to the Section 8.4 payload so FR4's TLP / date filters are
native payload filters. Filters only restrict the candidate set; k-NN is always over vectors.
"""
from __future__ import annotations

import datetime as dt
import re

from pymongo import ReturnDocument
from qdrant_client.http import models as qm

from app import stores
from app.config import settings
from app.embeddings import embedder
from app.metrics import timed
from app.security import allowed_tlps, norm_tlp

COLLECTION = settings.qdrant_collection
CHUNK_CHARS = 420


def _date_ts(date: str | None) -> int:
    try:
        return int(dt.datetime.fromisoformat(str(date)[:10]).replace(tzinfo=dt.timezone.utc).timestamp())
    except Exception:
        return 0


def chunk_text(body: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body or "") if s.strip()]
    chunks, buf = [], ""
    for s in sentences:
        if buf and len(buf) + len(s) + 1 > CHUNK_CHARS:
            chunks.append(buf)
            buf = s
        else:
            buf = f"{buf} {s}".strip()
    if buf:
        chunks.append(buf)
    return chunks or ([body] if body else [])


def _next_ids(n: int) -> list[int]:
    """Monotonic point ids from a MongoDB counter (Section 8.4)."""
    doc = stores.mongo_db().meta.find_one_and_update(
        {"_id": "chunk_seq"}, {"$inc": {"value": n}}, upsert=True,
        return_document=ReturnDocument.AFTER)
    end = doc["value"]
    return list(range(end - n + 1, end + 1))


def collection_exists() -> bool:
    return COLLECTION in [c.name for c in stores.qdrant_client.get_collections().collections]


def ensure_collection(recreate: bool = False) -> None:
    q = stores.qdrant_client
    if recreate and collection_exists():
        q.delete_collection(COLLECTION)
    if not collection_exists():
        q.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=embedder.dim, distance=qm.Distance.COSINE),
            hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=100),
        )
        for field, schema in (("report_id", qm.PayloadSchemaType.KEYWORD),
                              ("actors", qm.PayloadSchemaType.KEYWORD),
                              ("tlp", qm.PayloadSchemaType.KEYWORD),
                              ("date_ts", qm.PayloadSchemaType.INTEGER)):
            try:
                q.create_payload_index(COLLECTION, field_name=field, field_schema=schema)
            except Exception:
                pass  # embedded mode ignores payload indexes


def _payloads(doc: dict) -> list[dict]:
    return [{
        "report_id": doc["_id"], "title": doc.get("title", ""), "source": doc.get("source", ""),
        "date": doc.get("date", ""), "date_ts": _date_ts(doc.get("date")), "chunk_index": i,
        "text": text, "actors": doc.get("actors", []), "campaigns": doc.get("campaigns", []),
        "tlp": norm_tlp(doc.get("tlp")),
    } for i, text in enumerate(chunk_text(doc.get("body", "")))]


def delete_report_chunks(report_id: str) -> None:
    if not collection_exists():
        return
    stores.qdrant_client.delete(
        COLLECTION,
        points_selector=qm.FilterSelector(filter=qm.Filter(must=[
            qm.FieldCondition(key="report_id", match=qm.MatchValue(value=report_id))])),
    )


def index_report(doc: dict) -> int:
    """Idempotent: delete this report's chunks, then embed + upsert fresh ones."""
    if not embedder.ready and not embedder.load():
        raise RuntimeError("embedder not ready — run a vector rebuild first")
    ensure_collection()
    delete_report_chunks(doc["_id"])
    payloads = _payloads(doc)
    if not payloads:
        return 0
    vecs = embedder.embed([p["text"] + " " + p["title"] for p in payloads])
    ids = _next_ids(len(payloads))
    points = []
    for pid, p, v in zip(ids, payloads, vecs):
        p["id"] = pid
        points.append(qm.PointStruct(id=pid, vector=v, payload=p))
    with timed("qdrant"):
        stores.qdrant_client.upsert(COLLECTION, points=points, wait=True)
    return len(points)


def rebuild_all(docs: list[dict]) -> dict:
    """Refit the (TF-IDF) embedder on the whole corpus and rebuild the collection."""
    texts = []
    for d in docs:
        texts += [p["text"] + " " + p["title"] for p in _payloads(d)]
    embedder.fit(texts)
    ensure_collection(recreate=True)
    stores.mongo_db().meta.update_one({"_id": "chunk_seq"}, {"$set": {"value": 0}}, upsert=True)
    n = sum(index_report(d) for d in docs)
    return {"points": n, "dim": embedder.dim, "backend": embedder.backend}


def _filter(user: dict, actors: list[str] | None, tlp: list[str] | None,
            date_from: str | None, date_to: str | None,
            report_ids: list[str] | None = None) -> qm.Filter:
    allowed = allowed_tlps(user["clearance"])
    if tlp:
        allowed = [t for t in allowed if t in {norm_tlp(x) for x in tlp}] or ["__none__"]
    must = [qm.FieldCondition(key="tlp", match=qm.MatchAny(any=allowed))]
    if actors:
        must.append(qm.FieldCondition(key="actors", match=qm.MatchAny(any=actors)))
    if date_from or date_to:
        must.append(qm.FieldCondition(key="date_ts", range=qm.Range(
            gte=_date_ts(date_from) if date_from else None,
            lte=_date_ts(date_to) if date_to else None)))
    if report_ids:
        must.append(qm.FieldCondition(key="report_id", match=qm.MatchAny(any=report_ids)))
    return qm.Filter(must=must)


def search(query: str, user: dict, k: int = 6, actors: list[str] | None = None,
           tlp: list[str] | None = None, date_from: str | None = None,
           date_to: str | None = None, with_map: bool = False,
           sink: dict | None = None) -> dict:
    if not collection_exists():
        return {"hits": [], "map": None}
    if not embedder.ready:
        embedder.load()
    qvec = embedder.embed([query])[0]
    with timed("qdrant", sink):
        res = stores.qdrant_client.query_points(
            COLLECTION, query=qvec, limit=k, with_payload=True, with_vectors=with_map,
            query_filter=_filter(user, actors, tlp, date_from, date_to),
        ).points
    hits = [{"point_id": p.id, "score": round(float(p.score), 4), **(p.payload or {})} for p in res]
    out = {"hits": hits, "map": None}
    if with_map and res:
        # similarity neighbourhood: query + hits + a background sample of the collection
        bg, _ = stores.qdrant_client.scroll(
            COLLECTION, limit=60, with_vectors=True, with_payload=["report_id", "title", "tlp"],
            scroll_filter=_filter(user, None, None, None, None))
        hit_ids = {p.id for p in res}
        bg = [p for p in bg if p.id not in hit_ids]
        vecs = [qvec] + [list(p.vector) for p in res] + [list(p.vector) for p in bg]
        xy = embedder.project_2d(vecs)
        pts = [{"kind": "query", "x": xy[0][0], "y": xy[0][1], "label": query}]
        for i, p in enumerate(res, start=1):
            pts.append({"kind": "hit", "x": xy[i][0], "y": xy[i][1], "point_id": p.id,
                        "report_id": p.payload["report_id"], "label": p.payload["title"],
                        "score": round(float(p.score), 4)})
        off = 1 + len(res)
        for j, p in enumerate(bg):
            pts.append({"kind": "corpus", "x": xy[off + j][0], "y": xy[off + j][1],
                        "point_id": p.id, "report_id": p.payload["report_id"],
                        "label": p.payload["title"]})
        out["map"] = pts
    return out


def get_points(ids: list[int]) -> list[dict]:
    if not ids or not collection_exists():
        return []
    pts = stores.qdrant_client.retrieve(COLLECTION, ids=ids, with_payload=True)
    return [{"point_id": p.id, **(p.payload or {})} for p in pts]


def report_ids_in_index() -> set[str]:
    if not collection_exists():
        return set()
    ids, offset = set(), None
    while True:
        pts, offset = stores.qdrant_client.scroll(COLLECTION, limit=256, offset=offset,
                                                  with_payload=["report_id"])
        ids |= {p.payload["report_id"] for p in pts}
        if offset is None:
            break
    return ids
