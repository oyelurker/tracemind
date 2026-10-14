"""
tests/graph/test_queries.py — Integration tests for multi-hop Cypher queries.

All tests run against `tracemind_test` only via the `test_graph` fixture.
The development graph is never touched.

Mark: @pytest.mark.integration — skipped automatically if FalkorDB is down.
"""

import pytest

from backend.graph.schema import create_constraints
from backend.graph.seed import seed_nodes, seed_relationships

pytestmark = pytest.mark.integration


@pytest.fixture()
def seeded_graph(test_graph):
    """Provide a test_graph that has been fully seeded with demo data."""
    client, graph = test_graph
    create_constraints(graph)
    seed_nodes(graph)
    seed_relationships(graph)
    return client, graph


class TestMultiHopQueries:
    """Multi-hop graph traversal queries against the demo dataset."""

    def test_fixes_for_dependents_of_auth_service(self, seeded_graph):
        """
        'What fixes resolved incidents affecting services that depend on auth-service?'
        Expected: api-gateway and user-service both depend on auth-service;
        INC-001 affects api-gateway and auth-service itself; FIX-001 resolves INC-001.
        """
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (dep:Service {name: $svc})<-[:DEPENDS_ON]-(s:Service)"
            "<-[:AFFECTS]-(i:Incident)<-[:RESOLVES]-(f:Fix) "
            "RETURN dep.name, s.name, i.id, f.id",
            params={"svc": "auth-service"},
        )
        rows = result.result_set or []
        assert len(rows) > 0, "Expected at least one fix for dependents of auth-service"

        # FIX-001 resolves INC-001 which affects api-gateway (which depends on auth-service)
        fix_ids = {row[3] for row in rows}
        assert "FIX-001" in fix_ids

    def test_sev1_incident_documents(self, seeded_graph):
        """
        'What documents describe fixes for SEV1 incidents?'
        Expected: INC-001 (SEV1) ← FIX-001 → DOC-001, DOC-002
        """
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (i:Incident {severity: 'SEV1'})<-[:RESOLVES]-(f:Fix)"
            "-[:DESCRIBED_IN]->(d:Document) "
            "RETURN i.id, f.id, d.id",
        )
        rows = result.result_set or []
        assert len(rows) > 0, "Expected documents for SEV1 incidents"

        doc_ids = {row[2] for row in rows}
        # FIX-001 is described in DOC-001 and DOC-002; both resolve INC-001 (SEV1)
        assert "DOC-001" in doc_ids
        assert "DOC-002" in doc_ids

    def test_full_investigation_path_api_gateway(self, seeded_graph):
        """
        Full path: api-gateway ← AFFECTS ← INC-001 ← RESOLVES ← FIX-001 → DESCRIBED_IN → DOC-001
        """
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (s:Service {name: $svc})<-[:AFFECTS]-(i:Incident)"
            "<-[:RESOLVES]-(f:Fix)-[:DESCRIBED_IN]->(d:Document) "
            "RETURN s.name, i.id, f.id, d.id",
            params={"svc": "api-gateway"},
        )
        rows = result.result_set or []
        assert len(rows) > 0, "Expected full investigation paths for api-gateway"

        # Verify at least the known path exists
        path_keys = {(row[1], row[2], row[3]) for row in rows}
        assert ("INC-001", "FIX-001", "DOC-001") in path_keys or (
            "INC-001", "FIX-001", "DOC-002"
        ) in path_keys

    def test_service_with_no_incidents_returns_empty(self, seeded_graph):
        """
        logging-svc has no incidents in the dataset → empty result.
        """
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (s:Service {name: $svc})<-[:AFFECTS]-(i:Incident) "
            "RETURN i.id",
            params={"svc": "logging-svc"},
        )
        rows = result.result_set or []
        assert rows == [], f"logging-svc should have no incidents, got: {rows}"

    def test_nonexistent_service_returns_empty(self, seeded_graph):
        """Querying a service that doesn't exist returns an empty result set."""
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (s:Service {name: $svc})<-[:AFFECTS]-(i:Incident) "
            "RETURN i.id",
            params={"svc": "does-not-exist"},
        )
        rows = result.result_set or []
        assert rows == []


class TestIncompletePath:
    """Tests for INC-004: an incident with no resolving fix (status: investigating)."""

    def test_inc004_has_no_fix(self, seeded_graph):
        """INC-004 has no RESOLVES relationship pointing to it."""
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (f:Fix)-[:RESOLVES]->(i:Incident {id: 'INC-004'}) "
            "RETURN f.id",
        )
        rows = result.result_set or []
        assert rows == [], (
            f"INC-004 should have no fix, but found: {[r[0] for r in rows]}"
        )

    def test_inc004_affects_expected_services(self, seeded_graph):
        """INC-004 affects api-gateway and auth-service."""
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (i:Incident {id: 'INC-004'})-[:AFFECTS]->(s:Service) "
            "RETURN s.name",
        )
        rows = result.result_set or []
        affected = {row[0] for row in rows}
        assert "api-gateway" in affected
        assert "auth-service" in affected

    def test_inc004_full_path_returns_incident_but_no_fix(self, seeded_graph):
        """
        Full investigation path query for INC-004 should return the incident
        and affected services but produce an empty result for fix+document,
        because there is no Fix node resolving INC-004.
        """
        _, graph = seeded_graph
        # Query that requires a fix — should return nothing for INC-004
        result = graph.query(
            "MATCH (s:Service)<-[:AFFECTS]-(i:Incident {id: 'INC-004'})"
            "<-[:RESOLVES]-(f:Fix)-[:DESCRIBED_IN]->(d:Document) "
            "RETURN s.name, i.id, f.id, d.id",
        )
        rows = result.result_set or []
        assert rows == [], (
            "INC-004 has no fix, so the full investigation path should be empty"
        )

        # But the incident itself is reachable
        inc_result = graph.query(
            "MATCH (i:Incident {id: 'INC-004'}) RETURN i.id, i.status",
        )
        inc_rows = inc_result.result_set or []
        assert len(inc_rows) == 1
        assert inc_rows[0][0] == "INC-004"
        assert inc_rows[0][1] == "investigating"

    def test_unresolved_incidents_query_returns_only_inc004(self, seeded_graph):
        """
        'Unresolved incidents' (status != 'resolved') returns only INC-004.
        """
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (i:Incident) WHERE i.status <> 'resolved' "
            "RETURN i.id, i.status",
        )
        rows = result.result_set or []
        assert len(rows) == 1, f"Expected 1 unresolved incident, got {len(rows)}: {rows}"
        assert rows[0][0] == "INC-004"
        assert rows[0][1] == "investigating"

    def test_resolved_incidents_excludes_inc004(self, seeded_graph):
        """Resolved incidents do NOT include INC-004."""
        _, graph = seeded_graph
        result = graph.query(
            "MATCH (i:Incident {status: 'resolved'}) RETURN i.id",
        )
        rows = result.result_set or []
        resolved_ids = {row[0] for row in rows}
        assert "INC-004" not in resolved_ids
        assert resolved_ids == {"INC-001", "INC-002", "INC-003"}
