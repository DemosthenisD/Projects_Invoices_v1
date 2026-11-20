# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo contains unit tests for the IFRS17 Tool. The focus is on building and validating test combinations, not on application logic.

## Commands

```bash
npm install          # install dependencies
npm run dev          # start dev server
npm run build        # build the project
npm run test         # run all tests
npm run test <path>  # run a single test file
```

Git pushes require explicit user confirmation (configured in `.claude/settings.json`).

## Architecture

Use the following top-level folders:
- `frontend/` — UI components and views
- `backend/` — server-side logic and APIs
- `shared/` — types, utilities, and constants shared across frontend and backend

Do not reorganise files across these folders unless there is a clear reason.

## Repo Rules

- Keep the repo small and focused.
- Prefer small, focused files and functions; reuse existing patterns before adding new ones.
- Explain the plan before making major changes.
- Review design and architecture before finalising implementation.
- Run tests before suggesting a task is complete.
- Always ask before pushing to GitHub.

---

## General Behavioral Guidelines

*Workspace-level guidelines from `GitProject/CLAUDE.md`. Bias toward caution over speed; use judgment for trivial tasks.*

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.