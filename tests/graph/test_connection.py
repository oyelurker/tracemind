"""
tests/graph/test_connection.py — Unit tests for backend.graph.connection.

All FalkorDB I/O is mocked. No live FalkorDB instance required.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestGetConnectionParams:
    """Tests for get_connection_params() reading from env vars."""

    def test_defaults_when_no_env_set(self, monkeypatch):
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_GRAPH", raising=False)
        monkeypatch.delenv("FALKORDB_TIMEOUT_MS", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)

        from backend.graph.connection import get_connection_params
        params = get_connection_params()

        assert params["host"] == "localhost"
        assert params["port"] == 6379
        assert params["graph_name"] == "tracemind"
        assert params["timeout_ms"] == 5000
        assert params["password"] is None

    def test_reads_custom_host_and_port(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_HOST", "myhost.example.com")
        monkeypatch.setenv("FALKORDB_PORT", "7777")

        from backend.graph.connection import get_connection_params
        params = get_connection_params()

        assert params["host"] == "myhost.example.com"
        assert params["port"] == 7777

    def test_reads_custom_graph_name(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_GRAPH", "my_custom_graph")

        from backend.graph.connection import get_connection_params
        params = get_connection_params()

        assert params["graph_name"] == "my_custom_graph"

    def test_reads_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_TIMEOUT_MS", "3000")

        from backend.graph.connection import get_connection_params
        params = get_connection_params()

        assert params["timeout_ms"] == 3000

    def test_reads_password_from_env(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_PASSWORD", "s3cr3t")

        from backend.graph.connection import get_connection_params
        params = get_connection_params()

        assert params["password"] == "s3cr3t"

    def test_empty_password_env_returns_none(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_PASSWORD", "")

        from backend.graph.connection import get_connection_params
        params = get_connection_params()

        assert params["password"] is None

    def test_invalid_port_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_PORT", "not_a_number")

        from backend.graph.connection import get_connection_params
        with pytest.raises(ValueError, match="FALKORDB_PORT"):
            get_connection_params()

    def test_invalid_timeout_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_TIMEOUT_MS", "fast")

        from backend.graph.connection import get_connection_params
        with pytest.raises(ValueError, match="FALKORDB_TIMEOUT_MS"):
            get_connection_params()


class TestGetGraph:
    """Tests for get_graph() connection and error handling."""

    def test_returns_client_and_graph(self, monkeypatch):
        """get_graph() returns a (client, graph) tuple on success."""
        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_client.select_graph.return_value = mock_graph

        with patch("backend.graph.connection.FalkorDB", return_value=mock_client):
            from backend.graph.connection import get_graph
            client, graph = get_graph("test_graph")

        assert client is mock_client
        assert graph is mock_graph
        mock_client.select_graph.assert_called_once_with("test_graph")

    def test_uses_graph_name_override(self, monkeypatch):
        """graph_name argument overrides the FALKORDB_GRAPH env var."""
        mock_client = MagicMock()
        mock_client.select_graph.return_value = MagicMock()

        with patch("backend.graph.connection.FalkorDB", return_value=mock_client):
            from backend.graph.connection import get_graph
            get_graph("override_name")

        mock_client.select_graph.assert_called_once_with("override_name")

    def test_uses_env_graph_name_when_no_override(self, monkeypatch):
        monkeypatch.setenv("FALKORDB_GRAPH", "env_graph")
        mock_client = MagicMock()
        mock_client.select_graph.return_value = MagicMock()

        with patch("backend.graph.connection.FalkorDB", return_value=mock_client):
            from backend.graph.connection import get_graph
            get_graph()

        mock_client.select_graph.assert_called_once_with("env_graph")

    def test_connection_failure_raises_connection_error(self, monkeypatch):
        """When FalkorDB() raises, get_graph() raises ConnectionError with a clear message."""
        with patch(
            "backend.graph.connection.FalkorDB",
            side_effect=Exception("Connection refused"),
        ):
            from backend.graph.connection import get_graph
            with pytest.raises(ConnectionError, match="Cannot connect to FalkorDB"):
                get_graph()

    def test_timeout_parameter_passed_to_client(self, monkeypatch):
        """Timeout from FALKORDB_TIMEOUT_MS is passed to the FalkorDB constructor."""
        monkeypatch.setenv("FALKORDB_TIMEOUT_MS", "2000")
        mock_client = MagicMock()
        mock_client.select_graph.return_value = MagicMock()

        with patch("backend.graph.connection.FalkorDB", return_value=mock_client) as mock_cls:
            from backend.graph.connection import get_graph
            get_graph("g")

        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["socket_timeout"] == pytest.approx(2.0)
        assert call_kwargs["socket_connect_timeout"] == pytest.approx(2.0)
