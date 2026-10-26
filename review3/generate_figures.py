#!/usr/bin/env python3
"""Diagrams for the Review-III report, user manual and slides (same visual language as Review-I).

Figures carry no baked-in title or number; captions live in the documents. Drawn on a logical
1600-px-wide canvas and rendered at 2x for print.   python review3/generate_figures.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)
K = 2  # render scale

NAVY = (15, 42, 71)
TEAL = (14, 90, 102)
COPPER = (140, 78, 36)
GREEN = (27, 94, 64)
PURPLE = (72, 48, 107)
RED = (122, 42, 42)
BROWN = (92, 64, 44)
SLATE = (44, 62, 80)
BG = (252, 252, 251)
LINE = (40, 48, 56)
MUTED = (90, 98, 108)
WHITE = (255, 255, 255)
PALE_BLUE = (232, 239, 247)
PALE_GREEN = (236, 245, 240)
PALE_COPPER = (248, 240, 232)
PALE_RED = (248, 236, 236)
PALE_PURPLE = (241, 236, 247)


def font(size: int, bold: bool = False, mono: bool = False):
    if mono:
        paths = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"]
    elif bold:
        paths = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]
    else:
        paths = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]
    for p in paths:
        try:
            return ImageFont.truetype(p, size * K)
        except OSError:
            continue
    return ImageFont.load_default()


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.im = Image.new("RGB", (w * K, h * K), BG)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _s(xy):
        return [v * K for v in xy]

    def box(self, xy, fill=WHITE, outline=NAVY, r=10, width=2):
        self.d.rounded_rectangle(self._s(xy), radius=r * K, fill=fill, outline=outline, width=width * K)

    def card(self, xy, title, color, lines=(), size=12, title_size=13, align="left", mono=False):
        """Coloured header band + body lines (Review-I card style)."""
        x0, y0, x1, y1 = xy
        self.box(xy, WHITE, color, r=10)
        self.d.rounded_rectangle(self._s((x0, y0, x1, y0 + 34)), radius=10 * K, fill=color)
        self.d.rectangle(self._s((x0, y0 + 20, x1, y0 + 34)), fill=color)
        self.text_c((x0, y0, x1, y0 + 34), title, font(title_size, True), WHITE)
        f = font(size, mono=mono)
        y = y0 + 46
        for ln in lines:
            bold = ln.startswith("**")
            t = ln.strip("*")
            ff = font(size, True) if bold else f
            col = color if bold else LINE
            if align == "center":
                self.text_c((x0, y, x1, y + size + 6), t, ff, col)
            else:
                self.d.text(((x0 + 14) * K, y * K), t, font=ff, fill=col)
            y += size + 9

    def text(self, xy, t, fnt, fill=LINE):
        self.d.text((xy[0] * K, xy[1] * K), t, font=fnt, fill=fill)

    def text_c(self, xy, t, fnt, fill=LINE, gap=3):
        x0, y0, x1, y1 = self._s(xy)
        lines = t.split("\n")
        sizes = [self.d.textbbox((0, 0), ln, font=fnt) for ln in lines]
        hs = [b[3] - b[1] for b in sizes]
        total = sum(hs) + gap * K * (len(lines) - 1)
        y = (y0 + y1 - total) / 2 - K
        for ln, b, h in zip(lines, sizes, hs):
            self.d.text(((x0 + x1 - (b[2] - b[0])) / 2, y - b[1]), ln, font=fnt, fill=fill)
            y += h + gap * K

    def arrow(self, a, b, color=LINE, width=2, head=10, dashed=False):
        (x0, y0), (x1, y1) = a, b
        if dashed:
            n = max(1, int(math.dist(a, b) / 12))
            for i in range(0, n, 2):
                p = (x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n)
                q = (x0 + (x1 - x0) * min(n, i + 1) / n, y0 + (y1 - y0) * min(n, i + 1) / n)
                self.d.line(self._s((*p, *q)), fill=color, width=width * K)
        else:
            self.d.line(self._s((x0, y0, x1, y1)), fill=color, width=width * K)
        ang = math.atan2(y1 - y0, x1 - x0)
        p1 = (x1 - head * math.cos(ang - 0.42), y1 - head * math.sin(ang - 0.42))
        p2 = (x1 - head * math.cos(ang + 0.42), y1 - head * math.sin(ang + 0.42))
        self.d.polygon(self._s((x1, y1, *p1, *p2)), fill=color)

    def label(self, center, t, size=11, color=LINE, fill=WHITE):
        f = font(size, True)
        b = self.d.multiline_textbbox((0, 0), t, font=f, spacing=3 * K)
        w, h = (b[2] - b[0]) / K + 12, (b[3] - b[1]) / K + 8
        cx, cy = center
        self.d.rounded_rectangle(self._s((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)),
                                 radius=5 * K, fill=fill, outline=color, width=K)
        self.text_c((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), t, f, color)

    def save(self, name: str):
        self.im.save(OUT / name, "PNG", optimize=True)
        print("wrote", OUT / name)


def edge_point(box, toward):
    """Point where the segment from the box centre toward `toward` leaves the box."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    if dx == dy == 0:
        return cx, cy
    tx = (x1 - x0) / 2 / abs(dx) if dx else math.inf
    ty = (y1 - y0) / 2 / abs(dy) if dy else math.inf
    t = min(tx, ty)
    return cx + dx * t, cy + dy * t


# ====================================================================== 1. architecture
def fig_architecture():
    c = Canvas(1600, 915)
    # clients
    c.box((40, 20, 1560, 170), PALE_BLUE, NAVY, 12)
    c.text((60, 32), "CLIENTS", font(13, True), NAVY)
    c.text((60, 56), "Analyst console  ·  React + Vite  ·  JWT session", font(12), NAVY)
    pages = ["GraphRAG\nconsole", "Graph\nexplorer", "Report\nbrowser", "IOC\nblocklist",
             "Semantic\nsearch", "Ingest", "Audit &\nreplay", "Operations"]
    for i, pg in enumerate(pages):
        x = 60 + i * 124
        c.box((x, 82, x + 114, 152), WHITE, NAVY, 8)
        c.text_c((x, 82, x + 114, 152), pg, font(12), NAVY)
    c.box((1080, 56, 1540, 152), WHITE, RED, 8)
    c.text_c((1080, 56, 1540, 152), "Enforcement consumers  ·  firewall, EDR, SIEM\nX-API-Key, GET only", font(12), RED)

    c.arrow((540, 170), (540, 223), NAVY)
    c.label((540, 197), "HTTPS / JSON + bearer token", 10, NAVY)
    c.arrow((1300, 152), (1300, 223), RED)
    c.label((1300, 197), "/api/enforce/*", 10, RED)

    # API / orchestration
    c.box((40, 225, 1560, 560), PALE_GREEN, GREEN, 12)
    c.text((60, 237), "API & ORCHESTRATION  ·  FastAPI (Python 3.11)", font(13, True), GREEN)
    mods = [
        ((60, 268, 540, 400), "Auth & TLP policy", GREEN,
         ["JWT sessions, PBKDF2 password hashes", "roles: analyst / lead / admin", "clearance WHITE → RED checked on every read"]),
        ((560, 268, 1040, 400), "GraphRAG orchestrator", GREEN,
         ["entity linking → 4-channel retrieval", "context pack [G#] [C#] [R:id] [I#]", "prompt budget → local LLM → grounding gate"]),
        ((1060, 268, 1540, 400), "Ingest pipeline", GREEN,
         ["STIX 2.1 bundles and free-text reports", "IOC extraction and refanging", "fan-out job log, idempotent retry"]),
        ((60, 418, 540, 545), "Audit & replay", GREEN,
         ["every answer persisted with its evidence", "replay re-verifies hops, chunks,", "documents and IOC state"]),
        ((560, 418, 1040, 545), "Health, SLOs, integrity", GREEN,
         ["per-store latency p50 / p95 / p99", "Section 8.5 cross-store integrity rules", "seed and reindex (admin)"]),
        ((1060, 418, 1540, 545), "Enforcement API", RED,
         ["reads Redis only, never falls back", "Redis down → 503 with blocked: true", "/check and /export (txt, json)"]),
    ]
    for xy, t, col, ln in mods:
        c.card(xy, t, col, ln, size=12)

    # stores + LLM
    c.box((40, 600, 1250, 900), PALE_COPPER, COPPER, 12)
    c.text((60, 612), "PERSISTENCE", font(13, True), COPPER)
    stores_ = [
        ("GRAPH · Neo4j 5", NAVY, ["threat knowledge graph", "8 labels, 12 rel. types", "**operations", "MERGE on unique ids", "1–3 hop paths with", "hub budget", "shared infra / tooling", "shortestPath"]),
        ("DOCUMENT · MongoDB 7", TEAL, ["reports, schema-on-read", "STIX bundles, users,", "audit log, ingest jobs", "**operations", "get / hydrate by _id", "multikey actor, IOC", "indexes; TLP $in filter", "replace_one (idempotent)"]),
        ("VECTOR · Qdrant 1.13", PURPLE, ["report chunks, 64-d", "cosine, HNSW m = 16", "payload: tlp, actors, date", "**operations", "filtered k-NN", "payload indexes", "upsert / delete by report", "scroll (integrity check)"]),
        ("KEY–VALUE · Redis 7", RED, ["hot IOC blocklist", "ioc:{type}:{value}", "ioc:index ZSET (expiry)", "**operations", "GET + TTL, pipelined", "SET EX per-key TTL", "ZRANGEBYSCORE hot set", "AOF persistence"]),
    ]
    xs = [60, 357, 654, 951]
    for x, (t, col, ln) in zip(xs, stores_):
        c.card((x, 645, x + 280, 885), t, col, ln, size=12)
    for x in xs[:3]:
        c.arrow((x + 140, 560), (x + 140, 643), LINE)
    c.arrow((1000, 560), (1000, 643), LINE)
    c.arrow((1180, 545), (1180, 643), RED, 3)
    c.label((1180, 588), "Redis only", 10, RED)

    c.box((1270, 600, 1560, 900), PALE_PURPLE, PURPLE, 12)
    c.text((1288, 612), "LOCAL MODEL", font(13, True), PURPLE)
    c.card((1290, 645, 1540, 885), "Ollama", PURPLE,
           ["**llama3.2:3b (default)", "llama3.1:8b (optional)", "", "no cloud API (NFR1)", "LLM down →", "retrieve-only answer", "(NFR8)"], size=12)
    c.arrow((1415, 560), (1415, 643), PURPLE)
    c.label((1415, 588), "prompt ↔ answer", 10, PURPLE)
    c.save("r3_architecture.png")


# ====================================================================== 2. GraphRAG answer path
def fig_answer_path():
    c = Canvas(1600, 900)
    c.box((40, 20, 1560, 80), NAVY, NAVY, 10)
    c.text_c((40, 20, 1560, 80), "Analyst question  →  entity linking (gazetteer, aliases, refanged IOCs)", font(14, True), WHITE)
    chans = [
        ("Qdrant", PURPLE, ["k-NN over report chunks", "TLP payload filter", "→ passages [C#]"]),
        ("Neo4j", NAVY, ["1–3 hop expansion", "stop at hubs (degree ≤ 12)", "templated UC1 / UC3 paths", "→ typed edges [G#]"]),
        ("MongoDB", TEAL, ["hydrate cited reports", "TLP check per document", "orphan chunks refused", "→ documents [R:id]"]),
        ("Redis", RED, ["GET + TTL for named IOCs", "live / expired / unknown", "never a Mongo fallback", "→ IOC state [I#]"]),
    ]
    c.text((60, 96), "Parallel retrieval  ·  all four stores, TLP-filtered at the source", font(13, True), NAVY)
    for i, (t, col, ln) in enumerate(chans):
        x = 60 + i * 375
        c.card((x, 124, x + 355, 290), t, col, ln, size=12)
        c.arrow((x + 177, 290), (x + 177 if i in (1, 2) else (680 if i == 0 else 920), 330), LINE)
    c.box((340, 332, 1260, 400), PALE_GREEN, GREEN, 10)
    c.text_c((340, 332, 1260, 400), "Context pack  ·  every item carries a citation id\nup to 60 edges, 6 chunks, 10 documents, 25 IOC states", font(13, True), GREEN)

    # two branches
    c.arrow((500, 400), (300, 450), LINE)
    c.arrow((800, 400), (800, 450), LINE)
    c.card((60, 452, 560, 600), "Full evidence", SLATE,
           ["→ evidence panel: animated hops, chunks,", "   similarity map, documents, ticking TTLs", "→ audit log (hops, chunks, docs, IOC states)", "→ replay re-verifies against the live stores"], size=12)
    c.card((640, 452, 960, 600), "Prompt budget", PURPLE,
           ["top 30 facts (no MENTIONED_IN)", "6 docs × 300 chars", "12 IOC states", "ids keep full-pack numbers"], size=12)
    c.arrow((960, 526), (1010, 526), PURPLE)
    c.card((1010, 452, 1540, 600), "Local LLM", PURPLE,
           ["system prompt: cite every sentence,", "never invent, flag commodity hubs,", "say if IOCs are live, refuse if unsupported", "output ≤ 320 tokens, model kept loaded"], size=12)
    c.arrow((1275, 600), (1275, 640), LINE)

    c.box((560, 642, 1540, 760), PALE_RED, RED, 10)
    c.text((580, 652), "Groundedness gate (NFR4)", font(13, True), RED)
    steps = ["1  normalise tags\n[G1-G4] (G20) [rpt-001]", "2  keep a sentence only if\na tag is in the pack",
             "3  coverage = kept / all", "4  refuse if coverage < 0.5"]
    for i, s in enumerate(steps):
        x = 580 + i * 240
        c.box((x, 680, x + 225, 748), WHITE, RED, 8)
        c.text_c((x, 680, x + 225, 748), s, font(11), RED)
    c.arrow((560, 700), (450, 700), GREEN, 3)
    c.label((505, 680), "pass", 11, GREEN)
    c.card((60, 640, 450, 760), "Answer", GREEN,
           ["cited sentences only", "labelled with the highest TLP", "of the documents it cites"], size=12)
    c.arrow((1050, 760), (1050, 800), COPPER)
    c.label((1110, 782), "fail", 11, COPPER)
    c.box((560, 802, 1540, 880), PALE_COPPER, COPPER, 10)
    c.text_c((560, 802, 1540, 880), "Retrieve-only fallback: deterministic sentences rendered from the evidence, gated again\n"
             "(also used when the LLM is down or disabled)  ·  if nothing survives: explicit refusal", font(12), COPPER)
    c.arrow((560, 840), (255, 762), COPPER, dashed=True)
    c.save("r3_answer_path.png")


# ====================================================================== 3. graph schema
def fig_graph_schema():
    c = Canvas(1600, 1000)
    W, H = 290, 118
    pos = {
        "ThreatActor": (300, 300, NAVY, ["id, name, aliases[]", "origin, sponsor, motivation", "8 seed actors"]),
        "Campaign": (800, 140, COPPER, ["id, name, year", "target_sector, summary", "8 seed campaigns"]),
        "Victim": (1300, 140, GREEN, ["id, name", "sector, country", "8 seed victims"]),
        "Malware": (800, 500, RED, ["id, name, family, kind", "hubs: Mimikatz (5 users),", "Cobalt Strike (4)"]),
        "Technique": (1300, 500, PURPLE, ["id = ATT&CK id (T1566)", "name, tactic", "shared across campaigns"]),
        "Infrastructure": (300, 700, TEAL, ["id, value (IP / domain)", "kind, notes", "13 seed hosts"]),
        "Indicator": (800, 860, BROWN, ["(type, value) unique", "severity", "historical: kept after TTL"]),
        "Report": (1300, 860, SLATE, ["id = MongoDB _id", "title, source, date, tlp", "12 seed reports"]),
    }
    boxes = {k: (x - W / 2, y - H / 2, x + W / 2, y + H / 2) for k, (x, y, *_r) in pos.items()}
    edges = [
        ("ThreatActor", "Campaign", "ATTRIBUTED_TO_CAMPAIGN", None),
        ("Campaign", "Victim", "TARGETS", "also ThreatActor"),
        ("ThreatActor", "Malware", "USES", None),
        ("Campaign", "Malware", "USES_MALWARE", None),
        ("Campaign", "Technique", "EMPLOYS", "also ThreatActor"),
        ("Malware", "Technique", "IMPLEMENTS", None),
        ("ThreatActor", "Infrastructure", "USES_INFRA", "also Campaign"),
        ("Infrastructure", "Malware", "HOSTS", None),
        ("Infrastructure", "Indicator", "OBSERVED_AS", None),
        ("Malware", "Indicator", "HAS_IOC", None),
        ("Malware", "Report", "MENTIONED_IN", "also ThreatActor, Campaign"),
    ]
    centre = {k: (v[0], v[1]) for k, v in pos.items()}
    for a, b, rel, note in edges:
        p = edge_point(boxes[a], centre[b])
        q = edge_point(boxes[b], centre[a])
        c.arrow(p, q, LINE, 2)
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        c.label((mx, my), f"{rel}\n{note}" if note else rel, 11, LINE)
    for k, (x, y, col, ln) in pos.items():
        c.card(boxes[k], k, col, ln, size=12, align="center")
    # SHARES_UNIT self-loop on ThreatActor
    x0, y0, x1, y1 = boxes["ThreatActor"]
    c.d.arc(c._s((x0 - 70, y0 + 20, x0 + 20, y1 - 20)), 90, 270, fill=LINE, width=2 * K)
    c.arrow((x0 - 25 + 20, y0 + 22), (x0 + 2, y0 + 24), LINE)
    c.label((x0 - 70, y0 + H / 2), "SHARES_UNIT", 11, LINE)
    # notes
    c.box((40, 930 - 20, 560, 990), PALE_BLUE, NAVY, 10)
    c.text((58, 918), "Join keys across stores", font(12, True), NAVY)
    c.text((58, 940), "Report.id = MongoDB _id = Qdrant payload.report_id", font(11), LINE)
    c.text((58, 960), "Indicator (type, value) = Redis key ioc:{type}:{value}", font(11), LINE)
    c.save("r3_graph_schema.png")


# ====================================================================== 4. document + key schemas
def fig_store_schemas():
    c = Canvas(1600, 440)
    mono = True
    c.card((40, 20, 560, 420), "MongoDB  ·  reports", TEAL, [
        "**core envelope (every report)",
        '_id: "rpt-002"   ← join key', 'title, source, date', 'tlp: "GREEN"   confidence',
        'actors: ["apt29"]  campaigns: [...]', 'malware: ["sunburst", "teardrop"]',
        'iocs: ["avsvmcloud.com", ...]', "body: <narrative>",
        "**report-specific (schema-on-read)",
        'build_pipeline: { product: "Orion",', '  vector: "trojanized MSI" }',
        'mitre: ["T1195", "T1078"]', "rpt-001 → attribution {...}", "rpt-004 → ics_protocols [...]",
        "**indexes", "actors · iocs (multikey) · date · tlp",
    ], size=12, mono=False)
    c.card((600, 20, 1060, 420), "Qdrant  ·  threat_chunks", PURPLE, [
        "**point", "id: 17 (sequence in meta.chunk_seq)", "vector: float32[64], cosine",
        "**payload", "report_id: \"rpt-002\"  ← join key", "chunk_index: 0", "text: ≤ 420 chars",
        "title, source, date", "date_ts: 1612224000", 'tlp: "GREEN"', 'actors: ["apt29"]',
        "**payload indexes", "report_id, actors, tlp (keyword)", "date_ts (integer)",
        "**filters", "tlp in clearance AND actors AND date",
    ], size=12)
    c.card((1100, 20, 1560, 420), "Redis  ·  enforcement plane", RED, [
        "**hot key  (STRING, EX = TTL)", "ioc:ip:185.86.77.12", '→ {"type": "ip",', '   "severity": "high",',
        '   "actor": "apt28",', '   "campaign": "dnc-2016",', '   "published_by": "lead", ... }',
        "**expiry index  (ZSET)", "ioc:index", "member = key, score = expires_at",
        "**operations", "GET + TTL   O(1)", "SET EX + ZADD   (publish)", "ZRANGEBYSCORE  (hot set)",
        "never scanned by actor (NFR3)",
    ], size=12)
    c.save("r3_store_schemas.png")


# ====================================================================== 5. ingest fan-out
def fig_ingest():
    c = Canvas(1600, 470)
    c.card((40, 20, 330, 200), "Sources", NAVY, ["STIX 2.1 bundle (upload / JSON)", "free-text report", "role: lead or admin", "TLP from marking refs"], size=12)
    c.arrow((330, 110), (380, 110))
    c.card((380, 20, 760, 200), "Plan", GREEN, ["map SDOs / SROs to labels + edges", "merge by name or alias", "extract + refang IOCs, CVEs, T-ids", "keep report-specific fields"], size=12)
    c.arrow((760, 110), (810, 110))
    c.card((810, 20, 1150, 200), "Job log  ·  ingest_jobs", TEAL, ["one document per job", "status per step", "attempts, error, timings", "plan stored for retry"], size=12)
    steps = [("1  Neo4j", NAVY, "MERGE nodes, edges,\nReport + MENTIONED_IN"),
             ("2  MongoDB", TEAL, "replace_one report,\nstix_bundles"),
             ("3  Qdrant", PURPLE, "chunk, embed, upsert\n(needs the Report node)"),
             ("4  Redis", RED, "SET EX each IOC\n(opt-in: publish_iocs)")]
    for i, (t, col, body) in enumerate(steps):
        x = 60 + i * 380
        c.box((x, 270, x + 330, 380), WHITE, col, 10)
        c.d.rounded_rectangle(c._s((x, 270, x + 330, 302)), radius=10 * K, fill=col)
        c.d.rectangle(c._s((x, 288, x + 330, 302)), fill=col)
        c.text_c((x, 270, x + 330, 302), t, font(13, True), WHITE)
        c.text_c((x, 304, x + 330, 380), body, font(12), LINE)
        if i < 3:
            c.arrow((x + 330, 325), (x + 380, 325))
    c.arrow((980, 200), (225, 268), LINE)
    c.d.line(c._s((1530, 380, 1530, 420, 225, 420)), fill=COPPER, width=2 * K)
    c.arrow((225, 420), (225, 382), COPPER)
    c.text((560, 428), "retry resumes from the first step that did not finish  ·  every step is idempotent", font(12, True), COPPER)
    c.save("r3_ingest.png")


# ====================================================================== 6. database consoles
def fig_db_consoles():
    """2x2 composite of the four databases in their own consoles (needs capture_db_consoles.js)."""
    shots = [("db_neo4j_shared_infra.png", "Neo4j Browser  ·  graph (Cypher)", NAVY),
             ("db_mongo_document.png", "mongo-express  ·  MongoDB document", TEAL),
             ("db_redis_key.png", "Redis Commander  ·  key with live TTL", RED),
             ("db_qdrant_points.png", "Qdrant dashboard  ·  vector points + payload", PURPLE)]
    src = Path(__file__).parent / "screenshots"
    if not all((src / f).exists() for f, _, _ in shots):
        print("skip r3_db_consoles.png (run capture_db_consoles.js first)")
        return
    cw, ch, gap, band = 1440, 900, 24, 64
    im = Image.new("RGB", (2 * cw + 3 * gap, 2 * (ch + band) + 3 * gap), BG)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 34)
    for i, (name, title, col) in enumerate(shots):
        x = gap + (i % 2) * (cw + gap)
        y = gap + (i // 2) * (ch + band + gap)
        d.rectangle((x, y, x + cw, y + band), fill=col)
        d.text((x + 24, y + 14), title, font=f, fill=WHITE)
        shot = Image.open(src / name).convert("RGB").resize((cw, ch), Image.LANCZOS)
        im.paste(shot, (x, y + band))
        d.rectangle((x, y, x + cw, y + band + ch), outline=col, width=4)
    im.save(OUT / "r3_db_consoles.png", "PNG", optimize=True)
    print("wrote", OUT / "r3_db_consoles.png")


if __name__ == "__main__":
    fig_db_consoles()
    fig_architecture()
    fig_answer_path()
    fig_graph_schema()
    fig_store_schemas()
    fig_ingest()
