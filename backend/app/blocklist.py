"""Redis enforcement plane (FR3, FR12, Section 8.3).

Key:   ioc:{type}:{value}  →  JSON {value, type, actor, campaign, severity, ttl, published_by, published_at}
TTL:   EXPIRE = operational TTL chosen by the detection engineer
Index: sorted set ``ioc:index`` scored by expiry unix time (hot-set listing + expiry alerts)

Redis is never queried by actor name, and a Redis miss is never "fixed" by scanning
MongoDB on the enforcement path (NFR3). The historical graph is never rewritten here (FR12).
"""
from __future__ import annotations

import ipaddress
import json
import re
import time

from app import stores
from app.metrics import timed

INDEX = "ioc:index"
IOC_TYPES = ("ip", "domain", "hash", "url")
SEVERITIES = ("low", "medium", "high", "critical")
_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9-]{1,63}\.)+[a-z0-9-]{2,63}$", re.I)


def normalise(ioc_type: str, value: str) -> tuple[str, str]:
    t = ioc_type.lower().strip()
    v = value.strip()
    if t not in IOC_TYPES:
        raise ValueError(f"type must be one of {IOC_TYPES}")
    if t == "ip":
        v = str(ipaddress.ip_address(v))
    elif t == "domain":
        v = v.lower().rstrip(".")
        if not _DOMAIN_RE.match(v):
            raise ValueError("invalid domain")
    elif t == "hash":
        v = v.lower()
        if not _HASH_RE.match(v):
            raise ValueError("hash must be MD5, SHA-1 or SHA-256 hex")
    return t, v


def infer_type(value: str) -> str:
    v = value.strip()
    try:
        ipaddress.ip_address(v)
        return "ip"
    except ValueError:
        pass
    if _HASH_RE.match(v):
        return "hash"
    if v.startswith(("http://", "https://")):
        return "url"
    return "domain"


def key(ioc_type: str, value: str) -> str:
    return f"ioc:{ioc_type}:{value}"


def publish(ioc_type: str, value: str, ttl: int, severity: str = "medium",
            actor: str | None = None, campaign: str | None = None,
            published_by: str = "system", source: str | None = None) -> dict:
    t, v = normalise(ioc_type, value)
    if ttl <= 0:
        raise ValueError("ttl must be positive seconds")
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}")
    now = int(time.time())
    payload = {
        "value": v, "type": t, "actor": actor, "campaign": campaign,
        "severity": severity, "ttl": int(ttl), "published_by": published_by,
        "published_at": now, "source": source,
    }
    k = key(t, v)
    r = stores.redis_client
    with timed("redis"):
        pipe = r.pipeline()
        pipe.set(k, json.dumps(payload), ex=int(ttl))
        pipe.zadd(INDEX, {k: now + int(ttl)})
        pipe.execute()
    return {**payload, "key": k, "expires_at": now + int(ttl)}


def revoke(ioc_type: str, value: str) -> bool:
    t, v = normalise(ioc_type, value)
    k = key(t, v)
    with timed("redis"):
        pipe = stores.redis_client.pipeline()
        pipe.delete(k)
        pipe.zrem(INDEX, k)
        deleted, _ = pipe.execute()
    return bool(deleted)


def lookup(ioc_type: str, value: str) -> dict:
    """O(1) GET + TTL. Raises on Redis failure so callers can decide fail-open/closed."""
    t, v = normalise(ioc_type, value)
    k = key(t, v)
    with timed("redis"):
        pipe = stores.redis_client.pipeline()
        pipe.get(k)
        pipe.ttl(k)
        raw, ttl = pipe.execute()
    if raw is None:
        return {"key": k, "type": t, "value": v, "blocked": False, "ttl_remaining": 0}
    return {"key": k, **json.loads(raw), "blocked": True, "ttl_remaining": int(ttl)}


def lookup_many(values: list[str]) -> list[dict]:
    """Batch state lookup for GraphRAG (type inferred). Never touches MongoDB."""
    keys = []
    for v in dict.fromkeys(values):
        try:
            t, nv = normalise(infer_type(v), v)
            keys.append((t, nv, key(t, nv)))
        except ValueError:
            continue
    if not keys:
        return []
    with timed("redis"):
        pipe = stores.redis_client.pipeline()
        for _, _, k in keys:
            pipe.get(k)
            pipe.ttl(k)
        res = pipe.execute()
    out = []
    for i, (t, v, k) in enumerate(keys):
        raw, ttl = res[2 * i], res[2 * i + 1]
        if raw:
            out.append({"key": k, **json.loads(raw), "state": "live", "ttl_remaining": int(ttl)})
        else:
            out.append({"key": k, "type": t, "value": v, "state": "not-in-blocklist",
                        "ttl_remaining": 0})
    return out


def hot_set(include_expired: bool = True, limit: int = 500) -> dict:
    """Live keys with remaining TTL (for the console) + recently expired keys (UC4)."""
    r = stores.redis_client
    now = int(time.time())
    with timed("redis"):
        live_keys = r.zrangebyscore(INDEX, now, "+inf", start=0, num=limit)
        expired_keys = r.zrangebyscore(INDEX, "-inf", now - 1, start=0, num=100) if include_expired else []
        pipe = r.pipeline()
        for k in live_keys:
            pipe.get(k)
            pipe.ttl(k)
        res = pipe.execute() if live_keys else []
    live = []
    for i, k in enumerate(live_keys):
        raw, ttl = res[2 * i], res[2 * i + 1]
        if raw is None:  # expired between the two calls
            expired_keys.append(k)
            continue
        live.append({"key": k, **json.loads(raw), "ttl_remaining": int(ttl)})
    expired = []
    for k in expired_keys:
        _, t, v = k.split(":", 2)
        expired.append({"key": k, "type": t, "value": v, "ttl_remaining": 0, "state": "expired"})
    live.sort(key=lambda x: x["ttl_remaining"])
    return {"live": live, "expired": expired, "server_time": now}


def purge_expired_index(older_than_s: int = 3600) -> int:
    """Housekeeping: drop index entries that expired more than an hour ago."""
    return stores.redis_client.zremrangebyscore(INDEX, "-inf", int(time.time()) - older_than_s)


def export_hot_set() -> list[dict]:
    """Downstream consumer view: keys only, never report bodies (Section 7.4)."""
    return [
        {"type": x["type"], "value": x["value"], "severity": x.get("severity"),
         "expires_in": x["ttl_remaining"]}
        for x in hot_set(include_expired=False)["live"]
    ]
