---
description: Test a TraceMind feature against its spec without fixing application code
argument-hint: "<spec name, e.g. 01-graph-foundation>"
---

Test the TraceMind feature specified by `$ARGUMENTS`. This command diagnoses; it does not fix application code.

## 1. Validate
- If no argument is provided, stop and show usage: `/test-feature <spec-name>`.
- Confirm `.claude/specs/$ARGUMENTS.md` exists. If not, stop.
- Read the spec, `CLAUDE.md`, the relevant implementation, and existing test configuration.
- Determine the repository's actual test commands from its files; do not assume a framework or invent a command.

## 2. Build a test checklist
Map each acceptance criterion to one or more tests. Include relevant cases from:
- Normal success path.
- Empty or missing graph results.
- Invalid inputs and validation errors.
- Database unavailable, timeout, or query failure.
- LLM unavailable or malformed model output.
- Evidence/provenance: claims must refer to retrieved records and paths.
- Cross-session memory persistence and recall, if part of the spec.
- Security boundaries, including untrusted text in incident reports or retrieved documents.
- UI loading, empty, and error states, if applicable.

Do not assume every category applies; explain any important category that is not applicable.

## 3. Run tests
- Run the smallest relevant existing test set first, then appropriate broader checks if practical.
- Add tests only when the spec requires coverage that is missing. Do not edit production/application code.
- Do not run destructive commands, real incident mutations, or tests against production data.
- Prefer mocks/fakes for external LLM calls and deterministic graph fixtures for unit tests. Run integration tests only when the required local services and test configuration are available.
- Never print or expose secrets from environment files or logs.
- Record the exact commands run and their results. Do not report unrun tests as passing.

## 4. Diagnose failures
For every failure, report:
- Test and failing behavior.
- Expected behavior from the spec.
- Actual result.
- Likely root cause, with file/line references when available.
- Classification: implementation bug, test bug, environment/setup issue, or unclear.
- Suggested next action.

Do not modify production code or claim a failure is fixed.

## 5. Report
Produce:

### TraceMind Test Report — $ARGUMENTS
- **Coverage:** acceptance criteria tested and not tested.
- **Commands run:** exact commands and outcomes.
- **Passed / failed / blocked:** counts where available.
- **Failures:** diagnosis and likely cause.
- **Verdict:** `PASS`, `FAIL`, or `BLOCKED`.
- **Next step:** the smallest useful action to take.

A `PASS` verdict is allowed only when all applicable acceptance criteria were tested successfully. Use `BLOCKED` when important checks could not run.
