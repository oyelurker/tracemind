---
description: Review TraceMind changes for correctness, security, graph reasoning, and maintainability
argument-hint: "[optional spec name]"
---

Review the current TraceMind changes. Do not edit files or fix findings during this command.

Optional spec: `$ARGUMENTS`

## 1. Pre-flight
- Inspect `git status`, unstaged diff, and staged diff.
- Review tracked changes and relevant untracked files without exposing secrets.
- If there are no meaningful changes, stop and report: "No changes detected. Implement a feature before running code review."
- If a spec name was supplied, confirm `.claude/specs/$ARGUMENTS.md` exists and read it. If it does not exist, stop. If no spec name was supplied, review against `CLAUDE.md` and existing project conventions.
- Read enough surrounding code to understand each changed line. Do not review only the diff in isolation.

## 2. Review dimensions
Review the changed code for:

### Correctness
- Does it satisfy the spec and preserve existing behavior?
- Are edge cases, error paths, types, and resource cleanup handled?
- Are API responses and UI states consistent?

### Graph and agent reasoning
- Are graph queries correct and appropriately scoped?
- Are user inputs passed as query parameters rather than concatenated into Cypher?
- Does the agent perform genuine graph retrieval/multi-hop reasoning where required, rather than pretending graph traversal occurred?
- Are returned answers supported by actual retrieved evidence and paths?
- Does the system clearly distinguish observed facts, inference, and unknowns?
- Is cross-session memory persisted and retrieved correctly when required?

### Security and privacy
- Are secrets, credentials, personal data, or internal errors exposed?
- Can untrusted logs, tickets, or documents manipulate the agent's instructions?
- Are API inputs validated and errors handled safely?
- Are access boundaries enforced if the app has multiple users or workspaces?
- Are unsafe dynamic queries, command execution, path traversal, or overly broad permissions introduced?

### Reliability and maintainability
- Are timeouts, retries, empty results, and unavailable services handled?
- Are external services mocked in unit tests where appropriate?
- Are dependencies necessary and configuration documented?
- Are there dead paths, duplicated logic, brittle assumptions, or unrelated changes?

## 3. Findings standard
- Report only actionable findings introduced by the changed code or directly blocking the feature.
- Do not report speculative issues as confirmed vulnerabilities.
- For each finding, include severity (`Critical`, `High`, `Medium`, `Low`), file and line, the concrete problem, impact, and a suggested fix.
- Separate verified findings from questions or suggestions.
- Do not invent line numbers, test results, or runtime behavior.
- If you run checks, record the exact command and result. Do not run destructive operations.

## 4. Final report
Use this format:

### TraceMind Code Review — [spec name or current changes]

**Critical / High**
- Findings, or `None found`.

**Medium / Low**
- Findings, or `None found`.

**Suggestions**
- Non-blocking improvements, clearly separated from defects.

**Checks**
- Commands run and actual outcomes, or `Not run`.

**Verdict**
- `CHANGES REQUESTED` — a correctness or security issue should be fixed before proceeding.
- `APPROVED WITH SUGGESTIONS` — no blocking finding; optional improvements remain.
- `APPROVED` — no actionable findings identified in the reviewed scope.

End by asking: "Do you want me to implement the action plan now?"
Wait for explicit confirmation before editing any files.
