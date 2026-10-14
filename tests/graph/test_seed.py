"""
tests/graph/test_seed.py — Integration tests for backend.graph.seed.

Requires a live FalkorDB instance. Tests run against `tracemind_test` only,
via the `test_graph` fixture from conftest.py. The development graph is
never touched.

Mark: @pytest.mark.integration — skipped automatically if FalkorDB is down.
"""

import pytest

from backend.graph.seed import (
    DOCUMENTS,
    FIXES,
    INCIDENTS,
    SERVICES,
    SERVICE_DEPS,
    INCIDENT_AFFECTS,
    INCIDENT_DOCUMENTED_IN,
    FIX_RESOLVES,
    FIX_DESCRIBED_IN,
    seed_nodes,
    seed_relationships,
)
from backend.graph.schema import create_constraints

pytestmark = pytest.mark.integration

EXPECTED_TOTAL_NODES = 17
EXPECTED_TOTAL_RELS = 21


def _count_nodes(graph, label: str, timeout_ms: int = 5000) -> int:
    result = graph.query(
        f"MATCH (n:{label}) RETURN count(n) AS cnt", timeout=timeout_ms
    )
    return result.result_set[0][0] if result.result_set else 0


def _count_rels(graph, timeout_ms: int = 5000) -> int:
    result = graph.query(
        "MATCH ()-[r]->() RETURN count(r) AS cnt", timeout=timeout_ms
    )
    return result.result_set[0][0] if result.result_set else 0


class TestDemoDataConstants:
    """
    Pure unit tests (no FalkorDB) verifying the demo data arrays in seed.py
    have exactly the right counts from the spec.
    """

    def test_service_count(self):
        assert len(SERVICES) == 6

    def test_incident_count(self):
        assert len(INCIDENTS) == 4

    def test_document_count(self):
        assert len(DOCUMENTS) == 4

    def test_fix_count(self):
        assert len(FIXES) == 3

    def test_total_node_count(self):
        assert len(SERVICES) + len(INCIDENTS) + len(DOCUMENTS) + len(FIXES) == 17

    def test_depends_on_count(self):
        assert len(SERVICE_DEPS) == 7

    def test_affects_count(self):
        assert len(INCIDENT_AFFECTS) == 6

    def test_documented_in_count(self):
        assert len(INCIDENT_DOCUMENTED_IN) == 2

    def test_resolves_count(self):
        assert len(FIX_RESOLVES) == 3

    def test_described_in_count(self):
        assert len(FIX_DESCRIBED_IN) == 3

    def test_total_relationship_count(self):
        total = (
            len(SERVICE_DEPS)
            + len(INCIDENT_AFFECTS)
            + len(INCIDENT_DOCUMENTED_IN)
            + len(FIX_RESOLVES)
            + len(FIX_DESCRIBED_IN)
        )
        assert total == 21

    def test_inc004_not_in_fix_resolves(self):
        """INC-004 has no resolving fix — it is investigating."""
        resolved_incident_ids = {inc_id for _, inc_id in FIX_RESOLVES}
        assert "INC-004" not in resolved_incident_ids

    def test_inc004_status_is_investigating(self):
        inc004 = next(i for i in INCIDENTS if i["id"] == "INC-004")
        assert inc004["status"] == "investigating"

    def test_inc004_severity_is_sev1(self):
        inc004 = next(i for i in INCIDENTS if i["id"] == "INC-004")
        assert inc004["severity"] == "SEV1"

    def test_all_fix_ids_unique(self):
        ids = [f["id"] for f in FIXES]
        assert len(ids) == len(set(ids))

    def test_all_service_names_unique(self):
        names = [s["name"] for s in SERVICES]
        assert len(names) == len(set(names))

    def test_all_incident_ids_unique(self):
        ids = [i["id"] for i in INCIDENTS]
        assert len(ids) == len(set(ids))

    def test_all_document_ids_unique(self):
        ids = [d["id"] for d in DOCUMENTS]
        assert len(ids) == len(set(ids))


class TestSeedIntegration:
    """Integration tests — require live FalkorDB on tracemind_test graph."""

    def test_empty_graph_has_zero_nodes(self, test_graph):
        _, graph = test_graph
        assert _count_nodes(graph, "Service") == 0
        assert _count_nodes(graph, "Incident") == 0
        assert _count_nodes(graph, "Document") == 0
        assert _count_nodes(graph, "Fix") == 0

    def test_empty_graph_has_zero_relationships(self, test_graph):
        _, graph = test_graph
        assert _count_rels(graph) == 0

    def test_seed_creates_exact_node_counts(self, test_graph):
        client, graph = test_graph
        create_constraints(graph)
        seed_nodes(graph)

        assert _count_nodes(graph, "Service") == 6
        assert _count_nodes(graph, "Incident") == 4
        assert _count_nodes(graph, "Document") == 4
        assert _count_nodes(graph, "Fix") == 3

    def test_seed_creates_exact_total_nodes(self, test_graph):
        client, graph = test_graph
        create_constraints(graph)
        seed_nodes(graph)

        total = sum(
            _count_nodes(graph, label)
            for label in ("Service", "Incident", "Document", "Fix")
        )
        assert total == EXPECTED_TOTAL_NODES

    def test_seed_creates_exact_relationship_counts(self, test_graph):
        client, graph = test_graph
        create_constraints(graph)
        seed_nodes(graph)
        seed_relationships(graph)

        assert _count_rels(graph) == EXPECTED_TOTAL_RELS

    def test_idempotency_nodes(self, test_graph):
        """Running seed_nodes twice does not duplicate nodes."""
        client, graph = test_graph
        create_constraints(graph)

        seed_nodes(graph)
        before = sum(
            _count_nodes(graph, label)
            for label in ("Service", "Incident", "Document", "Fix")
        )

        seed_nodes(graph)  # second run
        after = sum(
            _count_nodes(graph, label)
            for label in ("Service", "Incident", "Document", "Fix")
        )

        assert before == after == EXPECTED_TOTAL_NODES

    def test_idempotency_relationships(self, test_graph):
        """Running seed_relationships twice does not duplicate relationships."""
        client, graph = test_graph
        create_constraints(graph)
        seed_nodes(graph)
        seed_relationships(graph)

        before = _count_rels(graph)
        seed_relationships(graph)  # second run
        after = _count_rels(graph)

        assert before == after == EXPECTED_TOTAL_RELS

    def test_constraints_created_on_test_graph(self, test_graph):
        """Uniqueness constraints are created and at least PENDING after setup."""
        client, graph = test_graph
        create_constraints(graph)

        rows = graph.list_constraints()
        # Expect 4 constraints (one per label)
        assert len(rows) == 4, (
            f"Expected 4 constraints, got {len(rows)}: {rows}"
        )
        statuses = {row["status"] for row in rows}
        # Status may be PENDING (still building) or OPERATIONAL (already built)
        allowed = {"PENDING", "UNDER CONSTRUCTION", "OPERATIONAL"}
        assert statuses.issubset(allowed), (
            f"Unexpected constraint status(es): {statuses - allowed}"
        )
