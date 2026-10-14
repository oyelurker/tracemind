---
description: Create a focused, testable TraceMind feature specification
argument-hint: "<feature name or goal>"
---

Create a feature specification for TraceMind. Do not implement the feature in this command.

User request: $ARGUMENTS

## 1. Validate the request
- If `$ARGUMENTS` is empty, stop and ask what feature to specify.
- Inspect the repository before making assumptions. Read `CLAUDE.md` if present, inspect the directory structure, existing specs in `.claude/specs/`, and the relevant source and test files.
- If this is a new/mostly empty repository, make the spec an incremental first step rather than pretending existing components are present.
- Do not overwrite an existing spec. If the requested feature overlaps an existing spec, explain the overlap and ask whether to update it or specify a distinct feature.

## 2. Keep the scope small
- Define one demonstrable feature that can be completed and tested independently.
- Prefer a thin end-to-end slice over broad scaffolding.
- For graph work, identify the relevant node labels, relationship types, properties, and Cypher operations.
- For agent work, define inputs, graph retrieval, evidence requirements, output shape, and failure behavior.
- For memory work, define what is stored, how it is retrieved in a later session, and how stale or conflicting memories are handled.
- Do not add dependencies unless the feature needs them. Explain why each proposed dependency is necessary.
- Never invent existing APIs, schemas, files, or environment variables; verify them or mark them as proposed.

## 3. Write the spec
Create `.claude/specs/<NN>-<feature-slug>.md`, where `<NN>` is the next available two-digit sequence and the slug is lowercase kebab-case. If numbering cannot be inferred safely, ask before writing.

Use this structure:

# Spec: <Feature title>

## Goal
What the user can demonstrate when this feature is complete.

## User-visible behavior
Concrete input, expected behavior, and output.

## Scope
### In scope
- ...

### Out of scope
- ...

## Existing code and assumptions
List the files, interfaces, and conventions inspected. Separate verified facts from proposed decisions.

## Design
Explain the smallest workable design and the request/data flow.

## Graph model and queries
Specify relevant node labels, relationship types, properties, indexes/constraints if needed, and example Cypher patterns. If the feature does not use the graph, explain why.

## API contract
List endpoints, request/response examples, validation, and error cases. If no API changes are needed, say so.

## UI changes
List screens/components and loading, empty, success, and error states. If no UI changes are needed, say so.

## Persistence and memory
Describe what is persisted, its scope, how it is retrieved across sessions, and what must not be stored. If not applicable, say so.

## Files to create or modify
List expected paths and why. Mark paths as proposed if they do not exist yet.

## Testing
List unit, integration, and end-to-end checks that can verify the behavior. Include graph-query and failure-path tests when relevant.

## Security and reliability
Cover input validation, secrets, prompt injection from retrieved documents, data boundaries, timeouts, and safe error messages as applicable.

## Acceptance criteria
Use a checklist of observable, testable outcomes.

## Implementation notes
Constraints and decisions the implementation must follow.

## Open questions
Only unresolved questions that genuinely block implementation. Do not ask questions that repository inspection can answer.

## 4. Finish
- Write only the spec file in this command; do not edit application code, install packages, or run migrations.
- Report the spec path, goal, and acceptance criteria briefly.
- Ask the user to review the spec before implementation.
