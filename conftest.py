"""
conftest.py — shared pytest fixtures for TraceMind tests.

Graph isolation guarantee
--------------------------
Integration tests MUST use the `test_graph` fixture, which always
connects to the dedicated `tracemind_test` graph. A safety guard
in the fixture teardown refuses to drop any graph whose name is not
exactly `tracemind_test`, preventing accidental destruction of the
development graph.
"""

import os

import pytest

# ── Safety constant ────────────────────────────────────────────────────────────
TEST_GRAPH_NAME = "tracemind_test"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require a live FalkorDB instance "
        "(skipped automatically when FalkorDB is unavailable)",
    )


# ── Integration test connectivity check ───────────────────────────────────────

def _falkordb_available() -> bool:
    """Return True if a FalkorDB instance can be reached at the configured host/port."""
    try:
        from backend.graph.connection import get_connection_params
        from falkordb import FalkorDB

        params = get_connection_params()
        client = FalkorDB(
            host=params["host"],
            port=params["port"],
            password=params["password"],
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        # Attempt a cheap command to confirm connectivity
        client.connection.ping()
        return True
    except Exception:
        return False


_FALKORDB_UP = None  # cached after first check


def falkordb_available() -> bool:
    global _FALKORDB_UP
    if _FALKORDB_UP is None:
        _FALKORDB_UP = _falkordb_available()
    return _FALKORDB_UP


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def falkordb_client():
    """
    Session-scoped FalkorDB client for integration tests.

    Skips automatically if FalkorDB is not reachable.
    """
    if not falkordb_available():
        pytest.skip("FalkorDB not available — skipping integration tests")

    from backend.graph.connection import get_connection_params
    from falkordb import FalkorDB

    params = get_connection_params()
    client = FalkorDB(
        host=params["host"],
        port=params["port"],
        password=params["password"],
        socket_connect_timeout=params["timeout_ms"] / 1000.0,
        socket_timeout=params["timeout_ms"] / 1000.0,
    )
    return client


@pytest.fixture(scope="function")
def test_graph(falkordb_client):
    """
    Function-scoped fixture that provides a clean `tracemind_test` graph.

    Setup:  Drops any existing `tracemind_test` graph, then returns (client, graph).
    Teardown: Drops the `tracemind_test` graph after the test.

    SAFETY GUARD: Raises RuntimeError if the graph name is not exactly
    `tracemind_test` — preventing accidental dev-graph destruction.
    """
    _safe_drop(falkordb_client, TEST_GRAPH_NAME)
    graph = falkordb_client.select_graph(TEST_GRAPH_NAME)
    yield falkordb_client, graph
    _safe_drop(falkordb_client, TEST_GRAPH_NAME)


def _safe_drop(client, graph_name: str) -> None:
    """
    Drop a graph by name ONLY if it is the designated test graph.

    Raises:
        RuntimeError: If graph_name is not TEST_GRAPH_NAME.
    """
    if graph_name != TEST_GRAPH_NAME:
        raise RuntimeError(
            f"SAFETY GUARD: refusing to drop graph {graph_name!r}. "
            f"Only {TEST_GRAPH_NAME!r} may be dropped by test fixtures. "
            "This prevents accidental destruction of the development graph."
        )
    try:
        g = client.select_graph(graph_name)
        g.delete()
    except Exception:
        # Graph may not exist yet — that's fine
        pass
