"""
tests/graph/test_schema.py — Unit tests for backend.graph.schema.

All FalkorDB I/O is mocked. No live FalkorDB instance required.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from backend.graph.schema import (
    LABEL_DOCUMENT,
    LABEL_FIX,
    LABEL_INCIDENT,
    LABEL_SERVICE,
    REL_AFFECTS,
    REL_DEPENDS_ON,
    REL_DESCRIBED_IN,
    REL_DOCUMENTED_IN,
    REL_RESOLVES,
    UNIQUE_PROPS,
    create_constraints,
    create_indexes,
    list_constraints,
)


class TestConstants:
    """Node label and relationship type constants are correct strings."""

    def test_node_labels(self):
        assert LABEL_SERVICE == "Service"
        assert LABEL_INCIDENT == "Incident"
        assert LABEL_DOCUMENT == "Document"
        assert LABEL_FIX == "Fix"

    def test_relationship_types(self):
        assert REL_DEPENDS_ON == "DEPENDS_ON"
        assert REL_AFFECTS == "AFFECTS"
        assert REL_DOCUMENTED_IN == "DOCUMENTED_IN"
        assert REL_RESOLVES == "RESOLVES"
        assert REL_DESCRIBED_IN == "DESCRIBED_IN"

    def test_unique_props_covers_all_labels(self):
        assert set(UNIQUE_PROPS.keys()) == {
            LABEL_SERVICE,
            LABEL_INCIDENT,
            LABEL_DOCUMENT,
            LABEL_FIX,
        }
        assert UNIQUE_PROPS[LABEL_SERVICE] == "name"
        assert UNIQUE_PROPS[LABEL_INCIDENT] == "id"
        assert UNIQUE_PROPS[LABEL_DOCUMENT] == "id"
        assert UNIQUE_PROPS[LABEL_FIX] == "id"


class TestCreateIndexes:
    """create_indexes() calls graph.create_node_range_index() for each label."""

    def test_creates_index_for_each_label(self):
        mock_graph = MagicMock()
        create_indexes(mock_graph)

        # One call per label (4 labels)
        assert mock_graph.create_node_range_index.call_count == 4

    def test_index_calls_use_correct_label_and_property(self):
        mock_graph = MagicMock()
        create_indexes(mock_graph)

        calls = mock_graph.create_node_range_index.call_args_list
        called_args = [(c.args[0], c.args[1]) for c in calls]

        assert ("Service", "name") in called_args
        assert ("Incident", "id") in called_args
        assert ("Document", "id") in called_args
        assert ("Fix", "id") in called_args

    def test_idempotent_on_exception(self):
        """Exceptions from create_node_range_index are swallowed (index already exists)."""
        mock_graph = MagicMock()
        mock_graph.create_node_range_index.side_effect = Exception("Index already exists")
        # Should not raise
        create_indexes(mock_graph)


class TestCreateConstraints:
    """
    create_constraints() calls graph.create_node_unique_constraint()
    for each label — uses the falkordb 1.8.0 Graph API (not client).
    """

    def test_calls_create_constraint_for_each_label(self):
        mock_graph = MagicMock()
        create_constraints(mock_graph)

        assert mock_graph.create_node_unique_constraint.call_count == 4

        calls = mock_graph.create_node_unique_constraint.call_args_list
        called_args = [(c.args[0], c.args[1]) for c in calls]

        assert ("Service", "name") in called_args
        assert ("Incident", "id") in called_args
        assert ("Document", "id") in called_args
        assert ("Fix", "id") in called_args

    def test_raises_attribute_error_if_method_missing(self):
        """If graph lacks create_node_unique_constraint, raise a descriptive AttributeError."""
        mock_graph = MagicMock(spec=[])  # no attributes
        with pytest.raises(AttributeError, match="create_node_unique_constraint"):
            create_constraints(mock_graph)

    def test_idempotent_on_already_exists_error(self):
        """If constraint already exists, no exception is raised."""
        mock_graph = MagicMock()
        mock_graph.create_node_unique_constraint.side_effect = Exception(
            "Constraint already exists"
        )
        # Should not raise
        create_constraints(mock_graph)

    def test_reraises_unexpected_errors(self):
        """Unexpected errors from create_node_unique_constraint() are re-raised."""
        mock_graph = MagicMock()
        mock_graph.create_node_unique_constraint.side_effect = Exception("Network timeout")
        with pytest.raises(Exception, match="Network timeout"):
            create_constraints(mock_graph)

    def test_constraint_created_on_graph_not_client(self):
        """Constraints are created via graph.create_node_unique_constraint, not on a client."""
        # The function signature only takes `graph` — no client arg
        import inspect
        sig = inspect.signature(create_constraints)
        params = list(sig.parameters.keys())
        assert params == ["graph"], (
            f"create_constraints() must accept only 'graph', got: {params}"
        )


class TestListConstraints:
    """list_constraints() delegates to graph.list_constraints()."""

    def test_delegates_to_graph_list_constraints(self):
        mock_graph = MagicMock()
        mock_graph.list_constraints.return_value = []

        result = list_constraints(mock_graph)

        mock_graph.list_constraints.assert_called_once_with()
        assert result == []

    def test_returns_constraint_dicts(self):
        """list_constraints() passes through whatever graph.list_constraints() returns."""
        mock_graph = MagicMock()
        expected = [
            {
                "type": "UNIQUE",
                "label": "Service",
                "properties": ["name"],
                "entitytype": "NODE",
                "status": "OPERATIONAL",
            }
        ]
        mock_graph.list_constraints.return_value = expected

        result = list_constraints(mock_graph)
        assert result == expected
