#!/usr/bin/env python3
"""Performance charts for the Review-III report and slides, from review3/performance/*.json.

    pip install matplotlib==3.9.2 && python review3/make_charts.py

Light print palette: the validated reference categorical slots in fixed order, each series
direct-labelled with its own marker (three slots are below 3:1 on the surface, so identity
never relies on colour alone), recessive grid, one y-axis per panel.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

HERE = Path(__file__).parent
PERF = HERE / "performance"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARKERS = ["o", "s", "D", "^", "v", "P", "X", "*"]

plt.rcParams.update({
    "font.family": "Arial", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "xtick.color": INK2, "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "legend.fontsize": 8.5,
})

R = json.loads((PERF / "benchmark_results.json").read_text())
B = json.loads((PERF / "benchmark_baseline_before_fixes.json").read_text())
L = json.loads((PERF / "llm_latency_runs.json").read_text())


def ms_fmt(v, _=None):
    if v >= 1000:
        return f"{v / 1000:.3g} s"
    return f"{v:.3g} ms" if v >= 1 else f"{v:.2g} ms"


def log_ms_axis(axis, values=None):
    """Log axis: decade ticks over wide ranges, 1-2-5 ticks when a range is too short for that."""
    wide = values is not None and max(values) / max(min(values), 1e-9) > 300
    axis.set_major_locator(LogLocator(base=10, subs=(1,) if wide else (1, 2, 5)))
    axis.set_minor_formatter(NullFormatter())
    axis.set_major_formatter(FuncFormatter(ms_fmt))


BOX = {"boxstyle": "square,pad=0.15", "facecolor": SURFACE, "edgecolor": "none"}


def line(ax, xs, ys, i, label, end_label=True, dashed=False, dy=0):
    ax.plot(xs, ys, color=S[i], lw=1.8, marker=MARKERS[i], ms=5.5, ls="--" if dashed else "-",
            markeredgecolor=SURFACE, markeredgewidth=0.8, label=label, zorder=3)
    if end_label:
        ax.annotate(label, (xs[-1], ys[-1]), xytext=(6, dy), textcoords="offset points",
                    va="center", fontsize=8, color=INK)


def save(fig, name):
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


rows, base = R["scale"]["rows"], B["scale"]["rows"]
nodes = [r["nodes"] for r in rows]


# ------------------------------------------------------------------ 1. scalability before / after
def chart_scale_fix():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    panels = [("Entity linking, median", lambda r: r["graphrag_retrieve_only"]["channels"]["linking"]["p50"]),
              ("GraphRAG retrieval, median", lambda r: r["graphrag_retrieve_only"]["total"]["p50"]),
              ("GraphRAG retrieval, p95", lambda r: r["graphrag_retrieve_only"]["total"]["p95"])]
    for ax, (title, f) in zip(axes, panels):
        before, after = [f(r) for r in base], [max(f(r), 0.01) for r in rows]
        line(ax, [r["nodes"] for r in base], before, 1, "before", dy=0)
        line(ax, nodes, after, 0, "after", dy=0)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(title, fontsize=9)
        log_ms_axis(ax.yaxis, before + after)
        ax.set_xlabel("graph nodes (corpus 1× → 200×)")
        ax.set_xlim(right=max(nodes) * 4)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, ["before the fixes", "after the fixes"], loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.05))
    fig.tight_layout(rect=(0, 0.06, 1, 1), w_pad=1.2)
    save(fig, "chart_scale_fix.png")


# ------------------------------------------------------------------ 2. per-store scaling (after)
def chart_scale_stores():
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    series = [("Neo4j 2-hop neighbourhood", lambda r: r["neo4j"]["neighbourhood_2hop"]["p95"]),
              ("MongoDB reports by actor", lambda r: r["mongodb"]["list_by_actor"]["p95"]),
              ("Qdrant k-NN (k=6, TLP filter)", lambda r: r["qdrant"]["knn_k6_tlp_filter"]["p95"]),
              ("Redis blocklist GET", lambda r: r["redis"]["blocklist_get"]["p95"]),
              ("Entity linking", lambda r: r["graphrag_retrieve_only"]["channels"]["linking"]["p95"])]
    for i, (lab, f) in enumerate(series):
        line(ax, nodes, [max(f(r), 0.01) for r in rows], i, lab)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(ms_fmt))
    ax.set_xlabel("graph nodes (corpus 1× → 200×)")
    ax.set_ylabel("p95 latency")
    ax.set_xlim(right=max(nodes) * 9)
    log_ms_axis(ax.yaxis)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    save(fig, "chart_scale_stores.png")


# ------------------------------------------------------------------ 3. redis key-count scaling
def chart_redis():
    rr = R["redis"]["rows"]
    keys = [r["keys"] for r in rr]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    line(ax, keys, [r["get_hit"]["p99"] for r in rr], 0, "GET + TTL, p99 (enforcement path)")
    line(ax, keys, [r["full_scan_ms"] for r in rr], 1, "SCAN whole keyspace (non-key lookup)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(ms_fmt))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_xlabel("IOC keys in Redis")
    ax.set_xlim(right=max(keys) * 12)
    ax.legend(loc="upper left")
    save(fig, "chart_redis.png")


# ------------------------------------------------------------------ 4. index ablations
def chart_indexes():
    m, n = R["mongo"], R["neo4j"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw={"width_ratios": [1.6, 1]})
    qs = [("by_actor", "reports by actor"), ("by_ioc", "reports citing an IOC"), ("tlp_recent_50", "50 newest, TLP ≤ GREEN")]
    y = range(len(qs))
    for k, (phase, lab, dy) in enumerate((("no_index", "no secondary index", -0.19),
                                          ("production_indexes", "production indexes", 0.19))):
        vals = [m[phase][q]["latency"]["p50"] for q, _ in qs]
        a1.barh([i + dy for i in y], vals, height=0.34, color=S[1 - k], label=lab, zorder=3)
        for i, (q, _) in enumerate(qs):
            a1.annotate(f"{ms_fmt(vals[i])} · {m[phase][q]['docs_examined']:,} docs read",
                        (vals[i], i + dy), xytext=(4, 0), textcoords="offset points", va="center", fontsize=7.5, color=INK)
    a1.set_yticks(list(y), [lab for _, lab in qs])
    a1.invert_yaxis()
    a1.set_xscale("log")
    a1.xaxis.set_major_formatter(FuncFormatter(ms_fmt))
    a1.set_xlim(right=max(m["no_index"][q]["latency"]["p50"] for q, _ in qs) * 60)
    a1.set_title(f"MongoDB, {m['documents']:,} reports (median)", fontsize=9)
    h, lab = a1.get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=2, bbox_to_anchor=(0.32, -0.06))
    labs = ["label scan", "range index"]
    vals = [n["no_index"]["latency"]["p50"], n["range_index"]["latency"]["p50"]]
    hits = [n["no_index"]["db_hits"], n["range_index"]["db_hits"]]
    a2.barh([0, 1], vals, height=0.5, color=[S[1], S[0]], zorder=3)
    for i in range(2):
        a2.annotate(f"{ms_fmt(vals[i])} · {hits[i]:,} db hits", (vals[i], i), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=7.5, color=INK)
    a2.set_yticks([0, 1], labs)
    a2.invert_yaxis()
    a2.set_xscale("log")
    a2.xaxis.set_major_formatter(FuncFormatter(ms_fmt))
    a2.set_xlim(right=max(vals) * 60)
    a2.set_title(f"Neo4j lookup by value, {n['nodes']:,} nodes", fontsize=9)
    fig.tight_layout(rect=(0, 0.07, 1, 1), w_pad=1.5)
    save(fig, "chart_indexes.png")


# ------------------------------------------------------------------ 5. qdrant recall vs latency
def chart_qdrant():
    qr = R["qdrant"]["rows"]
    big = qr[-1]
    efs = (16, 64, 128)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.7))
    for i, (key, lab) in enumerate((("unfiltered", "unfiltered"), ("tlp_filter", "TLP payload filter"))):
        line(a1, list(efs), [big[key][f"hnsw_ef{ef}"]["recall_at_10"] for ef in efs], i, lab, end_label=False)
    a1.set_xscale("log", base=2)
    a1.set_xticks(list(efs), [str(e) for e in efs])
    a1.set_xlim(12, 180)
    a1.legend(loc="lower right")
    a1.set_xlabel("HNSW search breadth (ef)")
    a1.set_ylabel("recall@10 vs exact")
    a1.set_title(f"Recall, {big['points'] // 1000}k points", fontsize=9)
    pts = [r["points"] for r in qr]
    series = [("exact, unfiltered", "unfiltered", "exact"), ("HNSW ef=64, unfiltered", "unfiltered", "hnsw_ef64"),
              ("exact, TLP filter", "tlp_filter", "exact"), ("HNSW ef=64, TLP filter", "tlp_filter", "hnsw_ef64")]
    for i, (lab, key, mode) in enumerate(series):
        line(a2, pts, [r[key][mode]["p50"] for r in qr], i, lab, end_label=False, dashed=mode == "exact")
    a2.set_xticks(pts, [f"{p // 1000}k" for p in pts])
    a2.set_xlabel("points in the collection")
    a2.set_title("Median query latency (k = 10)", fontsize=9)
    a2.yaxis.set_major_formatter(FuncFormatter(ms_fmt))
    a2.set_ylim(bottom=0)
    a2.legend(loc="upper left", fontsize=7.5)
    fig.tight_layout(w_pad=1.5)
    save(fig, "chart_qdrant.png")


# ------------------------------------------------------------------ 6. API under load
def chart_load():
    ld = {k: v for k, v in R["load"].items() if isinstance(v, list)}
    names = {"enforce_check": "enforcement check (Redis)", "graph_shared_infrastructure": "shared-infrastructure query (Neo4j)",
             "graphrag_retrieve_only": "GraphRAG, retrieve-only"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.7))
    for i, (k, pts) in enumerate(ld.items()):
        cs = [p["concurrency"] for p in pts]
        line(a1, cs, [p["throughput_rps"] for p in pts], i, names[k], end_label=False)
        line(a2, cs, [p["p95"] for p in pts], i, names[k], end_label=False)
    for ax, t, yl in ((a1, "Throughput", "requests / s"), (a2, "Tail latency (p95)", None)):
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks([1, 4, 16, 64], ["1", "4", "16", "64"])
        ax.set_xlabel("concurrent clients")
        ax.set_title(t, fontsize=9)
        if yl:
            ax.set_ylabel(yl)
    a2.yaxis.set_major_formatter(FuncFormatter(ms_fmt))
    h, lab = a1.get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.07, 1, 1), w_pad=1.5)
    save(fig, "chart_load.png")


# ------------------------------------------------------------------ 7. LLM latency vs SLO
def chart_llm():
    runs = L["runs"]
    labs = [f"{r['label']}\n{r['model']}" for r in runs]
    vals = [r["p95_s"] for r in runs]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.barh(range(len(runs)), vals, height=0.58, color=S[0], zorder=3)
    for i, (v, r) in enumerate(zip(vals, runs)):
        ax.annotate(f"{v:g} s · coverage {r['mean_citation_coverage']:.2f}", (max(v, L["slo_p95_s"]), i),
                    xytext=(5, 0), textcoords="offset points", va="center", fontsize=7.5, color=INK, bbox=BOX, zorder=4)
    ax.axvline(L["slo_p95_s"], color=INK2, ls="--", lw=1, zorder=2)
    ax.text(L["slo_p95_s"] + 0.6, -0.72, "NFR2 target: p95 < 15 s", fontsize=8, color=INK2)
    ax.set_yticks(range(len(runs)), labs, fontsize=8)
    ax.set_xlabel("GraphRAG end-to-end p95, six Appendix-A questions (seconds)")
    ax.set_xlim(0, max(vals) * 1.45)
    ax.set_ylim(len(runs) - 0.5, -0.95)
    ax.grid(axis="y", visible=False)
    save(fig, "chart_llm.png")


# ------------------------------------------------------------------ 8. ingest throughput
def chart_ingest():
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    line(ax, [r["nodes"] for r in base], [r["ingest"]["reports_per_s"] for r in base], 1, "before")
    line(ax, nodes, [r["ingest"]["reports_per_s"] for r in rows], 0, "after")
    ax.set_xscale("log")
    ax.set_xlabel("graph nodes (corpus 1× → 200×)")
    ax.set_ylabel("reports / s (full fan-out)")
    ax.set_ylim(bottom=0)
    ax.set_xlim(right=max(nodes) * 4)
    ax.legend(["before the fixes", "after the fixes"], loc="upper left")
    save(fig, "chart_ingest.png")


if __name__ == "__main__":
    chart_scale_fix()
    chart_scale_stores()
    chart_redis()
    chart_indexes()
    chart_qdrant()
    chart_load()
    chart_llm()
    chart_ingest()
