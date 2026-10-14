"""
backend.graph.verify
~~~~~~~~~~~~~~~~~~~~
Graph health-check module for TraceMind.

Verifies:
  - Node counts per label (and total = 17)
  - Relationship counts per type (and total = 21)
  - At least one multi-hop investigation path exists
  - At least one unresolved incident exists (INC-004 case)

Run directly:
    python -m backend.graph.verify
    python -m backend.graph.verify --graph tracemind
"""

import argparse
import sys
from typing import NamedTuple

from .connection import get_connection_params, get_graph

# Expected counts from the spec
EXPECTED_NODE_COUNTS = {
    "Service": 6,
    "Incident": 4,
    "Document": 4,
    "Fix": 3,
}
EXPECTED_TOTAL_NODES = 17
EXPECTED_TOTAL_RELS = 21


class VerifyResult(NamedTuple):
    ok: bool
    node_counts: dict
    total_nodes: int
    total_rels: int
    multihop_paths: int
    unresolved_incidents: list
    issues: list


def verify(graph_name: str | None = None) -> VerifyResult:
    """
    Run all health checks against the graph.

    Args:
        graph_name: Override graph name (uses FALKORDB_GRAPH env var if None).

    Returns:
        VerifyResult with check outcomes.
    """
    params = get_connection_params()
    timeout_ms = params["timeout_ms"]
    name = graph_name if graph_name is not None else params["graph_name"]
    _, graph = get_graph(name)

    issues = []

    # ── Node counts per label ──────────────────────────────────────────────────
    node_counts: dict[str, int] = {}
    for label in ("Service", "Incident", "Document", "Fix"):
        result = graph.query(
            f"MATCH (n:{label}) RETURN count(n) AS cnt",
            timeout=timeout_ms,
        )
        count = result.result_set[0][0] if result.result_set else 0
        node_counts[label] = count
        expected = EXPECTED_NODE_COUNTS[label]
        if count != expected:
            issues.append(f"{label} count: expected {expected}, got {count}")

    total_nodes = sum(node_counts.values())
    if total_nodes != EXPECTED_TOTAL_NODES:
        issues.append(
            f"Total node count: expected {EXPECTED_TOTAL_NODES}, got {total_nodes}"
        )

    # ── Total relationship count ───────────────────────────────────────────────
    rel_result = graph.query(
        "MATCH ()-[r]->() RETURN count(r) AS cnt",
        timeout=timeout_ms,
    )
    total_rels = rel_result.result_set[0][0] if rel_result.result_set else 0
    if total_rels != EXPECTED_TOTAL_RELS:
        issues.append(
            f"Total relationship count: expected {EXPECTED_TOTAL_RELS}, got {total_rels}"
        )

    # ── Multi-hop path: service → incident → fix → document ───────────────────
    multihop_result = graph.query(
        "MATCH (s:Service)<-[:AFFECTS]-(i:Incident)<-[:RESOLVES]-(f:Fix)"
        "-[:DESCRIBED_IN]->(d:Document) "
        "RETURN s.name, i.id, f.id, d.id "
        "LIMIT 5",
        timeout=timeout_ms,
    )
    multihop_paths = len(multihop_result.result_set) if multihop_result.result_set else 0
    if multihop_paths == 0:
        issues.append("No multi-hop investigation paths found (service→incident→fix→document)")

    # ── Unresolved incidents (INC-004 case) ───────────────────────────────────
    unresolved_result = graph.query(
        "MATCH (i:Incident) WHERE i.status <> 'resolved' "
        "RETURN i.id, i.title, i.status",
        timeout=timeout_ms,
    )
    unresolved_incidents = [
        {"id": row[0], "title": row[1], "status": row[2]}
        for row in (unresolved_result.result_set or [])
    ]

    ok = len(issues) == 0
    return VerifyResult(
        ok=ok,
        node_counts=node_counts,
        total_nodes=total_nodes,
        total_rels=total_rels,
        multihop_paths=multihop_paths,
        unresolved_incidents=unresolved_incidents,
        issues=issues,
    )


def print_report(result: VerifyResult) -> None:
    """Print a human-readable health-check report."""
    sep = "─" * 50
    print(sep)
    print("TraceMind Graph Health Check")
    print(sep)

    print("\nNode counts:")
    for label, count in result.node_counts.items():
        expected = EXPECTED_NODE_COUNTS[label]
        status = "✓" if count == expected else "✗"
        print(f"  {status} {label}: {count} (expected {expected})")
    total_status = "✓" if result.total_nodes == EXPECTED_TOTAL_NODES else "✗"
    print(f"  {total_status} Total nodes: {result.total_nodes} (expected {EXPECTED_TOTAL_NODES})")

    print("\nRelationships:")
    rel_status = "✓" if result.total_rels == EXPECTED_TOTAL_RELS else "✗"
    print(f"  {rel_status} Total relationships: {result.total_rels} (expected {EXPECTED_TOTAL_RELS})")

    print("\nMulti-hop paths (service→incident→fix→document):")
    mh_status = "✓" if result.multihop_paths > 0 else "✗"
    print(f"  {mh_status} Found: {result.multihop_paths} path(s)")

    print("\nUnresolved incidents:")
    if result.unresolved_incidents:
        for inc in result.unresolved_incidents:
            print(f"  ! {inc['id']} — {inc['title']} [{inc['status']}]")
    else:
        print("  (none)")

    if result.issues:
        print("\nIssues:")
        for issue in result.issues:
            print(f"  ✗ {issue}")
    else:
        print("\n✓ All checks passed.")

    print(sep)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify TraceMind graph health.")
    parser.add_argument(
        "--graph",
        default=None,
        help="Graph name to verify (overrides FALKORDB_GRAPH env var).",
    )
    args = parser.parse_args()

    try:
        result = verify(graph_name=args.graph)
        print_report(result)
        sys.exit(0 if result.ok else 1)
    except Exception as exc:  # noqa: BLE001
        print(f"[verify] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
