"""
backend.graph.connection
~~~~~~~~~~~~~~~~~~~~~~~~
FalkorDB connection helper.

All connection parameters are read exclusively from environment variables.
No credentials are hardcoded here.

Environment variables:
    FALKORDB_HOST        Host of the FalkorDB server (default: localhost)
    FALKORDB_PORT        Port of the FalkorDB server (default: 6379)
    FALKORDB_GRAPH       Graph name (default: tracemind)
    FALKORDB_TIMEOUT_MS  Query/connection timeout in ms (default: 5000)
    FALKORDB_PASSWORD    Optional password (default: none)
"""

import os
from typing import Optional

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()  # Load .env if present; no-op if not found

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 6379
_DEFAULT_GRAPH = "tracemind"
_DEFAULT_TIMEOUT_MS = 5000


def get_connection_params() -> dict:
    """
    Return a dict of connection parameters read from environment variables.

    Returns:
        dict with keys: host, port, graph_name, timeout_ms, password
    """
    host = os.environ.get("FALKORDB_HOST", _DEFAULT_HOST)
    port_raw = os.environ.get("FALKORDB_PORT", str(_DEFAULT_PORT))
    graph_name = os.environ.get("FALKORDB_GRAPH", _DEFAULT_GRAPH)
    timeout_raw = os.environ.get("FALKORDB_TIMEOUT_MS", str(_DEFAULT_TIMEOUT_MS))
    password: Optional[str] = os.environ.get("FALKORDB_PASSWORD") or None

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError(
            f"FALKORDB_PORT must be an integer, got: {port_raw!r}"
        ) from exc

    try:
        timeout_ms = int(timeout_raw)
    except ValueError as exc:
        raise ValueError(
            f"FALKORDB_TIMEOUT_MS must be an integer, got: {timeout_raw!r}"
        ) from exc

    return {
        "host": host,
        "port": port,
        "graph_name": graph_name,
        "timeout_ms": timeout_ms,
        "password": password,
    }


def get_graph(graph_name: Optional[str] = None):
    """
    Connect to FalkorDB and return (client, graph) for the given graph name.

    Args:
        graph_name: Override the graph name from environment (used by tests
                    to specify the dedicated test graph).

    Returns:
        Tuple[FalkorDB, Graph]

    Raises:
        ConnectionError: If the FalkorDB server cannot be reached.
        ValueError: If connection parameters are invalid.
    """
    params = get_connection_params()
    name = graph_name if graph_name is not None else params["graph_name"]

    timeout_s = params["timeout_ms"] / 1000.0

    try:
        client = FalkorDB(
            host=params["host"],
            port=params["port"],
            password=params["password"],
            socket_connect_timeout=timeout_s,
            socket_timeout=timeout_s,
        )
        graph = client.select_graph(name)
        return client, graph
    except Exception as exc:
        raise ConnectionError(
            f"Cannot connect to FalkorDB at {params['host']}:{params['port']} — {exc}"
        ) from exc
