"""Entity linking + IOC extraction shared by ingest and GraphRAG."""
from __future__ import annotations

import re
import threading
import time

from app import graph

IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
HASH_RE = re.compile(r"\b(?:[a-fA-F0-9]{64}|[a-fA-F0-9]{40}|[a-fA-F0-9]{32})\b")
DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:[a-zA-Z]{2,24}|onion)\b")
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
TECH_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
NOT_DOMAIN_SUFFIX = {"exe", "dll", "msi", "js", "ps1", "doc", "docx", "pdf", "zip", "txt", "sys",
                     "bat", "vbs", "xls", "xlsx", "png", "jpg", "py", "sh", "json", "xml", "html",
                     "php", "net_", "eg", "ie", "e", "i"}


def refang(text: str) -> str:
    return (text.replace("[.]", ".").replace("(.)", ".").replace("[dot]", ".")
            .replace("hxxp", "http").replace("[:]", ":"))


def extract_iocs(text: str) -> list[dict]:
    t = refang(text or "")
    found: dict[tuple, dict] = {}
    for m in IPV4_RE.findall(t):
        found[("ip", m)] = {"type": "ip", "value": m}
    for m in HASH_RE.findall(t):
        found[("hash", m.lower())] = {"type": "hash", "value": m.lower()}
    for m in DOMAIN_RE.findall(t):
        d = m.lower().rstrip(".")
        tld = d.rsplit(".", 1)[-1]
        if tld in NOT_DOMAIN_SUFFIX or IPV4_RE.fullmatch(d) or len(d) < 5:
            continue
        found[("domain", d)] = {"type": "domain", "value": d}
    return list(found.values())


def extract_refs(text: str) -> dict:
    return {"cve": sorted({c.upper() for c in CVE_RE.findall(text or "")}),
            "mitre": sorted(set(TECH_RE.findall(text or "")))}


# ------------------------------------------------------------------ gazetteer
_gaz_cache: dict = {"at": 0, "rows": []}
_gaz_lock = threading.Lock()  # one refresh at a time, not one per waiting request
_ALNUM = re.compile(r"[a-z0-9]+")
_RUN = re.compile(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]")


def _gaz() -> list[dict]:
    if time.time() - _gaz_cache["at"] > 30:
        with _gaz_lock:
            if time.time() - _gaz_cache["at"] > 30:
                _gaz_cache["rows"] = graph.gazetteer()
                _gaz_cache["at"] = time.time()
    return _gaz_cache["rows"]


def invalidate_gazetteer() -> None:
    _gaz_cache["at"] = 0


def _surface_forms(row: dict) -> list[str]:
    forms = [row.get("name"), row.get("value"), *row.get("aliases", [])]
    if row.get("linkable") is False:  # an ordinary word as a name ("Net", "Silence"): link by id only
        forms = []
    if row["label"] in ("ThreatActor", "Malware", "Technique", "Campaign"):
        forms.append(row["id"])
    return [f for f in forms if f and len(f) >= 3]


def _anchor(form: str) -> str:
    """Lookup key for a lower-cased surface form: the whole form for dotted / hyphenated
    values (IPs, domains, X-Agent), otherwise its longest alphanumeric token."""
    if _RUN.fullmatch(form):
        return form
    return max(_ALNUM.findall(form), key=len, default=form)


def _text_keys(low: str) -> set[str]:
    """Every key a surface form in `low` could have: alphanumeric tokens plus each run of
    consecutive dot-separated segments (so evil.com is found inside mail.evil.com)."""
    keys = set(_ALNUM.findall(low))
    for run in _RUN.findall(low):
        seg = run.split(".")
        keys.update(".".join(seg[i:j]) for i in range(len(seg)) for j in range(i + 1, len(seg) + 1))
    return keys


def _index() -> dict:
    """Inverted index over the gazetteer, rebuilt whenever the cached rows change. Linking
    then costs O(tokens in the text) instead of one regex per gazetteer entry."""
    rows = _gaz()
    with _gaz_lock:
        if _gaz_cache.get("index_of") is rows:
            return _gaz_cache["index"]
        by_key: dict[str, list] = {}
        by_name: dict[tuple[str, str], str] = {}
        for row in rows:
            for rank, form in enumerate(_surface_forms(row)):
                f = form.lower()
                by_key.setdefault(_anchor(f), []).append((f, form, rank, row))
                by_name.setdefault((row["label"], f), row["id"])
        _gaz_cache.update(index_of=rows, index={"by_key": by_key, "by_name": by_name}, patterns={})
        return _gaz_cache["index"]


def _found(form_lower: str, low: str) -> bool:
    pats = _gaz_cache.setdefault("patterns", {})
    pat = pats.get(form_lower)
    if pat is None:
        pat = pats[form_lower] = re.compile(r"(?<![\w-])" + re.escape(form_lower) + r"(?![\w-])")
    return pat.search(low) is not None


def link_entities(text: str) -> list[dict]:
    """Word-boundary, case-insensitive linking to graph ids. Per entity the first matching
    surface form wins (name, value, aliases, id); the longest one if ids collide."""
    low = refang(text or "").lower()
    by_key = _index()["by_key"]
    best: dict[int, tuple] = {}  # id(row) -> (rank, form, row)
    for key in _text_keys(low):
        for f, form, rank, row in by_key.get(key, ()):
            prev = best.get(id(row))
            if (prev is None or rank < prev[0]) and _found(f, low):
                best[id(row)] = (rank, form, row)
    hits: dict[str, dict] = {}
    for _, form, row in best.values():
        prev = hits.get(row["id"])
        if not prev or len(form) > len(prev["matched"]):
            hits[row["id"]] = {"id": row["id"], "label": row["label"],
                               "name": row.get("name") or row.get("value") or row["id"],
                               "matched": form}
    return sorted(hits.values(), key=lambda h: (h["label"], h["id"]))


def resolve_name(label: str, name: str) -> str | None:
    """Existing graph id for a (label, name/alias) — used to merge STIX objects into the graph."""
    return _index()["by_name"].get((label, (name or "").strip().lower()))
