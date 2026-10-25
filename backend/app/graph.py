"""Neo4j Cypher library (FR2) — the canonical relationship store.

Every function returns plain dicts; subgraphs use {"nodes": [...], "edges": [...]}
so the console can draw them and GraphRAG can cite each edge.
"""
from __future__ import annotations

from app import stores
from app.config import settings
from app.metrics import timed

LABELS = ["ThreatActor", "Campaign", "Malware", "Infrastructure", "Technique",
          "Indicator", "Victim", "Report"]
REL_TYPES = ["ATTRIBUTED_TO_CAMPAIGN", "USES", "USES_MALWARE", "USES_INFRA", "HOSTS",
             "EMPLOYS", "IMPLEMENTS", "HAS_IOC", "OBSERVED_AS", "TARGETS", "MENTIONED_IN",
             "SHARES_UNIT"]


# ------------------------------------------------------------------ helpers
def _label(node) -> str:
    labels = list(node.labels)
    return labels[0] if labels else "Node"


def display_name(props: dict) -> str:
    return props.get("name") or props.get("value") or props.get("title") or props.get("id")


def node_dict(node) -> dict:
    p = dict(node)
    return {"id": p.get("id"), "label": _label(node), "name": display_name(p), "props": p}


def _rel_dict(rel) -> dict:
    return {"source": rel.start_node["id"], "target": rel.end_node["id"], "type": rel.type,
            "props": dict(rel)}


def _collect(records, *path_keys) -> dict:
    nodes, edges = {}, {}
    for rec in records:
        for k in path_keys:
            p = rec.get(k)
            if p is None:
                continue
            for n in p.nodes:
                nodes[n["id"]] = node_dict(n)
            for r in p.relationships:
                e = _rel_dict(r)
                edges[(e["source"], e["type"], e["target"])] = e
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def _run(cypher: str, sink: dict | None = None, **params):
    with timed("neo4j", sink):
        with stores.neo4j_session() as s:
            return list(s.run(cypher, **params))


# ------------------------------------------------------------------ lookup
def stats() -> dict:
    labels = {r["label"]: r["c"] for r in _run(
        "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c")}
    rels = {r["t"]: r["c"] for r in _run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c")}
    return {"labels": labels, "relationships": rels}


def search(q: str, limit: int = 20, label: str | None = None) -> list[dict]:
    q = q.strip().lower()
    if label and label not in LABELS:
        return []
    recs = _run(
        """
        MATCH (n) WHERE NOT n:Report AND ($label IS NULL OR $label IN labels(n)) AND (
              toLower(coalesce(n.name,'')) CONTAINS $q OR toLower(coalesce(n.id,'')) CONTAINS $q
           OR toLower(coalesce(n.value,'')) CONTAINS $q
           OR any(a IN coalesce(n.aliases, []) WHERE toLower(a) CONTAINS $q))
        RETURN n ORDER BY n.name LIMIT $limit
        """, q=q, limit=limit, label=label)
    return [node_dict(r["n"]) for r in recs]


def _match_by_id(var: str, labels=LABELS) -> str:
    """`MATCH (n {id:$id})` has no label, so Neo4j scans every node; a UNION of labelled
    matches uses each label's id constraint (an index seek) instead."""
    return f"CALL ({var}) {{ " + " UNION ALL ".join(
        f"MATCH (n:{lab} {{id: {var}}}) RETURN n" for lab in labels) + " }"


def get_node(node_id: str) -> dict | None:
    recs = _run(
        f"""
        WITH $id AS id {_match_by_id("id")}
        WITH n LIMIT 1
        OPTIONAL MATCH (n)-[r]-()
        RETURN n, count(r) AS degree
        """, id=node_id)
    if not recs or recs[0]["n"] is None:
        return None
    d = node_dict(recs[0]["n"])
    d["degree"] = recs[0]["degree"]
    return d


def get_nodes(ids, sink: dict | None = None,
              labels=("ThreatActor", "Infrastructure", "Malware")) -> dict[str, dict]:
    """Batch lookup by id (one round trip, index seeks), keyed by id."""
    if not ids:
        return {}
    recs = _run(f"UNWIND $ids AS id {_match_by_id('id', labels)} RETURN n", sink, ids=list(ids))
    return {d["id"]: d for d in (node_dict(r["n"]) for r in recs)}


def gazetteer() -> list[dict]:
    """Names/aliases/values for entity linking in GraphRAG and ingest."""
    recs = _run(
        """
        MATCH (n) WHERE n:ThreatActor OR n:Campaign OR n:Malware OR n:Technique
                     OR n:Infrastructure OR n:Victim OR n:Indicator
        RETURN n.id AS id, labels(n)[0] AS label, n.name AS name,
               coalesce(n.aliases, []) AS aliases, n.value AS value
        """)
    return [dict(r) for r in recs]


def hub_ids() -> dict[str, int]:
    """Commodity tools: Malware nodes used by many actors (weak attribution)."""
    recs = _run(
        """
        MATCH (m:Malware)<-[:USES]-(a:ThreatActor)
        WITH m, count(DISTINCT a) AS users WHERE users >= $t
        RETURN m.id AS id, users
        """, t=settings.hub_degree_threshold)
    return {r["id"]: r["users"] for r in recs}


def existing_report_ids(ids: list[str]) -> set[str]:
    if not ids:
        return set()
    return {r["id"] for r in _run("MATCH (r:Report) WHERE r.id IN $ids RETURN r.id AS id", ids=ids)}


# ------------------------------------------------------------------ traversals
def neighbourhood(node_id: str, hops: int = 2, limit: int = 150, sink: dict | None = None) -> dict:
    """1–3 hop expansion with a hub budget: paths may END at a hub (Mimikatz, Cobalt Strike,
    a Report) but never traverse THROUGH one, so dense hubs cannot explode the subgraph."""
    hops = max(1, min(int(hops), settings.max_hops))
    recs = _run(
        f"""
        MATCH p=(s {{id:$id}})-[*1..{hops}]-(n)
        WHERE all(x IN nodes(p)[1..-1] WHERE NOT x:Report
                   AND COUNT {{ (x)--() }} <= $maxdeg)
        RETURN p LIMIT $limit
        """, sink, id=node_id, maxdeg=settings.max_neighbours_per_node, limit=limit)
    return _collect(recs, "p")


def overview(limit: int = 400, include_reports: bool = False) -> dict:
    where = "" if include_reports else "WHERE NOT a:Report AND NOT b:Report"
    recs = _run(f"MATCH p=(a)-[r]->(b) {where} RETURN p LIMIT $limit", limit=limit)
    return _collect(recs, "p")


def shared_infrastructure(actor_id: str | None = None, sink: dict | None = None,
                          limit: int = 1000) -> list[dict]:
    """UC1 / flagship query: actors sharing an Infrastructure node via USES_INFRA.
    Pairs backed by a shared report come first; `limit` bounds the all-actors form."""
    recs = _run(
        """
        MATCH (a:ThreatActor)-[:USES_INFRA]->(i:Infrastructure)<-[:USES_INFRA]-(b:ThreatActor)
        WHERE ($id IS NULL AND a.id < b.id) OR a.id = $id
        OPTIONAL MATCH (i)-[:HOSTS]->(m:Malware)
        OPTIONAL MATCH (a)-[:MENTIONED_IN]->(r:Report)<-[:MENTIONED_IN]-(b)
        RETURN a.id AS actor, a.name AS actor_name, b.id AS other, b.name AS other_name,
               i.id AS infra_id, i.value AS infra, i.kind AS kind,
               collect(DISTINCT m.name) AS hosted_malware,
               collect(DISTINCT r.id) AS reports
        ORDER BY size(reports) DESC, actor, other
        LIMIT $limit
        """, sink, id=actor_id, limit=limit)
    return [dict(r) for r in recs]


def shared_tooling(malware_id: str | None = None, actor_id: str | None = None,
                   sink: dict | None = None) -> list[dict]:
    """Actors sharing a Malware/tool node. Hubs are flagged as weak attribution (UC3)."""
    recs = _run(
        """
        MATCH (a:ThreatActor)-[:USES]->(m:Malware)<-[:USES]-(b:ThreatActor)
        WHERE a.id < b.id OR a.id = $actor
        WITH a, b, m WHERE ($mal IS NULL OR m.id = $mal) AND ($actor IS NULL OR a.id = $actor)
        WITH a, b, m, COUNT { (m)<-[:USES]-(:ThreatActor) } AS users
        RETURN a.id AS actor, a.name AS actor_name, b.id AS other, b.name AS other_name,
               m.id AS malware_id, m.name AS malware, m.kind AS kind, users,
               users >= $t AS commodity_hub
        ORDER BY commodity_hub, malware
        """, sink, mal=malware_id, actor=actor_id, t=settings.hub_degree_threshold)
    return [dict(r) for r in recs]


def tool_users(malware_id: str, sink: dict | None = None) -> dict:
    recs = _run(
        """
        MATCH (m:Malware {id:$id})
        OPTIONAL MATCH (a:ThreatActor)-[:USES]->(m)
        OPTIONAL MATCH (a)-[:ATTRIBUTED_TO_CAMPAIGN]->(c:Campaign)-[:TARGETS]->(v:Victim)
        OPTIONAL MATCH (a)-[:USES_INFRA]->(i:Infrastructure)
        RETURN m.name AS malware, a.id AS actor, a.name AS actor_name,
               collect(DISTINCT v.sector) AS victim_sectors, collect(DISTINCT i.value) AS infra
        """, sink, id=malware_id)
    users = [dict(r) for r in recs if r["actor"]]
    return {"malware_id": malware_id, "users": users,
            "commodity_hub": len(users) >= settings.hub_degree_threshold}


def common_victims(actor_id: str | None = None, sink: dict | None = None) -> list[dict]:
    recs = _run(
        """
        MATCH (a:ThreatActor)-[:ATTRIBUTED_TO_CAMPAIGN|TARGETS*1..2]->(v:Victim)
              <-[:ATTRIBUTED_TO_CAMPAIGN|TARGETS*1..2]-(b:ThreatActor)
        WHERE a <> b AND (($id IS NULL AND a.id < b.id) OR a.id = $id)
        RETURN a.id AS actor, a.name AS actor_name, b.id AS other, b.name AS other_name,
               collect(DISTINCT v.name) AS victims, collect(DISTINCT v.sector) AS sectors
        """, sink, id=actor_id)
    return [dict(r) for r in recs]


def shortest_path(src: str, dst: str, max_len: int = 4) -> dict:
    max_len = max(1, min(max_len, 6))
    recs = _run(
        f"""
        MATCH (a {{id:$a}}), (b {{id:$b}})
        MATCH p = shortestPath((a)-[*..{max_len}]-(b))
        RETURN p
        """, a=src, b=dst)
    return _collect(recs, "p")


def indicator_history(value: str) -> dict:
    """UC4: after a Redis key expires, the graph still holds HAS_IOC / OBSERVED_AS history."""
    recs = _run(
        """
        MATCH (x) WHERE (x:Indicator OR x:Infrastructure) AND x.value = $v
        OPTIONAL MATCH p=(x)-[*1..2]-(n) WHERE NOT n:Report
        RETURN p
        """, v=value)
    return _collect(recs, "p")


def subgraph_for_entities(ids: list[str], hops: int = 2, sink: dict | None = None,
                          limit: int = 200) -> dict:
    """GraphRAG graph channel: expand from linked entities, biased toward
    USES_INFRA / HOSTS / MENTIONED_IN (Section 7.1), with the hub budget."""
    if not ids:
        return {"nodes": [], "edges": []}
    hops = max(1, min(int(hops), settings.max_hops))
    recs = _run(
        f"""
        MATCH p=(s)-[rels*1..{hops}]-(n)
        WHERE s.id IN $ids
          AND all(x IN nodes(p)[1..-1] WHERE NOT x:Report AND COUNT {{ (x)--() }} <= $maxdeg)
        WITH p, reduce(score = 0, r IN relationships(p) |
             score + CASE type(r) WHEN 'USES_INFRA' THEN 3 WHEN 'HOSTS' THEN 3
                                  WHEN 'MENTIONED_IN' THEN 2 WHEN 'SHARES_UNIT' THEN 2
                                  ELSE 1 END) * 1.0 / length(p) AS bias
        RETURN p ORDER BY bias DESC, length(p) ASC LIMIT $limit
        """, sink, ids=ids, maxdeg=settings.max_neighbours_per_node, limit=limit)
    return _collect(recs, "p")


def edges_exist(edges: list[dict]) -> list[bool]:
    """Replay/audit (FR10): does each cited edge still exist?"""
    if not edges:
        return []
    recs = _run(
        """
        UNWIND range(0, size($edges)-1) AS i
        WITH i, $edges[i] AS e
        OPTIONAL MATCH (a {id:e.source})-[r]->(b {id:e.target}) WHERE type(r) = e.type
        RETURN i, count(r) > 0 AS ok ORDER BY i
        """, edges=[{"source": e["source"], "target": e["target"], "type": e["type"]}
                    for e in edges])
    return [r["ok"] for r in recs]


# ------------------------------------------------------------------ writes (ingest only)
def merge_node(s, label: str, props: dict) -> None:
    assert label in LABELS
    if label == "Indicator":
        s.run(
            "MERGE (n:Indicator {type:$type, value:$value}) "
            "SET n.id = 'ioc:' + $type + ':' + $value, n.severity = coalesce($severity, n.severity)",
            type=props["type"], value=props["value"], severity=props.get("severity"))
        return
    clean = {k: v for k, v in props.items() if v is not None and k != "id"}
    s.run(f"MERGE (n:{label} {{id:$id}}) SET n += $props", id=props["id"], props=clean)


def merge_edge(s, src_label: str, src_id: str, rel: str, dst_label: str, dst_id: str) -> None:
    assert rel in REL_TYPES and src_label in LABELS and dst_label in LABELS
    s.run(
        f"MATCH (a:{src_label} {{id:$a}}), (b:{dst_label} {{id:$b}}) MERGE (a)-[:{rel}]->(b)",
        a=src_id, b=dst_id)
