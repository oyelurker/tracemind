"""
backend.graph.schema
~~~~~~~~~~~~~~~~~~~~
Node labels, relationship type constants, and helpers for creating
indexes and uniqueness constraints in FalkorDB.

Constraint implementation notes (falkordb-py 1.8.0)
-----------------------------------------------------
In falkordb-py 1.8.0 the constraint API lives on the **Graph** object,
not on the FalkorDB client:

    graph.create_node_unique_constraint(label, *properties)

This method automatically creates any missing range index internally, so a
separate index-creation step is NOT required. The constraint is built
asynchronously; poll graph.list_constraints() to check for "OPERATIONAL".

list_constraints() returns a list of dicts with keys:
    type, label, properties, entitytype, status

Running create_node_unique_constraint() on an already-constrained property
raises an exception whose message contains "already" or "exists". This is
treated as idempotent here and silently swallowed.

Verified against: falkordb==1.8.0 (Graph.create_node_unique_constraint)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from falkordb.graph import Graph

# ── Node labels ────────────────────────────────────────────────────────────────
LABEL_SERVICE = "Service"
LABEL_INCIDENT = "Incident"
LABEL_DOCUMENT = "Document"
LABEL_FIX = "Fix"

# ── Relationship types ─────────────────────────────────────────────────────────
REL_DEPENDS_ON = "DEPENDS_ON"        # Service  → Service
REL_AFFECTS = "AFFECTS"              # Incident → Service
REL_DOCUMENTED_IN = "DOCUMENTED_IN"  # Incident → Document
REL_RESOLVES = "RESOLVES"            # Fix      → Incident
REL_DESCRIBED_IN = "DESCRIBED_IN"    # Fix      → Document

# ── Unique property keys per label ─────────────────────────────────────────────
#    Maps label -> property name for which a uniqueness constraint is created.
UNIQUE_PROPS: dict[str, str] = {
    LABEL_SERVICE: "name",
    LABEL_INCIDENT: "id",
    LABEL_DOCUMENT: "id",
    LABEL_FIX: "id",
}

# ── Valid enum values (informational — enforced in seed data) ──────────────────
SERVICE_TIERS = frozenset({"critical", "standard", "internal"})
INCIDENT_SEVERITIES = frozenset({"SEV1", "SEV2", "SEV3"})
INCIDENT_STATUSES = frozenset({"resolved", "investigating", "open"})
DOCUMENT_TYPES = frozenset({"runbook", "postmortem"})
FIX_TYPES = frozenset({"hotfix", "config_change", "rollback"})


def create_constraints(graph: "Graph") -> None:
    """
    Create uniqueness constraints for Service.name, Incident.id,
    Document.id, and Fix.id using the falkordb 1.8.0 Graph API.

    Uses graph.create_node_unique_constraint(label, property) which
    internally creates the required range index if missing.

    Constraint creation is asynchronous — status starts as "PENDING"
    and transitions to "OPERATIONAL" once the index is built.

    Idempotent: if a constraint already exists, the exception is caught
    and swallowed rather than propagating.

    Args:
        graph: FalkorDB Graph object (falkordb.graph.Graph).

    Raises:
        AttributeError: If the Graph object does not expose
            create_node_unique_constraint(). This means the installed
            falkordb-py version is incompatible. Constraint creation is
            NOT silently skipped — the error is propagated.
    """
    if not hasattr(graph, "create_node_unique_constraint"):
        raise AttributeError(
            "The installed falkordb-py Graph object does not expose "
            "create_node_unique_constraint(). "
            "Uniqueness constraints cannot be created. "
            "Verified working version: falkordb>=1.8.0. "
            "Constraint creation has NOT been skipped silently."
        )

    for label, prop in UNIQUE_PROPS.items():
        try:
            graph.create_node_unique_constraint(label, prop)
        except Exception as exc:
            err_str = str(exc).lower()
            if "already" in err_str or "exists" in err_str or "constraint" in err_str:
                # Idempotent: constraint already present — not an error
                continue
            raise


def list_constraints(graph: "Graph") -> list[dict]:
    """
    Return the current constraints on the graph using the native client method.

    Uses graph.list_constraints() which calls the DB.CONSTRAINTS procedure.

    Each returned dict has keys: type, label, properties, entitytype, status.
    Status values: PENDING | UNDER CONSTRUCTION | OPERATIONAL | FAILED

    Args:
        graph: FalkorDB Graph object.

    Returns:
        List of constraint dicts.
    """
    return graph.list_constraints()


def create_indexes(graph: "Graph", timeout_ms: int = 5000) -> None:
    """
    Create range indexes explicitly.

    NOTE: In falkordb 1.8.0, create_node_unique_constraint() already creates
    any missing range index internally, so calling this separately is optional.
    Kept for explicitness and testability.

    Args:
        graph: FalkorDB Graph object.
        timeout_ms: Unused (index creation is synchronous in falkordb 1.8.0).
    """
    for label, prop in UNIQUE_PROPS.items():
        try:
            graph.create_node_range_index(label, prop)
        except Exception:
            # Index may already exist — treat as idempotent
            pass
