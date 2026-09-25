#!/usr/bin/env python3
"""Academic figures for Review-1: architecture, GraphRAG flow, graph schema."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

NAVY = (15, 42, 71)
SLATE = (44, 62, 80)
TEAL = (14, 90, 102)
COPPER = (140, 78, 36)
GREEN = (27, 94, 64)
PURPLE = (72, 48, 107)
RED = (122, 42, 42)
BG = (252, 252, 251)
LINE = (40, 48, 56)
MUTED = (90, 98, 108)
WHITE = (255, 255, 255)
PALE = (236, 241, 246)


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


F14 = font(14)
F13 = font(13)
F12 = font(12)
F11 = font(11)
F10 = font(10)
F9 = font(9)
FB18 = font(18, True)
FB16 = font(16, True)
FB14 = font(14, True)
FB13 = font(13, True)
FB12 = font(12, True)
FB11 = font(11, True)


def rounded(draw, xy, r, fill, outline=None, width=2):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def center_text(draw, xy, text, fnt, fill=WHITE):
    x0, y0, x1, y1 = xy
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((x0 + x1 - tw) / 2, (y0 + y1 - th) / 2 - 1), text, font=fnt, fill=fill)


def wrapped_center(draw, xy, lines, fnt, fill=WHITE, gap=2):
    x0, y0, x1, y1 = xy
    heights = []
    widths = []
    for line in lines:
        b = draw.textbbox((0, 0), line, font=fnt)
        widths.append(b[2] - b[0])
        heights.append(b[3] - b[1])
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = (y0 + y1 - total_h) / 2
    cx = (x0 + x1) / 2
    for line, w, h in zip(lines, widths, heights):
        draw.text((cx - w / 2, y), line, font=fnt, fill=fill)
        y += h + gap


def arrow(draw, start, end, color=LINE, width=2):
    draw.line([start, end], fill=color, width=width)
    x0, y0 = start
    x1, y1 = end
    import math

    ang = math.atan2(y1 - y0, x1 - x0)
    L = 10
    a1 = (x1 - L * math.cos(ang - 0.4), y1 - L * math.sin(ang - 0.4))
    a2 = (x1 - L * math.cos(ang + 0.4), y1 - L * math.sin(ang + 0.4))
    draw.polygon([end, a1, a2], fill=color)


def caption(draw, w, h, text):
    draw.text((40, h - 36), text, font=F11, fill=MUTED)


def fig_architecture():
    W, H = 1600, 1100
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((40, 28), "Figure 1.  Initial system architecture (polyglot persistence + GraphRAG)", font=FB18, fill=NAVY)

    # Presentation
    rounded(d, (80, 80, 1520, 210), 12, (232, 239, 247), NAVY, 2)
    d.text((100, 92), "PRESENTATION LAYER  —  analyst dashboard", font=FB13, fill=NAVY)
    boxes = [
        (110, 130, 360, 190, "Graph explorer\n(Neo4j traversals)"),
        (385, 130, 635, 190, "Report browser\n(MongoDB documents)"),
        (660, 130, 910, 190, "IOC blocklist\n(Redis TTL live view)"),
        (935, 130, 1185, 190, "Semantic search\n(Qdrant similarity)"),
        (1210, 130, 1490, 190, "GraphRAG console\n(NL Q&A + citations)"),
    ]
    for x0, y0, x1, y1, t in boxes:
        rounded(d, (x0, y0, x1, y1), 8, WHITE, NAVY, 2)
        wrapped_center(d, (x0, y0, x1, y1), t.split("\n"), F11, NAVY)

    arrow(d, (800, 210), (800, 248))

    # Orchestration
    rounded(d, (80, 250, 1520, 470), 12, (236, 245, 240), GREEN, 2)
    d.text((100, 262), "ORCHESTRATION LAYER  —  GraphRAG service", font=FB13, fill=GREEN)
    orch = [
        (110, 310, 370, 400, TEAL, "1. Query understanding\nentity linking"),
        (400, 310, 660, 400, PURPLE, "2. Vector retrieve\nQdrant top-k chunks"),
        (690, 310, 950, 400, NAVY, "3. Graph expand\nNeo4j 1–3 hop paths"),
        (980, 310, 1240, 400, COPPER, "4. Document hydrate\nMongoDB full reports"),
        (1270, 310, 1490, 400, SLATE, "5. Grounded generate\nlocal LLM + citations"),
    ]
    for x0, y0, x1, y1, col, t in orch:
        rounded(d, (x0, y0, x1, y1), 8, WHITE, col, 3)
        wrapped_center(d, (x0, y0, x1, y1), t.split("\n"), F11, col)
        if x1 < 1400:
            arrow(d, (x1 + 4, 355), (x1 + 26, 355), col)
    rounded(d, (110, 418, 1490, 452), 6, WHITE, GREEN, 1)
    center_text(d, (110, 418, 1490, 452), "also: Redis IOC lookup (sub-millisecond cache) before graph/document round-trips", F12, GREEN)

    arrow(d, (800, 470), (800, 508))

    # Persistence
    rounded(d, (80, 510, 1520, 860), 12, (247, 241, 232), COPPER, 2)
    d.text((100, 522), "PERSISTENCE LAYER  —  four complementary NoSQL models", font=FB13, fill=COPPER)

    stores = [
        (110, 565, 460, 830, NAVY, "GRAPH  ·  Neo4j",
         ["Threat knowledge graph", "Actors · campaigns · malware", "infra · techniques · victims", "",
          "Why this model", "Multi-hop paths without joins", "e.g. shared C2 / shared tooling"]),
        (485, 565, 835, 830, TEAL, "DOCUMENT  ·  MongoDB",
         ["Raw CTI reports (TLP, IOCs,", "variable nested fields)", "", "Why this model",
          "Schema-flexible ingest", "No migrations as report", "formats evolve"]),
        (860, 565, 1210, 830, RED, "KEY–VALUE  ·  Redis",
         ["Hot IOC blocklist", "IP / domain / hash → meta", "TTL auto-expiry", "",
          "Why this model", "O(1) lookup at line rate", "Freshness matches IOC life"]),
        (1235, 565, 1490, 830, PURPLE, "VECTOR  ·  Qdrant",
         ["Embedded report chunks", "cosine / HNSW index", "", "Why this model",
          "Semantic similarity", "beyond keyword match"]),
    ]
    for x0, y0, x1, y1, col, title, lines in stores:
        rounded(d, (x0, y0, x1, y1), 10, WHITE, col, 3)
        rounded(d, (x0, y0, x1, y0 + 42), 10, col, col, 0)
        d.rectangle((x0, y0 + 28, x1, y0 + 42), fill=col)
        center_text(d, (x0, y0, x1, y0 + 42), title, FB12, WHITE)
        y = y0 + 56
        for line in lines:
            if line == "Why this model":
                d.text((x0 + 16, y), line, font=FB11, fill=col)
            elif line:
                d.text((x0 + 16, y), line, font=F11, fill=SLATE)
            y += 20

    caption(d, W, H, "Polyglot persistence: each store is used only where its data model is demonstrably superior.")
    im.save(OUT / "fig1_architecture.png", "PNG")
    print("wrote fig1")


def fig_graphrag():
    W, H = 1600, 900
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((40, 28), "Figure 2.  GraphRAG query pipeline (retrieval + generation)", font=FB18, fill=NAVY)

    # Analyst query
    rounded(d, (80, 90, 1520, 160), 10, NAVY, NAVY, 0)
    center_text(d, (80, 90, 1520, 160),
                'Analyst:  “Which actors share C2 infrastructure with APT28, and which reports discuss that overlap?”',
                FB14, WHITE)

    arrow(d, (800, 160), (800, 198))

    # Parallel retrieve
    d.text((80, 210), "Parallel retrieval  (grounding evidence)", font=FB14, fill=NAVY)
    cols = [
        (80, 250, 440, 520, PURPLE, "Qdrant",
         ["Embed the question", "k-NN over report chunks", "Return passages + scores", "",
          "Output: semantically related", "narrative evidence"]),
        (460, 250, 820, 520, NAVY, "Neo4j",
         ["Match linked entities", "Traverse 1–3 hops", "Shared infra / tooling paths", "",
          "Output: typed subgraph", "and relationship facts"]),
        (840, 250, 1200, 520, TEAL, "MongoDB",
         ["Load full reports by id", "Keep variable schema", "Preserve TLP / nested IOCs", "",
          "Output: citable source", "documents"]),
        (1220, 250, 1520, 520, RED, "Redis",
         ["Lookup mentioned IOCs", "Return TTL + severity", "", "Output: live blocklist",
          "state (may already", "have expired)"]),
    ]
    for x0, y0, x1, y1, col, title, lines in cols:
        rounded(d, (x0, y0, x1, y1), 10, WHITE, col, 3)
        rounded(d, (x0, y0, x1, y0 + 44), 10, col, col, 0)
        d.rectangle((x0, y0 + 30, x1, y0 + 44), fill=col)
        center_text(d, (x0, y0, x1, y0 + 44), title, FB13, WHITE)
        y = y0 + 62
        for line in lines:
            d.text((x0 + 18, y), line, font=F12, fill=SLATE if line else SLATE)
            y += 22

    for x in (430, 810, 1170):
        arrow(d, (x + 10, 385), (x + 28, 385), MUTED)

    arrow(d, (800, 520), (800, 558))

    rounded(d, (200, 560, 1400, 710), 12, (236, 245, 240), GREEN, 2)
    d.text((230, 578), "Context pack  →  locally hosted LLM  (Ollama / Llama)", font=FB14, fill=GREEN)
    d.text((230, 616), "Prompt contains only retrieved graph facts, passages, and report identifiers. The model is instructed to", font=F12, fill=SLATE)
    d.text((230, 640), "refuse unsupported claims. Every sentence in the answer is tied to a graph edge, a Qdrant chunk, or a MongoDB _id.", font=F12, fill=SLATE)
    d.text((230, 672), "Dashboard replays the path: hops light up, similar chunks plot, Redis TTLs tick — so the NoSQL split is observable.", font=F12, fill=SLATE)

    arrow(d, (800, 710), (800, 748))
    rounded(d, (80, 750, 1520, 830), 10, WHITE, GREEN, 3)
    center_text(d, (80, 750, 1520, 830),
                "Grounded answer  +  citations  +  animated traversal  +  similarity hits  +  live IOC cache state",
                FB13, GREEN)

    caption(d, W, H, "GraphRAG = graph traversal + vector retrieval + generation, not generation alone.")
    im.save(OUT / "fig2_graphrag.png", "PNG")
    print("wrote fig2")


def fig_graph_schema():
    W, H = 1600, 1100
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((40, 28), "Figure 3.  Threat knowledge graph schema (Neo4j property graph)", font=FB18, fill=NAVY)

    # node positions: (cx, cy, w, h, color, title, subtitle)
    nodes = {
        "actor": (280, 200, 220, 88, NAVY, "ThreatActor", "id, name, aliases,\norigin, motivation"),
        "camp": (800, 140, 220, 88, COPPER, "Campaign", "id, name, year,\ntarget_sector"),
        "mal": (1320, 200, 220, 88, RED, "Malware", "id, name, family, kind"),
        "infra": (280, 500, 220, 88, TEAL, "Infrastructure", "id, value, kind, notes"),
        "tech": (800, 500, 220, 88, PURPLE, "Technique", "id (ATT&CK), name, tactic"),
        "ind": (1320, 500, 220, 88, (90, 60, 40), "Indicator", "value, type, severity"),
        "vic": (280, 820, 220, 88, GREEN, "Victim", "name, sector, country"),
        "rep": (800, 820, 260, 88, SLATE, "Report", "id → MongoDB _id\ntitle, tlp, date"),
    }

    def box(key):
        cx, cy, w, h, col, title, sub = nodes[key]
        x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        rounded(d, (x0, y0, x1, y1), 12, WHITE, col, 3)
        rounded(d, (x0, y0, x1, y0 + 32), 12, col, col, 0)
        d.rectangle((x0, y0 + 20, x1, y0 + 32), fill=col)
        center_text(d, (x0, y0, x1, y0 + 32), title, FB12, WHITE)
        wrapped_center(d, (x0, y0 + 32, x1, y1), sub.split("\n"), F11, SLATE)
        return cx, cy, w, h

    pos = {k: box(k) for k in nodes}

    def edge(a, b, label, offset=(0, 0), color=LINE):
        ax, ay, aw, ah = pos[a]
        bx, by, bw, bh = pos[b]
        # start/end at box borders toward the other
        dx, dy = bx - ax, by - ay
        import math
        dist = math.hypot(dx, dy) or 1
        sx = ax + (aw / 2) * dx / dist * 0.92
        sy = ay + (ah / 2) * dy / dist * 0.92
        ex = bx - (bw / 2) * dx / dist * 0.92
        ey = by - (bh / 2) * dy / dist * 0.92
        sx += offset[0]
        sy += offset[1]
        ex += offset[0]
        ey += offset[1]
        arrow(d, (sx, sy), (ex, ey), color, 2)
        mx, my = (sx + ex) / 2 + offset[0] * 0.2, (sy + ey) / 2 + offset[1] * 0.2
        bb = d.textbbox((0, 0), label, font=F10)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = 4
        d.rounded_rectangle((mx - tw / 2 - pad, my - th / 2 - pad, mx + tw / 2 + pad, my + th / 2 + pad),
                            4, fill=BG, outline=color)
        d.text((mx - tw / 2, my - th / 2 - 1), label, font=F10, fill=color)

    edge("actor", "camp", "ATTRIBUTED_TO")
    edge("actor", "mal", "USES", (0, 8))
    edge("camp", "mal", "USES_MALWARE", (0, -6))
    edge("actor", "infra", "USES_INFRA")
    edge("actor", "tech", "EMPLOYS", (10, 0))
    edge("camp", "tech", "EMPLOYS")
    edge("mal", "tech", "IMPLEMENTS")
    edge("mal", "ind", "HAS_IOC", (8, 0))
    edge("infra", "ind", "OBSERVED_AS", (0, 10))
    edge("infra", "mal", "HOSTS", (20, -10))
    edge("camp", "vic", "TARGETS")
    edge("actor", "vic", "TARGETS", (-16, 0))
    edge("actor", "rep", "MENTIONED_IN", (30, 0))
    edge("camp", "rep", "MENTIONED_IN")
    edge("mal", "rep", "MENTIONED_IN", (-20, 8))

    # note
    rounded(d, (1080, 740, 1520, 980), 10, PALE, NAVY, 1)
    d.text((1100, 758), "Design notes", font=FB13, fill=NAVY)
    notes = [
        "• Report.id is the join key to MongoDB.",
        "• Indicator.value is the Redis key suffix.",
        "• Multi-hop example: Actor–USES_INFRA→",
        "  Infra←USES_INFRA–Actor  (shared C2).",
        "• SHARES_UNIT links APT28–Sandworm (GRU).",
        "• Commodity tools (Mimikatz, Beacon) are",
        "  hubs — weak for attribution, useful for",
        "  clustering and GraphRAG context.",
    ]
    y = 788
    for n in notes:
        d.text((1100, y), n, font=F12, fill=SLATE)
        y += 22

    caption(d, W, H, "Labels are Neo4j node labels; properties are stored on nodes. Relationship types are first-class edges.")
    im.save(OUT / "fig3_graph_schema.png", "PNG")
    print("wrote fig3")


def fig_document_schema():
    W, H = 1600, 980
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((40, 28), "Figure 4.  Document-store schema variation (MongoDB reports collection)", font=FB18, fill=NAVY)

    docs = [
        (70, 90, 520, 900, TEAL, "Report A  ·  spearphish / GRU",
         [
             ('_id: "rpt-001"', False),
             ('title, source, date, tlp', False),
             ('confidence: "high"', False),
             ('actors: ["apt28","apt29"]', False),
             ('campaigns: ["dnc-2016"]', False),
             ('iocs: [ip, domain, ...]', False),
             ('body: <narrative>', False),
             ("", False),
             ("// fields unique to this doc", True),
             ('attribution: {', False),
             ('  country: "Russia",', False),
             ('  units: ["GRU 26165", ...],', False),
             ('  confidence: 0.82', False),
             ('}', False),
         ]),
        (560, 90, 1010, 900, COPPER, "Report B  ·  SolarWinds / SUNBURST",
         [
             ('_id: "rpt-002"', False),
             ('title, source, date, tlp', False),
             ('actors: ["apt29"]', False),
             ('malware: ["sunburst","teardrop"]', False),
             ('iocs: ["avsvmcloud.com"]', False),
             ('body: <narrative>', False),
             ("", False),
             ("// different nested shape", True),
             ('build_pipeline: {', False),
             ('  product: "Orion",', False),
             ('  vector: "trojanized MSI",', False),
             ('  signed: true', False),
             ('}', False),
             ('mitre: ["T1195","T1078"]', False),
         ]),
        (1050, 90, 1530, 900, RED, "Report C  ·  ICS / Industroyer",
         [
             ('_id: "rpt-004"', False),
             ('title, source, date, tlp', False),
             ('actors: ["sandworm"]', False),
             ('campaigns: ["industroyer"]', False),
             ('body: <narrative>', False),
             ("", False),
             ("// no iocs[] array at all", True),
             ('ics_protocols: [', False),
             ('  "IEC-104", "IEC-61850"', False),
             (']', False),
             ('outage_minutes: 75', False),
             ("", False),
             ("MongoDB stores A, B, and C", True),
             ("in one collection without", True),
             ("ALTER TABLE / migrations.", True),
         ]),
    ]
    for x0, y0, x1, y1, col, title, lines in docs:
        rounded(d, (x0, y0, x1, y1), 12, WHITE, col, 3)
        rounded(d, (x0, y0, x1, y0 + 52), 12, col, col, 0)
        d.rectangle((x0, y0 + 36, x1, y0 + 52), fill=col)
        center_text(d, (x0, y0, x1, y0 + 52), title, FB13, WHITE)
        y = y0 + 76
        for text, emph in lines:
            d.text((x0 + 28, y), text, font=FB12 if emph else F12, fill=col if emph else SLATE)
            y += 28

    caption(d, W, H, "Shared core fields coexist with report-specific nested objects — the document model’s reason for selection.")
    im.save(OUT / "fig4_document_schema.png", "PNG")
    print("wrote fig4")


if __name__ == "__main__":
    fig_architecture()
    fig_graphrag()
    fig_graph_schema()
    fig_document_schema()
    print("done", OUT)
