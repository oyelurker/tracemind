# Spec: Graph Foundation and Demo Data

## Goal
Establish the core FalkorDB graph schema for TraceMind and populate it with a small, deterministic demo dataset. After running one initialization command, a developer can verify that nodes, relationships, and multi-hop paths exist — proving the graph is ready for incident investigation features.

## User-visible behavior
1. A developer sets `FALKORDB_HOST`, `FALKORDB_PORT`, and `FALKORDB_GRAPH` environment variables (with documented defaults in `.env.example`).
2. Running `python -m backend.graph.seed` creates the graph and inserts the demo dataset idempotently (safe to run twice without duplicating data).
3. Running `python -m backend.graph.verify` prints a short health-check report confirming node counts, relationship counts, and at least one multi-hop path.
4. All tests pass with `pytest tests/` against a running FalkorDB instance.

## Scope

### In scope
- Node labels, relationship types, and required properties for: **Service**, **Incident**, **Document** (runbooks / postmortems), and **Fix**.
- Relationships that enable multi-hop investigation queries (e.g., "Which fix resolved incidents on services that depend on service X?").
- A small, deterministic demo dataset (exactly 17 nodes, 21 relationships).
- Uniqueness constraints on `Service.name`, `Incident.id`, `Document.id`, and `Fix.id`, created before seeding.
- A `seed` module that creates constraints and inserts demo data idempotently.
- A `verify` module that checks graph health.
- Unit tests (mocked FalkorDB) and integration tests (live FalkorDB) for graph creation, relationships, idempotency, empty graph, and error/timeout cases.
- `.env.example` with safe placeholder values.
- A `requirements.txt` listing only the dependencies needed for this slice.

### Out of scope
- FastAPI endpoints, REST/GraphQL API, or any HTTP layer.
- React/Vite frontend or any UI.
- LLM integration or answer synthesis.
- Investigation memory or session persistence.
- Production deployment, Docker Compose, or CI/CD configuration.
- Full-text search indexes or vector embeddings.
- Authentication, authorization, or multi-tenancy.

## Existing code and assumptions

### Verified facts
- Repository contains only `CLAUDE.md` and `.claude/commands/`. No application code, no `requirements.txt`, no `pyproject.toml`, no tests, no `.env` file.
- `CLAUDE.md` specifies Python/FastAPI backend and FalkorDB as the graph database.
- `CLAUDE.md` requires environment-variable-based configuration, parameterized Cypher, idempotent graph writes, deterministic test fixtures, and no committed secrets.

### Proposed decisions
- Use `falkordb` (the official FalkorDB Python client) as the sole new dependency for this slice.
- Use `pytest` as the test runner.
- Backend code lives under `backend/graph/`.
- Tests live under `tests/graph/`.
- Graph name defaults to `tracemind` when `FALKORDB_GRAPH` is unset.

## Design

### Graph model

```
(Service)-[:DEPENDS_ON]->(Service)
(Incident)-[:AFFECTS]->(Service)
(Incident)-[:DOCUMENTED_IN]->(Document)
(Fix)-[:RESOLVES]->(Incident)
(Fix)-[:DESCRIBED_IN]->(Document)
```

### Node labels and properties

| Label      | Required properties                                             | Notes                                |
|------------|------------------------------------------------------------------|--------------------------------------|
| Service    | `name` (string, unique), `tier` (string: "critical" / "standard" / "internal") | Represents a deployed service        |
| Incident   | `id` (string, unique), `title` (string), `severity` (string: "SEV1" / "SEV2" / "SEV3"), `status` (string: "resolved" / "investigating" / "open"), `created_at` (string, ISO-8601) | Represents a production incident     |
| Document   | `id` (string, unique), `title` (string), `doc_type` (string: "runbook" / "postmortem"), `content` (string) | Runbooks or postmortem write-ups     |
| Fix        | `id` (string, unique), `title` (string), `fix_type` (string: "hotfix" / "config_change" / "rollback"), `applied_at` (string, ISO-8601) | An action that resolved an incident  |

### Relationship types

| Relationship     | From     | To       | Properties              | Semantics                                 |
|-----------------|----------|----------|--------------------------|-------------------------------------------|
| DEPENDS_ON      | Service  | Service  | _(none)_                 | Runtime dependency                        |
| AFFECTS         | Incident | Service  | _(none)_                 | Incident impacts this service             |
| DOCUMENTED_IN   | Incident | Document | _(none)_                 | Incident is described in this document    |
| RESOLVES        | Fix      | Incident | _(none)_                 | Fix resolved this incident                |
| DESCRIBED_IN    | Fix      | Document | _(none)_                 | Fix procedure is documented here          |

### Multi-hop query examples

**"What fixes resolved incidents affecting services that depend on service X?"**
```cypher
MATCH (dep:Service {name: $service_name})<-[:DEPENDS_ON]-(s:Service)
      <-[:AFFECTS]-(i:Incident)<-[:RESOLVES]-(f:Fix)
RETURN dep.name, s.name, i.id, i.title, f.id, f.title
```

**"What documents describe fixes for SEV1 incidents?"**
```cypher
MATCH (i:Incident {severity: 'SEV1'})<-[:RESOLVES]-(f:Fix)
      -[:DESCRIBED_IN]->(d:Document)
RETURN i.id, i.title, f.title, d.title, d.doc_type
```

**"Full investigation path: service → incident → fix → document"**
```cypher
MATCH path = (s:Service)<-[:AFFECTS]-(i:Incident)<-[:RESOLVES]-(f:Fix)
              -[:DESCRIBED_IN]->(d:Document)
WHERE s.name = $service_name
RETURN path
```

### Demo dataset

**Services** (6):
| name            | tier       |
|-----------------|------------|
| api-gateway     | critical   |
| auth-service    | critical   |
| payment-service | critical   |
| user-service    | standard   |
| notification-svc| standard   |
| logging-svc     | internal   |

**DEPENDS_ON relationships** (7):
- api-gateway → auth-service
- api-gateway → user-service
- api-gateway → payment-service
- payment-service → auth-service
- user-service → auth-service
- notification-svc → user-service
- notification-svc → logging-svc

**Incidents** (4):
| id     | title                          | severity | status        | created_at           |
|--------|--------------------------------|----------|---------------|----------------------|
| INC-001| Auth token validation failure  | SEV1     | resolved      | 2025-09-10T08:15:00Z |
| INC-002| Payment timeout under load     | SEV2     | resolved      | 2025-09-12T14:30:00Z |
| INC-003| Notification delivery delays   | SEV3     | resolved      | 2025-09-15T10:00:00Z |
| INC-004| API gateway 502 errors         | SEV1     | investigating | 2025-09-18T03:45:00Z |

**AFFECTS relationships** (6):
- INC-001 → auth-service
- INC-001 → api-gateway _(cascading impact)_
- INC-002 → payment-service
- INC-003 → notification-svc
- INC-004 → api-gateway
- INC-004 → auth-service _(suspected root cause)_

**Documents** (4):
| id      | title                              | doc_type   | content (truncated summary)                       |
|---------|------------------------------------|------------|---------------------------------------------------|
| DOC-001 | Auth service runbook               | runbook    | Steps to restart auth-service, rotate tokens...   |
| DOC-002 | INC-001 postmortem                 | postmortem | Root cause: expired signing key in auth-service... |
| DOC-003 | Payment timeout runbook            | runbook    | Steps to increase pool size, enable circuit...    |
| DOC-004 | INC-002 postmortem                 | postmortem | Root cause: connection pool exhaustion under...   |

**Fixes** (3):
| id     | title                           | fix_type      | applied_at           |
|--------|---------------------------------|---------------|----------------------|
| FIX-001| Rotate auth signing key         | hotfix        | 2025-09-10T09:30:00Z |
| FIX-002| Increase payment pool size      | config_change | 2025-09-12T16:00:00Z |
| FIX-003| Add notification retry logic    | hotfix        | 2025-09-15T12:00:00Z |

**RESOLVES relationships** (3):
- FIX-001 → INC-001
- FIX-002 → INC-002
- FIX-003 → INC-003

**DOCUMENTED_IN relationships** (2):
- INC-001 → DOC-002
- INC-002 → DOC-004

**DESCRIBED_IN relationships** (3):
- FIX-001 → DOC-001
- FIX-001 → DOC-002
- FIX-002 → DOC-003

**Total**: 17 nodes, 21 relationships

### Notable multi-hop paths in this dataset
1. `api-gateway ←[AFFECTS]– INC-001 ←[RESOLVES]– FIX-001 –[DESCRIBED_IN]→ DOC-001` — 3 hops from service to runbook via incident and fix.
2. `api-gateway –[DEPENDS_ON]→ payment-service ←[AFFECTS]– INC-002 ←[RESOLVES]– FIX-002 –[DESCRIBED_IN]→ DOC-003` — dependency + incident + fix + document chain.
3. INC-004 has no fix yet (status: investigating) — tests should handle this incomplete path.

## API contract
No API endpoints are introduced in this spec. Graph access is through Python modules only.

## UI changes
No UI changes in this spec.

## Persistence and memory
- All data is persisted in FalkorDB under the graph named by `FALKORDB_GRAPH` (default: `tracemind`).
- No investigation memory or session state is introduced in this spec.
- No secrets or personal data are stored in the graph.

## Files to create or modify

| Path                              | Status   | Purpose                                              |
|-----------------------------------|----------|------------------------------------------------------|
| `.env.example`                    | proposed | Document env vars with safe defaults                 |
| `requirements.txt`               | proposed | `falkordb`, `pytest`, `python-dotenv`                |
| `backend/__init__.py`            | proposed | Package marker                                       |
| `backend/graph/__init__.py`      | proposed | Package marker                                       |
| `backend/graph/connection.py`    | proposed | FalkorDB connection helper using env vars            |
| `backend/graph/schema.py`        | proposed | Node/relationship constants, constraint creation, and helpers |
| `backend/graph/seed.py`          | proposed | Demo data insertion (idempotent), runnable as module |
| `backend/graph/verify.py`        | proposed | Graph health check, runnable as module               |
| `tests/__init__.py`              | proposed | Package marker                                       |
| `tests/graph/__init__.py`        | proposed | Package marker                                       |
| `tests/graph/test_connection.py` | proposed | Connection config, error, and timeout tests          |
| `tests/graph/test_schema.py`    | proposed | Schema creation and idempotency tests                |
| `tests/graph/test_seed.py`      | proposed | Seed data correctness and idempotency tests          |
| `tests/graph/test_queries.py`   | proposed | Multi-hop query tests against known fixtures         |
| `conftest.py`                    | proposed | Shared pytest fixtures (graph connection, cleanup)   |

## Testing

All integration tests run against a dedicated `tracemind_test` graph (never the development graph). The test graph is dropped and recreated per test session. This is configured via `conftest.py` fixtures.

### Unit tests (mocked FalkorDB)
- `test_connection.py`: Verify connection uses env vars; verify error when FalkorDB unreachable (mocked); verify timeout configuration.
- `test_schema.py`: Verify schema/constraint creation calls produce correct Cypher; verify idempotency (running twice does not error); verify constraint syntax is valid for the installed FalkorDB version.

### Integration tests (live FalkorDB required)
- `test_seed.py`:
  - Seed runs successfully on an empty graph.
  - After seeding, node counts match exactly: 6 Services, 4 Incidents, 4 Documents, 3 Fixes (17 total).
  - After seeding, relationship counts match exactly: 21 relationships.
  - Running seed a second time does not duplicate nodes or relationships (idempotency).
  - Uniqueness constraints exist on `Service.name`, `Incident.id`, `Document.id`, and `Fix.id` after seeding.
- `test_queries.py`:
  - Multi-hop query "fixes for incidents affecting dependents of auth-service" returns expected results.
  - Query for SEV1 incident documents returns expected results.
  - Query for a service with no incidents returns an empty result set.
  - Query for an incident with no fix (INC-004) returns an empty fix list.
  - Full investigation path query for INC-004 returns the incident and affected services but no fix or fix-described document.
  - "Unresolved incidents" query (status != 'resolved') returns only INC-004.

### Edge-case tests
- Empty graph before seeding returns zero counts from verify.
- Connection with wrong host/port raises a clear error.
- Query with a non-existent service name returns an empty result.
- Integration tests never read from, write to, or drop the development graph (`tracemind`).

## Security and reliability
- **No hardcoded credentials.** Connection params come from environment variables only. `.env` is gitignored; `.env.example` contains only safe placeholder values.
- **Parameterized Cypher.** All queries use `$param` syntax; no string concatenation of user input into Cypher.
- **Timeouts.** Connection and query calls use bounded timeouts (configurable via `FALKORDB_TIMEOUT_MS`, default 5000 ms).
- **Error handling.** Connection failures, query errors, and unexpected empty results produce clear error messages without leaking internal details.
- **No secrets in graph.** Demo data contains no real credentials, tokens, or personal information.

## Acceptance criteria
- [ ] `.env.example` exists with `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_GRAPH`, `FALKORDB_TIMEOUT_MS` and safe defaults documented.
- [ ] Uniqueness constraints are created on `Service.name`, `Incident.id`, `Document.id`, and `Fix.id` before data is seeded. If the FalkorDB version or client has constraint limitations, the issue is reported clearly rather than silently omitted.
- [ ] `python -m backend.graph.seed` creates exactly 17 nodes and 21 relationships on a fresh graph.
- [ ] Running `python -m backend.graph.seed` a second time does not increase node or relationship counts.
- [ ] `python -m backend.graph.verify` prints correct counts and confirms at least one multi-hop path.
- [ ] All unit tests pass with FalkorDB mocked.
- [ ] All integration tests run against a dedicated `tracemind_test` graph and never touch the development graph.
- [ ] All integration tests pass against a running local FalkorDB instance.
- [ ] Multi-hop query returns expected fix → incident → service → document paths.
- [ ] INC-004 (no fix) is explicitly tested: queries return the incident and affected services but no fix.
- [ ] Queries against an empty or partially-populated graph return empty results without errors.
- [ ] No credentials are hardcoded; configuration is entirely through environment variables.
- [ ] No secrets, `.env`, or generated files are committed.

## Implementation notes
- Create uniqueness constraints (`CREATE CONSTRAINT ...`) before running any `MERGE` statements. Verify the constraint syntax against the installed FalkorDB version/client at implementation time; if the syntax differs or is unsupported, document the limitation and raise an error rather than silently skipping.
- Use `MERGE` (not `CREATE`) in Cypher to ensure idempotency.
- Mark integration tests with `@pytest.mark.integration` so they can be skipped when FalkorDB is unavailable.
- Integration tests must use `tracemind_test` as the graph name. `conftest.py` fixtures must drop and recreate the test graph per session. Tests must never reference or clear the default `tracemind` development graph.
- Keep `content` values in Document nodes short but realistic enough to show in a future UI — 1–2 sentences each.
- Use ISO-8601 strings for timestamps (FalkorDB does not have a native datetime type).
- The `connection.py` module should return a thin wrapper or a raw FalkorDB graph object — avoid unnecessary abstractions at this stage.
- Do not add FastAPI, frontend, LLM integration, or investigation memory in this feature.

## Resolved decisions
1. **FalkorDB constraints**: ✅ Enforce `UNIQUE` constraints on `Service.name`, `Incident.id`, `Document.id`, and `Fix.id` now, created before seeding. If the installed FalkorDB version or client has limitations, verify the supported syntax and report them rather than silently omitting constraints.
2. **Graph cleanup in tests**: ✅ Use a dedicated `tracemind_test` graph for integration tests. Tests must never clear or drop the development graph. Cleanup is restricted to the dedicated test graph.
3. **Exact seed counts**: ✅ The expected dataset is exactly 17 nodes and 21 relationships. Tests assert those exact counts.
4. **INC-004 incomplete path**: ✅ Add explicit test coverage confirming that INC-004 has no resolving fix and that investigation queries handle this incomplete path correctly (returning the incident and affected services but no fix).
5. **Scope boundary**: ✅ No FastAPI, frontend, LLM integration, or investigation memory is added in this feature.
