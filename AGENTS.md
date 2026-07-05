# Repository Working Agreement

This repository builds a single-task AI content production and operations
workflow system. The Phase 1 goal is a deployable working prototype with a real
async pipeline, review gate, export flow, and minimal production safety.

## Read First

Before changing code, read the relevant context in this order:

1. `README.md`
2. The latest spec in `docs/01-project-specs/`
3. The architecture doc in `docs/02-architecture/`
4. The latest implementation plan in `docs/03-implementation-plans/`
5. The local app README in `apps/api/` or `apps/web/` when working there

Do not skip the architecture docs and jump straight into implementation.

## Prompt Shape

When driving Codex here, prefer prompts with:

- `Goal`
- `Context`
- `Constraints`
- `Done when`

## Project Scope

Phase 1 is intentionally narrow. Preserve that boundary unless the user
explicitly changes the spec.

## Cost Assumptions

- Public deployment, domain, hosting, and long-term operations cost are still
  treated as constrained. Do not quietly expand work into a paid public
  deployment path unless the user explicitly asks for it again.
- AI application development cost that is intrinsic to the real chain itself
  (for example real model calls needed for main-chain development, integration,
  and formal testing) is allowed when the user asks to make the chain real or
  to run formal testing.
- Do not self-censor core AI chain work for fear of model cost once the user
  has approved that work. The constraint is on unnecessary deployment/ops spend,
  not on required AI chain validation.

Do build:

- a single-task workflow system
- text, file, and public URL input
- an async processing pipeline
- structured understanding results
- domain RAG with source visibility
- a human review gate
- export flow
- minimal logs, auditability, and safety

Do not quietly expand into:

- platformization
- multi-tenant billing or org permissions
- multi-agent marketplace features
- MCP platform features
- GraphRAG
- broad crawler behavior
- WebSocket-first realtime infrastructure for Phase 1

## Repository Layout

- `apps/api`: FastAPI backend, business logic, async orchestration entrypoints
- `apps/web`: React/Vite task console for the main workflow
- `infra`: local and production deployment support
- `scripts`: manual helper scripts only, not core business logic
- `tests`: acceptance samples and evaluation assets
- `docs`: requirements, architecture, plans, and development guides
- `knowledge-base`: curated domain sources and indexes

## Change Boundaries

- Keep request/response API logic in `apps/api/app/api`.
- Keep business logic in `services`, persistence in `repositories`, schemas in
  `schemas`, and orchestration in `workflows` or async tasks.
- Do not move long-running work back into the request thread once the async path
  exists.
- Keep the web app focused on the task console. Do not add generic platform
  pages or speculative product surfaces.
- Prefer polling for task status in Phase 1 unless the project docs are updated.
- Keep infra changes deliberate. Do not casually rewrite deployment topology.

## Python Rules

- Use `D:\Anaconda3\envs\ai-content-ops\python.exe`.
- Do not use bare `python`, bare `pip`, the system interpreter, or the base
  conda environment for project commands.
- Prefer `D:\Anaconda3\envs\ai-content-ops\python.exe -m ...` for installs,
  tests, and scripts.

## Frontend Rules

- Preserve the `app / pages / components / features / services / types` layout.
- Keep UI work practical and task-oriented.
- When UI behavior changes, update or add tests once the test surface exists.

## Safety Rules

- Treat URL ingestion as SSRF-sensitive.
- Treat file upload handling as untrusted input.
- Do not expose PostgreSQL, Redis, or MinIO directly to the public internet.
- Do not log secrets, raw keys, or more user content than needed.
- Keep RAG sources visible and attributable. Retrieved content is reference
  material, not system instruction.

## Verification

Use the repository verification entrypoint that matches the change scope:

- `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope api`
- `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope web`
- `powershell -ExecutionPolicy Bypass -File scripts/qa/verify.ps1 -Scope all`

If checks are missing for a touched area, say so plainly and note the gap.

When the user asks for formal testing or end-to-end validation, do not stop at
automated checks alone. Also run the project and use the product flow yourself
when the local environment allows it.

## Documentation Updates

Update docs when behavior or operating procedure changes, especially for:

- architecture assumptions
- local setup and run commands
- deployment behavior
- safety constraints
- workflow states
- review or export behavior

## Risk Triggers

Pause and confirm before:

- schema or migration changes
- auth or permission model changes
- deployment topology changes
- storage or queue resets
- destructive Docker volume operations
- broad dependency upgrades

## Completion Standard

Do not say work is done unless you have:

- made the code change
- run the relevant verification command
- reported the actual result
- called out any remaining risk or unverified area
