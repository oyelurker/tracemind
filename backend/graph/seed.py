"""
backend.graph.seed
~~~~~~~~~~~~~~~~~~
Seeds the TraceMind demo dataset into FalkorDB.

Idempotency: Uses MERGE (not CREATE) for all node and relationship writes.
Running this module twice produces the same graph state.

Constraint and index creation happens before any MERGE statements.

Demo dataset (deterministic):
  - 6 Service nodes
  - 4 Incident nodes
  - 4 Document nodes
  - 3 Fix nodes
  Total: 17 nodes

  - 7 DEPENDS_ON
  - 6 AFFECTS
  - 2 DOCUMENTED_IN
  - 3 RESOLVES
  - 3 DESCRIBED_IN
  Total: 21 relationships

Run directly:
    python -m backend.graph.seed
    python -m backend.graph.seed --graph tracemind   # explicit graph name
"""

import argparse
import sys

from .connection import get_connection_params, get_graph
from .schema import create_constraints

# ── Demo data ──────────────────────────────────────────────────────────────────

SERVICES = [
    {"name": "api-gateway", "tier": "critical"},
    {"name": "auth-service", "tier": "critical"},
    {"name": "payment-service", "tier": "critical"},
    {"name": "user-service", "tier": "standard"},
    {"name": "notification-svc", "tier": "standard"},
    {"name": "logging-svc", "tier": "internal"},
]

# (from_name, to_name)
SERVICE_DEPS = [
    ("api-gateway", "auth-service"),
    ("api-gateway", "user-service"),
    ("api-gateway", "payment-service"),
    ("payment-service", "auth-service"),
    ("user-service", "auth-service"),
    ("notification-svc", "user-service"),
    ("notification-svc", "logging-svc"),
]

INCIDENTS = [
    {
        "id": "INC-001",
        "title": "Auth token validation failure",
        "severity": "SEV1",
        "status": "resolved",
        "created_at": "2025-09-10T08:15:00Z",
    },
    {
        "id": "INC-002",
        "title": "Payment timeout under load",
        "severity": "SEV2",
        "status": "resolved",
        "created_at": "2025-09-12T14:30:00Z",
    },
    {
        "id": "INC-003",
        "title": "Notification delivery delays",
        "severity": "SEV3",
        "status": "resolved",
        "created_at": "2025-09-15T10:00:00Z",
    },
    {
        "id": "INC-004",
        "title": "API gateway 502 errors",
        "severity": "SEV1",
        "status": "investigating",
        "created_at": "2025-09-18T03:45:00Z",
    },
]

# (incident_id, service_name)
INCIDENT_AFFECTS = [
    ("INC-001", "auth-service"),
    ("INC-001", "api-gateway"),
    ("INC-002", "payment-service"),
    ("INC-003", "notification-svc"),
    ("INC-004", "api-gateway"),
    ("INC-004", "auth-service"),
]

DOCUMENTS = [
    {
        "id": "DOC-001",
        "title": "Auth service runbook",
        "doc_type": "runbook",
        "content": (
            "To restore auth-service: restart the pod, rotate the JWT signing key "
            "via the secrets manager, and verify token validation with a smoke test."
        ),
    },
    {
        "id": "DOC-002",
        "title": "INC-001 postmortem",
        "doc_type": "postmortem",
        "content": (
            "Root cause: the JWT signing key in auth-service expired after 90 days "
            "with no automated rotation, causing all token validations to fail."
        ),
    },
    {
        "id": "DOC-003",
        "title": "Payment timeout runbook",
        "doc_type": "runbook",
        "content": (
            "To resolve payment-service timeouts: increase the DB connection pool "
            "size to 50, enable the circuit breaker, and restart the service."
        ),
    },
    {
        "id": "DOC-004",
        "title": "INC-002 postmortem",
        "doc_type": "postmortem",
        "content": (
            "Root cause: connection pool exhaustion in payment-service under "
            "peak load due to an under-sized pool and missing circuit breaker."
        ),
    },
]

FIXES = [
    {
        "id": "FIX-001",
        "title": "Rotate auth signing key",
        "fix_type": "hotfix",
        "applied_at": "2025-09-10T09:30:00Z",
    },
    {
        "id": "FIX-002",
        "title": "Increase payment pool size",
        "fix_type": "config_change",
        "applied_at": "2025-09-12T16:00:00Z",
    },
    {
        "id": "FIX-003",
        "title": "Add notification retry logic",
        "fix_type": "hotfix",
        "applied_at": "2025-09-15T12:00:00Z",
    },
]

# (fix_id, incident_id)
FIX_RESOLVES = [
    ("FIX-001", "INC-001"),
    ("FIX-002", "INC-002"),
    ("FIX-003", "INC-003"),
]

# (incident_id, doc_id)
INCIDENT_DOCUMENTED_IN = [
    ("INC-001", "DOC-002"),
    ("INC-002", "DOC-004"),
]

# (fix_id, doc_id)
FIX_DESCRIBED_IN = [
    ("FIX-001", "DOC-001"),
    ("FIX-001", "DOC-002"),
    ("FIX-002", "DOC-003"),
]


# ── Seed functions ─────────────────────────────────────────────────────────────


def seed_nodes(graph, timeout_ms: int = 5000) -> None:
    """Insert all demo nodes using idempotent MERGE statements."""

    # Services
    for svc in SERVICES:
        graph.query(
            "MERGE (s:Service {name: $name}) SET s.tier = $tier",
            params={"name": svc["name"], "tier": svc["tier"]},
            timeout=timeout_ms,
        )

    # Incidents
    for inc in INCIDENTS:
        graph.query(
            "MERGE (i:Incident {id: $id}) "
            "SET i.title = $title, i.severity = $severity, "
            "    i.status = $status, i.created_at = $created_at",
            params=inc,
            timeout=timeout_ms,
        )

    # Documents
    for doc in DOCUMENTS:
        graph.query(
            "MERGE (d:Document {id: $id}) "
            "SET d.title = $title, d.doc_type = $doc_type, d.content = $content",
            params=doc,
            timeout=timeout_ms,
        )

    # Fixes
    for fix in FIXES:
        graph.query(
            "MERGE (f:Fix {id: $id}) "
            "SET f.title = $title, f.fix_type = $fix_type, f.applied_at = $applied_at",
            params=fix,
            timeout=timeout_ms,
        )


def seed_relationships(graph, timeout_ms: int = 5000) -> None:
    """Insert all demo relationships using idempotent MERGE statements."""

    # Service DEPENDS_ON Service
    for from_name, to_name in SERVICE_DEPS:
        graph.query(
            "MATCH (a:Service {name: $from_name}), (b:Service {name: $to_name}) "
            "MERGE (a)-[:DEPENDS_ON]->(b)",
            params={"from_name": from_name, "to_name": to_name},
            timeout=timeout_ms,
        )

    # Incident AFFECTS Service
    for inc_id, svc_name in INCIDENT_AFFECTS:
        graph.query(
            "MATCH (i:Incident {id: $inc_id}), (s:Service {name: $svc_name}) "
            "MERGE (i)-[:AFFECTS]->(s)",
            params={"inc_id": inc_id, "svc_name": svc_name},
            timeout=timeout_ms,
        )

    # Incident DOCUMENTED_IN Document
    for inc_id, doc_id in INCIDENT_DOCUMENTED_IN:
        graph.query(
            "MATCH (i:Incident {id: $inc_id}), (d:Document {id: $doc_id}) "
            "MERGE (i)-[:DOCUMENTED_IN]->(d)",
            params={"inc_id": inc_id, "doc_id": doc_id},
            timeout=timeout_ms,
        )

    # Fix RESOLVES Incident
    for fix_id, inc_id in FIX_RESOLVES:
        graph.query(
            "MATCH (f:Fix {id: $fix_id}), (i:Incident {id: $inc_id}) "
            "MERGE (f)-[:RESOLVES]->(i)",
            params={"fix_id": fix_id, "inc_id": inc_id},
            timeout=timeout_ms,
        )

    # Fix DESCRIBED_IN Document
    for fix_id, doc_id in FIX_DESCRIBED_IN:
        graph.query(
            "MATCH (f:Fix {id: $fix_id}), (d:Document {id: $doc_id}) "
            "MERGE (f)-[:DESCRIBED_IN]->(d)",
            params={"fix_id": fix_id, "doc_id": doc_id},
            timeout=timeout_ms,
        )


def seed(graph_name: str | None = None) -> None:
    """
    Full seed operation:
      1. Create indexes
      2. Create uniqueness constraints
      3. Seed nodes (idempotent MERGE)
      4. Seed relationships (idempotent MERGE)

    Args:
        graph_name: Override graph name (uses FALKORDB_GRAPH env var if None).
    """
    params = get_connection_params()
    timeout_ms = params["timeout_ms"]
    name = graph_name if graph_name is not None else params["graph_name"]

    _, graph = get_graph(name)

    print(f"[seed] Connecting to FalkorDB graph: {name!r}")

    print("[seed] Creating uniqueness constraints (and indexes) …")
    create_constraints(graph)

    print("[seed] Seeding nodes …")
    seed_nodes(graph, timeout_ms=timeout_ms)

    print("[seed] Seeding relationships …")
    seed_relationships(graph, timeout_ms=timeout_ms)

    print("[seed] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TraceMind demo data into FalkorDB.")
    parser.add_argument(
        "--graph",
        default=None,
        help="Graph name to seed (overrides FALKORDB_GRAPH env var).",
    )
    args = parser.parse_args()

    try:
        seed(graph_name=args.graph)
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
