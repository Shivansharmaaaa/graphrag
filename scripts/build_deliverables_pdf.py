"""Build the project report PDF: progress report + API docs + database dump notes + screenshots.

Minimal hand-rolled Markdown -> ReportLab renderer (headers, tables, code fences,
bullet lists, bold/inline-code, links) so the three markdown files in this repo
render as one PDF without an external HTML-to-PDF dependency.
"""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image, ListFlowable, ListItem, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "GraphRAG_CTI_Platform_Report.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1x", parent=styles["Heading1"], spaceBefore=18, spaceAfter=8,
                           textColor=colors.HexColor("#14304d")))
styles.add(ParagraphStyle("H2x", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6,
                           textColor=colors.HexColor("#1b4a75")))
styles.add(ParagraphStyle("H3x", parent=styles["Heading3"], spaceBefore=10, spaceAfter=4,
                           textColor=colors.HexColor("#26608f")))
styles.add(ParagraphStyle("H4x", parent=styles["Heading4"], spaceBefore=8, spaceAfter=3,
                           fontSize=10.5, textColor=colors.HexColor("#333")))
styles.add(ParagraphStyle("Body", parent=styles["BodyText"], spaceAfter=6, leading=14))
styles.add(ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8.5, leading=11,
                           textColor=colors.HexColor("#555")))
styles.add(ParagraphStyle("Codex", parent=styles["Code"], fontSize=7.6, leading=9.6,
                           backColor=colors.HexColor("#f4f4f4")))

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # the built-in PDF fonts have no emoji glyphs: both marks would render as the same box
    text = text.replace("✅", "Yes").replace("❌", "No")
    text = LINK.sub(r'<link href="\2" color="#1b4a75">\1</link>', text)
    text = BOLD.sub(r"<b>\1</b>", text)
    text = INLINE_CODE.sub(r'<font face="Courier" size="8.5" color="#a3312a">\1</font>', text)
    return text


def parse_table(lines: list[str], i: int):
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        row = lines[i].strip()
        if not re.match(r"^\|[\s:\-|]+\|$", row):
            cells = [c.strip() for c in row.strip("|").split("|")]
            rows.append(cells)
        i += 1
    return rows, i


def md_to_flowables(md_path: Path, image_base: Path | None = None):
    lines = md_path.read_text().splitlines()
    flow = []
    i = 0
    in_code = False
    code_buf: list[str] = []
    list_buf: list[str] = []

    def flush_list():
        nonlocal list_buf
        if list_buf:
            items = [ListItem(Paragraph(inline(x), styles["Body"]), leftIndent=12) for x in list_buf]
            flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))
            list_buf = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                flush_list()
                flow.append(Preformatted("\n".join(code_buf), styles["Codex"]))
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if stripped.startswith("|"):
            flush_list()
            rows, i = parse_table(lines, i)
            if rows:
                data = [[Paragraph(inline(c), styles["Small"]) for c in r] for r in rows]
                ncols = max(len(r) for r in rows)
                colw = (6.6 * inch) / ncols
                t = Table(data, colWidths=[colw] * ncols, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7eef5")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbb")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                flow.append(t)
                flow.append(Spacer(1, 8))
            continue

        if stripped.startswith("#### "):
            flush_list(); flow.append(Paragraph(inline(stripped[5:]), styles["H4x"])); i += 1; continue
        if stripped.startswith("### "):
            flush_list(); flow.append(Paragraph(inline(stripped[4:]), styles["H3x"])); i += 1; continue
        if stripped.startswith("## "):
            flush_list(); flow.append(Paragraph(inline(stripped[3:]), styles["H2x"])); i += 1; continue
        if stripped.startswith("# "):
            flush_list(); flow.append(Paragraph(inline(stripped[2:]), styles["H1x"])); i += 1; continue

        if stripped.startswith("---"):
            flush_list(); flow.append(Spacer(1, 4)); i += 1; continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            list_buf.append(stripped[2:])
            i += 1
            continue

        if not stripped:
            flush_list()
            flow.append(Spacer(1, 4))
            i += 1
            continue

        flush_list()
        flow.append(Paragraph(inline(stripped), styles["Body"]))
        i += 1

    flush_list()
    return flow


def title_page():
    center = lambda name, **kw: ParagraphStyle(name, parent=styles["BodyText"], alignment=1, **kw)
    flow = [Spacer(1, 1.3 * inch)]
    flow.append(Paragraph("GraphRAG-Powered Cyber Threat Intelligence Platform", styles["Title"]))
    flow.append(Paragraph("A Multi-Model NoSQL Approach", ParagraphStyle(
        "sub", parent=styles["Heading2"], alignment=1, textColor=colors.HexColor("#555"))))
    flow.append(Spacer(1, 0.5 * inch))
    flow.append(Paragraph("Submitted by", center("bytag", fontSize=11, textColor=colors.HexColor("#666"))))
    flow.append(Spacer(1, 0.08 * inch))
    for name in ["Shivansh Sharma — 23BCE0254", "Himali Sharma — 23BCE0317", "Aayush Sinha — 23BCE0558"]:
        flow.append(Paragraph(name, center("name", fontSize=13)))
    flow.append(Spacer(1, 0.35 * inch))
    flow.append(Paragraph("VIT Vellore", center("inst", fontSize=12)))
    flow.append(Paragraph("Guide: Dr. Lydia Jane G", center("guide", fontSize=11, textColor=colors.HexColor("#555"))))
    flow.append(Spacer(1, 0.6 * inch))
    flow.append(Paragraph(
        'https://github.com/Shivansharmaaaa/graphrag',
        center("repo", fontSize=11, textColor=colors.HexColor("#1b4a75"))))
    flow.append(Spacer(1, 0.2 * inch))
    flow.append(Paragraph("September 2026 · results updated October 2026", center("date", fontSize=10, textColor=colors.HexColor("#888"))))
    flow.append(PageBreak())
    return flow


def screenshots_section():
    shots = [
        ("Login", "screenshots/login.png",
         "Demo-account login with TLP-clearance quick-fill buttons (analyst / junior / lead / admin)."),
        ("GraphRAG console — grounded answer with citations", "screenshots/graphrag_console_answer.png",
         "Acceptance test #6 (Mimikatz). The pipeline's grounding gate demoted this answer to "
         "retrieve-only after the LLM's first draft failed citation coverage — evidence panel "
         "shows graph edges [G#], chunks [C#], report [R:id] and live Redis IOC state [I#]."),
        ("Graph explorer — whole graph", "screenshots/graph_explorer.png",
         "73 nodes / 116 edges: ThreatActor, Campaign, Malware, Infrastructure, Technique, "
         "Indicator, Victim and Report nodes, colour-coded by label."),
        ("IOC blocklist — Redis enforcement plane", "screenshots/ioc_blocklist.png",
         "Live hot set (12 IOCs, 5 s refresh) with per-key TTL and severity, plus recently-expired "
         "IOCs that remain historically present in Neo4j/MongoDB (UC4)."),
    ]
    flow = [Paragraph("Screenshots", styles["H1x"]), Spacer(1, 6)]
    for title, rel, caption in shots:
        img_path = ROOT / "docs" / rel
        flow.append(Paragraph(title, styles["H3x"]))
        im = Image(str(img_path))
        max_w, max_h = 6.6 * inch, 8.5 * inch
        ratio = im.imageWidth / im.imageHeight
        w, h = max_w, max_w / ratio
        if h > max_h:
            h = max_h
            w = h * ratio
        im.drawWidth, im.drawHeight = w, h
        flow.append(im)
        flow.append(Paragraph(caption, styles["Small"]))
        flow.append(PageBreak())
    return flow


def build():
    doc = SimpleDocTemplate(
        str(OUT), pagesize=LETTER,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        title="GraphRAG CTI Platform — Project Report",
    )
    story = []
    story += title_page()

    story.append(Paragraph("1. Progress Report", styles["Title"]))
    story.append(Spacer(1, 10))
    story += md_to_flowables(ROOT / "reports" / "progress-report.md")
    story.append(PageBreak())

    story.append(Paragraph("2. API Documentation", styles["Title"]))
    story.append(Spacer(1, 10))
    story += md_to_flowables(ROOT / "docs" / "api.md")
    story.append(PageBreak())

    story.append(Paragraph("3. Database Dump Summary", styles["Title"]))
    story.append(Spacer(1, 10))
    story += md_to_flowables(ROOT / "database_dumps" / "README.md")
    story.append(PageBreak())

    story += screenshots_section()
    if isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    build()
