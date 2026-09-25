"""Entity linking + IOC extraction shared by ingest and GraphRAG."""
from __future__ import annotations

import re
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


def _gaz() -> list[dict]:
    if time.time() - _gaz_cache["at"] > 30:
        _gaz_cache["rows"] = graph.gazetteer()
        _gaz_cache["at"] = time.time()
    return _gaz_cache["rows"]


def invalidate_gazetteer() -> None:
    _gaz_cache["at"] = 0


def _surface_forms(row: dict) -> list[str]:
    forms = [row.get("name"), row.get("value"), *row.get("aliases", [])]
    if row["label"] in ("ThreatActor", "Malware", "Technique", "Campaign"):
        forms.append(row["id"])
    return [f for f in forms if f and len(f) >= 3]


def link_entities(text: str) -> list[dict]:
    """Longest-match, word-boundary, case-insensitive linking to graph ids."""
    low = refang(text or "").lower()
    hits: dict[str, dict] = {}
    for row in _gaz():
        for form in _surface_forms(row):
            f = form.lower()
            pat = r"(?<![\w-])" + re.escape(f) + r"(?![\w-])"
            if re.search(pat, low):
                prev = hits.get(row["id"])
                if not prev or len(f) > len(prev["matched"]):
                    hits[row["id"]] = {"id": row["id"], "label": row["label"],
                                       "name": row.get("name") or row.get("value") or row["id"],
                                       "matched": form}
                break
    # common-word collisions: a campaign named like its malware is kept; drop 1-3 char noise
    return sorted(hits.values(), key=lambda h: (h["label"], h["id"]))


def resolve_name(label: str, name: str) -> str | None:
    """Existing graph id for a (label, name/alias) — used to merge STIX objects into the graph."""
    n = (name or "").strip().lower()
    for row in _gaz():
        if row["label"] != label:
            continue
        if n in {f.lower() for f in _surface_forms(row) if f}:
            return row["id"]
    return None
