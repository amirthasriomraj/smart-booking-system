# CLAUDE.md

Persistent working instructions for Claude Code in this repository. This file does not restate product or architectural requirements — see **Source of Truth** below for those.

## Source of Truth

- `docs/PRODUCT_REQUIREMENTS_DOCUMENT.md` — frozen Version 1 PRD.
- `docs/TECHNICAL_ARCHITECTURE_SPECIFICATION.md` — frozen Version 1 TAS.
- `docs/IMPLEMENTATION_DECISIONS.md` — approved implementation-time clarifications and decisions made where the frozen PRD/TAS was ambiguous or required explicit resolution.
- `docs/IMPLEMENTATION_PLAN.md` — approved V1 implementation milestone scope and sequencing.

The PRD and TAS are frozen and remain the primary source of V1 requirements and architecture.
`IMPLEMENTATION_DECISIONS.md` records explicitly approved post-freeze clarifications where implementation required a decision.
`IMPLEMENTATION_PLAN.md` records the approved implementation sequence and milestone boundaries.
Do not add, remove, change, defer, or move implementation decisions or milestone scope without explicit user approval.

## Project Nature

This is an **evolution of an existing, working application** — not a rewrite. The starting codebase (flat `User`/`Booking` model) is being built out incrementally toward the frozen V1 PRD/TAS scope under a one-month delivery target.

- Implement one approved milestone at a time. Do not jump ahead or batch multiple milestones.
- Refactor existing code only when the current feature genuinely requires it. No repository-wide restructuring as a standalone step.
- Preserve existing working functionality and backward compatibility unless a milestone explicitly requires a change.
- Do not add features, endpoints, or models outside frozen V1 scope.
- Do not silently narrow, cut, or defer mandatory V1 requirements to fit the one-month target — flag scope/timeline tension to the user instead of resolving it unilaterally.

## Engineering Conventions

- Use Alembic for all database schema changes (`backend/alembic/`). Migrations are additive/backward-compatible unless a milestone explicitly calls for altering existing tables.
- Add tests for new behavior; run the full regression suite before declaring a milestone complete.
- Prefer focused, targeted repository inspection (specific files/directories) over repeated full-repo scans.
- Don't launch subagents/background agents by default — only when they provide clear value for a genuinely complex, parallelizable task.
- Keep responses and implementation work scoped and concise to conserve usage.

## Git Discipline

- Never commit unless explicitly instructed.
- Never push unless explicitly instructed.
- Don't modify or delete files unrelated to the current task.
- Don't run destructive Git commands (`reset --hard`, `checkout --`, force operations, etc.) without explicit instruction.

## Milestone Completion Report

At the end of each milestone, report and then stop for review (don't proceed to the next milestone unprompted):

1. Files created/modified
2. Migrations / schema changes
3. API endpoints added/changed
4. Tests added and their results
5. Deviations from the approved plan
6. Remaining risks/issues

## Project Structure

- `backend/` — FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis. Routers in `backend/routers/`, models in `backend/models.py`, migrations in `backend/alembic/versions/`, tests in `backend/tests/`.
- `frontend/` — React + Vite.
- `docs/` — frozen PRD and TAS (see Source of Truth above).
