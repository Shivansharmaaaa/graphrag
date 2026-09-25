"""Cypher-export dump of the Neo4j graph (no APOC dependency).

Writes MERGE statements for every node (by label + all properties) and every
relationship (by type + all properties), so the graph can be rebuilt on any
neo4j 5.x instance with `cypher-shell < database_dumps/neo4j/graph_dump.cypher`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import stores  # noqa: E402


def _lit(v):
    return json.dumps(v)


def _props(d: dict) -> str:
    items = [f"{k}: {_lit(v)}" for k, v in d.items() if v is not None]
    return "{" + ", ".join(items) + "}"


def export(out_path: Path) -> None:
    stores.connect()
    lines = [
        "// Neo4j graph dump — rebuild with:",
        "//   cypher-shell -u neo4j -p <password> < graph_dump.cypher",
        "",
    ]
    with stores.neo4j_session() as s:
        nodes = s.run("MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props").data()
        rels = s.run(
            "MATCH (a)-[r]->(b) RETURN elementId(a) AS a, elementId(b) AS b, "
            "type(r) AS type, properties(r) AS props"
        ).data()

    lines.append(f"// {len(nodes)} nodes")
    for n in nodes:
        label = n["labels"][0] if n["labels"] else "Node"
        props = n["props"]
        key = "id" if "id" in props else ("value" if "value" in props else None)
        if key:
            match_prop = f"{{{key}: {_lit(props[key])}}}"
            lines.append(f"MERGE (n:{label} {match_prop}) SET n += {_props(props)};")
        else:
            lines.append(f"CREATE (n:{label} {_props(props)});")

    lines.append(f"\n// {len(rels)} relationships — matched by id/value since elementId() is not stable across restores")
    eid_to_node = {n["eid"]: n for n in nodes}
    for r in rels:
        a, b = eid_to_node.get(r["a"]), eid_to_node.get(r["b"])
        if not a or not b:
            continue
        a_key = "id" if "id" in a["props"] else "value"
        b_key = "id" if "id" in b["props"] else "value"
        if a_key not in a["props"] or b_key not in b["props"]:
            continue
        a_label, b_label = a["labels"][0], b["labels"][0]
        lines.append(
            f"MATCH (a:{a_label} {{{a_key}: {_lit(a['props'][a_key])}}}), "
            f"(b:{b_label} {{{b_key}: {_lit(b['props'][b_key])}}}) "
            f"MERGE (a)-[r:{r['type']}]->(b) SET r += {_props(r['props'])};"
        )

    out_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {out_path} ({len(nodes)} nodes, {len(rels)} relationships)")
    stores.close()


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "database_dumps" / "neo4j" / "graph_dump.cypher"
    out.parent.mkdir(parents=True, exist_ok=True)
    export(out)
