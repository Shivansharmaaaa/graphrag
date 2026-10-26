"""Unit tests that need no running database."""
import json
from pathlib import Path

import pytest

from app import blocklist, extract, graphrag, ingest, security, vectors

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "stix_apt28_bundle.json"


@pytest.fixture(autouse=True)
def gazetteer():
    extract._gaz_cache.update(at=9e18, rows=[
        {"id": "apt28", "label": "ThreatActor", "name": "APT28", "aliases": ["Fancy Bear"], "value": None},
        {"id": "mimikatz", "label": "Malware", "name": "Mimikatz", "aliases": [], "value": None},
        {"id": "lazarus", "label": "ThreatActor", "name": "Lazarus Group", "aliases": ["Hidden Cobra"], "value": None},
    ])


# ---------------------------------------------------------------- TLP (FR11)
def test_tlp_ordering_and_clearance():
    assert security.allowed_tlps("GREEN") == ["WHITE", "GREEN"]
    assert security.norm_tlp("TLP:CLEAR") == "WHITE"
    assert security.norm_tlp("amber+strict") == "AMBER"
    user = {"clearance": "AMBER"}
    assert security.can_read(user, "GREEN") and not security.can_read(user, "RED")
    assert security.max_tlp(["WHITE", "AMBER", "GREEN"]) == "AMBER"


def test_password_hashing():
    h = security.hash_password("s3cret")
    assert security.verify_password("s3cret", h) and not security.verify_password("nope", h)


# ---------------------------------------------------------------- extraction
def test_ioc_extraction_refangs_and_skips_filenames():
    iocs = extract.extract_iocs("Dropped setup.exe from evil-cdn[.]com, beacon 203.0.113.9, "
                                "hash d1f2a9c4e8b7a001deadbeefcafebabe")
    vals = {(i["type"], i["value"]) for i in iocs}
    assert ("domain", "evil-cdn.com") in vals
    assert ("ip", "203.0.113.9") in vals
    assert ("hash", "d1f2a9c4e8b7a001deadbeefcafebabe") in vals
    assert not any(v.endswith(".exe") for _, v in vals)


def test_entity_linking_by_alias():
    ids = {e["id"] for e in extract.link_entities("Fancy Bear reused Mimikatz")}
    assert ids == {"apt28", "mimikatz"}


def test_generic_names_link_only_by_id():
    """An ATT&CK tool called "Net" must not link on the ".net" of a domain."""
    extract._gaz_cache.update(at=9e18, rows=[
        {"id": "S0039", "label": "Malware", "name": "Net", "aliases": [], "value": None, "linkable": False},
        {"id": "apt28", "label": "ThreatActor", "name": "APT28", "aliases": [], "value": None},
    ])
    assert {e["id"] for e in extract.link_entities("APT28 used microsoft-update-check.net")} == {"apt28"}
    assert {e["id"] for e in extract.link_entities("What does S0039 do?")} == {"S0039"}


def test_feed_parsing_and_attack_text_cleanup():
    from scripts import import_feeds as f
    assert f.clean("[APT28](https://attack.mitre.org/groups/G0007) used it.(Citation: X 2020)") == "APT28 used it."
    assert f.weak("Net") and f.weak("cmd") and not f.weak("Mimikatz") and not f.weak("certutil")
    feodo = json.dumps([{"ip_address": "50.16.16.211", "port": 443, "status": "online", "malware": "QakBot",
                         "first_seen": "2025-12-30 13:56:31", "last_online": "2026-03-12"}]).encode()
    agg = (b'# header\n"first_seen_utc","dst_ip","dst_port","c2_status","last_online","malware"\n'
           b'"2021-01-17 07:30:05","67.213.75.205","443","offline","2021-09-08","Dridex"\n'
           b'"2025-06-01 00:00:00","198.51.100.7","8080","offline","2025-07-01","Emotet"\n')
    rows = {e["ip"]: e for e in f.parse_ip_feeds(feodo, agg, b"# list\n203.0.113.5\nnot-an-ip\n")}
    assert set(rows) == {"50.16.16.211", "198.51.100.7", "203.0.113.5"}  # 2021 entry is too old
    assert rows["50.16.16.211"]["severity"] == "critical" and rows["50.16.16.211"]["ttl"] == 7 * 86400
    assert rows["203.0.113.5"]["ttl"] == 86400


def _reference_link(text: str) -> list[dict]:
    """The original linker (one regex per gazetteer form): the indexed one must agree with it."""
    import re
    low = extract.refang(text or "").lower()
    hits = {}
    for row in extract._gaz():
        for form in extract._surface_forms(row):
            if re.search(r"(?<![\w-])" + re.escape(form.lower()) + r"(?![\w-])", low):
                prev = hits.get(row["id"])
                if not prev or len(form) > len(prev["matched"]):
                    hits[row["id"]] = {"id": row["id"], "label": row["label"],
                                       "name": row.get("name") or row.get("value") or row["id"],
                                       "matched": form}
                break
    return sorted(hits.values(), key=lambda h: (h["label"], h["id"]))


def test_indexed_linking_matches_reference_linker():
    extract._gaz_cache.update(at=9e18, rows=[
        {"id": "apt28", "label": "ThreatActor", "name": "APT28", "aliases": ["Fancy Bear"], "value": None},
        {"id": "x-agent", "label": "Malware", "name": "X-Agent", "aliases": [], "value": None},
        {"id": "cobalt-strike", "label": "Malware", "name": "Cobalt Strike", "aliases": ["Beacon"], "value": None},
        {"id": "industroyer", "label": "Malware", "name": "Industroyer / CrashOverride", "aliases": [], "value": None},
        {"id": "T1566", "label": "Technique", "name": "Phishing", "aliases": [], "value": None},
        {"id": "infra-evil", "label": "Infrastructure", "name": None, "aliases": [], "value": "evil.com"},
        {"id": "infra-vps", "label": "Infrastructure", "name": None, "aliases": [], "value": "185.86.77.12"},
        {"id": "ioc:ip:185.86.77.12", "label": "Indicator", "name": None, "aliases": [], "value": "185.86.77.12"},
    ])
    texts = ["mail.evil.com and evil.com.au", "x-agent-v2, my-x-agent, a.x-agent", "APT28_x vs (apt28)",
             "Cobalt Strike Beacon via T1566 phishing", "Industroyer / CrashOverride hit the grid",
             "beacon to 185.86.77[.]12 and 185.86.77.123", "Fancy Bear, fancy-bear, FANCY BEAR.", ""]
    for t in texts:
        assert extract.link_entities(t) == _reference_link(t), t
    assert extract.resolve_name("Malware", "beacon") == "cobalt-strike"
    assert extract.resolve_name("ThreatActor", "Unknown") is None


# ---------------------------------------------------------------- blocklist key schema
def test_blocklist_normalisation():
    assert blocklist.normalise("domain", "Evil.COM.") == ("domain", "evil.com")
    assert blocklist.key("ip", "1.2.3.4") == "ioc:ip:1.2.3.4"
    assert blocklist.infer_type("d1f2a9c4e8b7a001deadbeefcafebabe") == "hash"
    with pytest.raises(ValueError):
        blocklist.normalise("ip", "999.1.1.1")


# ---------------------------------------------------------------- ingest (FR1)
def test_free_text_plan_links_entities_and_keeps_extra_fields():
    plan = ingest.plan_from_text("Lure", "APT28 used Mimikatz and 198.51.100.7 (T1566).",
                                 tlp="GREEN", extra={"lure_themes": ["invite"]})
    doc = plan["reports"][0]
    assert doc["actors"] == ["apt28"] and doc["malware"] == ["mimikatz"]
    assert doc["iocs"] == ["198.51.100.7"] and doc["mitre"] == ["T1566"]
    assert doc["lure_themes"] == ["invite"] and doc["tlp"] == "GREEN"


def test_stix_bundle_maps_to_graph_document_and_indicators():
    plan = ingest.plan_from_stix(json.loads(SAMPLE.read_text()))
    labels = {n["label"] for n in plan["nodes"]}
    assert {"ThreatActor", "Campaign", "Malware", "Technique", "Infrastructure", "Indicator", "Victim"} <= labels
    actor = next(n for n in plan["nodes"] if n["label"] == "ThreatActor")
    assert actor["props"]["id"] == "apt28"  # merged into the existing graph node by name
    rels = {(e["src"], e["rel"], e["dst"]) for e in plan["edges"]}
    assert ("apt28", "ATTRIBUTED_TO_CAMPAIGN", "embassy-lure-2024") in rels  # attributed-to reversed
    assert any(r[1] == "HAS_IOC" for r in rels)
    doc = plan["reports"][0]
    assert doc["tlp"] == "GREEN" and "apt28" in doc["actors"] and len(doc["iocs"]) == 2
    assert plan["bundle"]["_id"].startswith("bundle--")


def test_stix_rejects_non_bundle():
    with pytest.raises(ValueError):
        ingest.plan_from_stix({"type": "report"})


# ---------------------------------------------------------------- chunking (Section 8.4)
def test_chunking_respects_size():
    body = " ".join(f"Sentence number {i} about threat actors." for i in range(60))
    chunks = vectors.chunk_text(body)
    assert len(chunks) > 1 and all(len(c) <= vectors.CHUNK_CHARS + 60 for c in chunks)


# ---------------------------------------------------------------- groundedness gate (NFR4)
CTX = {"facts": [{"cid": "G1"}], "chunks": [{"cid": "C1", "report_id": "rpt-002"}], "iocs": [{"cid": "I1"}]}


def test_uncited_sentences_are_dropped():
    g = graphrag.enforce_grounding(
        "APT29 used SUNBURST. [G1] This is speculation. The domain is live [I1].", CTX, [{"_id": "rpt-002"}])
    assert g["answer"] == "APT29 used SUNBURST [G1]. The domain is live [I1]."
    assert g["dropped"] == ["This is speculation."] and not g["refused"]


def test_invented_citations_do_not_count():
    g = graphrag.enforce_grounding("Mars is red [G9]. Pluto is cold [R:rpt-999].", CTX, [])
    assert g["refused"] and g["answer"] == graphrag.REFUSAL


def test_explicit_refusal_passes_through():
    g = graphrag.enforce_grounding(graphrag.REFUSAL, CTX, [])
    assert g["refused"]


def test_grouped_citations_are_expanded():
    g = graphrag.enforce_grounding("APT29 used SUNBURST [G1, C1].", CTX, [])
    assert g["citations"] == ["G1", "C1"] and not g["refused"]


def test_variant_citation_forms_are_recovered():
    ctx = {**CTX, "facts": [{"cid": f"G{i}"} for i in range(1, 5)]}
    g = graphrag.enforce_grounding(
        "Four actors use it [G1-G4]. Sandworm ran NotPetya (G2). It is documented [R:002]. "
        "Also in [rpt-002].", ctx, [{"_id": "rpt-002"}])
    assert g["citations"] == ["G1", "G2", "G3", "G4", "R:rpt-002"] and g["dropped"] == []


def test_parenthesised_c2_is_not_a_citation():
    g = graphrag.enforce_grounding("The actor rotated its command-and-control (C2) servers.", CTX, [])
    assert g["refused"] and g["citations"] == []
