"""Evaluation harness (Section 2.4 / Review-III): gold-path correctness, latency SLOs (NFR2),
GraphRAG groundedness (citation coverage, NFR4), blocklist freshness and ingest consistency.

Run against a live, seeded stack:  cd backend && python -m scripts.evaluate
Writes eval_report.json next to where it is run. ``--check`` exits non-zero when a correctness
gate fails (gold recall, refusals, commodity caution, freshness, integrity); latency SLOs are
reported but not gated, since they depend on the host and the local LLM.
"""
from __future__ import annotations

import json
import statistics
import sys
import time

from app import blocklist, graph, graphrag, integrity, metrics, stores
from app.embeddings import embedder

ANALYST = {"username": "eval", "role": "analyst", "clearance": "AMBER", "display": "eval"}

# Gold graph facts every correct answer path must contain (Appendix A acceptance tests)
GOLD = [
    {"question": "Which threat actors share command-and-control infrastructure, and what malware was hosted there?",
     "must_edges": [("apt28", "USES_INFRA", "infra-vps-185"), ("sandworm", "USES_INFRA", "infra-vps-185")],
     "must_reports": ["rpt-001"]},
    {"question": "How is APT29 connected to supply-chain compromises, and which reports describe SUNBURST?",
     "must_edges": [("apt29", "USES", "sunburst")], "must_reports": ["rpt-002"]},
    {"question": "Who else uses Cobalt Strike besides FIN7, and do they share any domains?",
     "must_edges": [("fin7", "USES", "cobalt-strike"), ("scattered-spider", "USES", "cobalt-strike")],
     "must_reports": ["rpt-007"]},
    {"question": "What destructive campaigns is Sandworm responsible for, and does it share any infrastructure with APT28?",
     "must_edges": [("sandworm", "ATTRIBUTED_TO_CAMPAIGN", "notpetya"), ("apt28", "USES_INFRA", "infra-vps-185")],
     "must_reports": ["rpt-003"]},
    {"question": "Find activity similar to spearphishing against government and political organizations.",
     "must_edges": [], "must_reports": ["rpt-001"]},
    {"question": "Why is Mimikatz a weak attribution signal, and which actors still use it?",
     "must_edges": [("apt28", "USES", "mimikatz"), ("fin7", "USES", "mimikatz")],
     "must_reports": ["rpt-010"], "must_caution": True},
]


def pct(values, p):
    v = sorted(values)
    return round(v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))], 2) if v else None


def bench(fn, n):
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def main() -> dict:
    stores.connect()
    embedder.load()
    report: dict = {"ts": int(time.time())}

    # ---- NFR2 latency ------------------------------------------------------------
    redis_ms = bench(lambda: blocklist.lookup("ip", "185.86.77.12"), 500)
    hop_ms = {h: bench(lambda h=h: graph.neighbourhood("apt28", h), 30) for h in (1, 2, 3)}
    report["latency"] = {
        "redis_get_p99_ms": pct(redis_ms, 99), "redis_slo_p99_lt_5ms": pct(redis_ms, 99) < 5,
        **{f"graph_{h}hop_p95_ms": pct(v, 95) for h, v in hop_ms.items()},
        "graph_slo_p95_lt_500ms": all(pct(v, 95) < 500 for v in hop_ms.values()),
    }

    # ---- gold paths + groundedness ----------------------------------------------
    rows, rag_ms = [], []
    for g in GOLD:
        res = graphrag.ask(g["question"], ANALYST, max_hops=2, use_llm=True)
        rag_ms.append(res["latency_ms"]["total"])
        edges = {(e["source"], e["type"], e["target"]) for e in res["evidence"]["graph"]["edges"]}
        docs = {d["_id"] for d in res["evidence"]["documents"]}
        hit_e = [e for e in g["must_edges"] if e in edges]
        hit_r = [r for r in g["must_reports"] if r in docs]
        row = {
            "question": g["question"], "mode": res["mode"],
            "gold_edges_recalled": f"{len(hit_e)}/{len(g['must_edges'])}",
            "gold_reports_recalled": f"{len(hit_r)}/{len(g['must_reports'])}",
            "citation_coverage": res["citation_coverage"], "refused": res["refused"],
            "latency_ms": res["latency_ms"]["total"],
        }
        if g.get("must_caution"):
            row["commodity_caution_present"] = bool(res["evidence"]["hub_notes"])
        rows.append(row)
    report["graphrag"] = {
        "questions": rows,
        "mean_citation_coverage": round(statistics.mean(r["citation_coverage"] for r in rows), 3),
        "gold_edge_recall": round(sum(int(r["gold_edges_recalled"].split("/")[0]) for r in rows)
                                  / max(1, sum(int(r["gold_edges_recalled"].split("/")[1]) for r in rows)), 3),
        "gold_report_recall": round(sum(int(r["gold_reports_recalled"].split("/")[0]) for r in rows)
                                    / max(1, sum(int(r["gold_reports_recalled"].split("/")[1]) for r in rows)), 3),
        "p95_ms": pct(rag_ms, 95), "slo_p95_lt_15s": pct(rag_ms, 95) < 15000,
    }

    # ---- blocklist freshness (UC4) -----------------------------------------------
    blocklist.publish("domain", "eval-expiry-probe.example", 2, "low", published_by="eval")
    live_before = blocklist.lookup("domain", "eval-expiry-probe.example")["blocked"]
    time.sleep(3)
    live_after = blocklist.lookup("domain", "eval-expiry-probe.example")["blocked"]
    report["blocklist_freshness"] = {"live_before_expiry": live_before, "live_after_expiry": live_after,
                                     "ok": live_before and not live_after}

    # ---- ingest consistency (Section 8.5) ---------------------------------------
    report["integrity"] = integrity.check()
    report["process_latency_summary"] = metrics.summary()
    return report


def failed_gates(r: dict) -> list[str]:
    g = r["graphrag"]
    fails = [f"gold edge recall {g['gold_edge_recall']} < 1.0"] if g["gold_edge_recall"] < 1 else []
    if g["gold_report_recall"] < 1:
        fails.append(f"gold report recall {g['gold_report_recall']} < 1.0")
    fails += [f"refused: {q['question']}" for q in g["questions"] if q["refused"]]
    fails += [f"no commodity caution: {q['question']}" for q in g["questions"]
              if q.get("commodity_caution_present") is False]
    if not r["blocklist_freshness"]["ok"]:
        fails.append("blocklist expiry probe failed")
    if not r["integrity"]["ok"]:  # informational rules do not affect integrity's own verdict
        fails.append("integrity: " + "; ".join(x["rule"] for x in r["integrity"]["rules"] if not x["ok"]))
    return fails


if __name__ == "__main__":
    r = main()
    with open("eval_report.json", "w") as f:
        json.dump(r, f, indent=2, default=str)
    print(json.dumps({k: v for k, v in r.items() if k not in ("process_latency_summary",)}, indent=2, default=str))
    if "--check" in sys.argv[1:]:
        fails = failed_gates(r)
        print("\n".join(["", "FAILED GATES:", *fails] if fails else ["", "all correctness gates passed"]))
        sys.exit(1 if fails else 0)
