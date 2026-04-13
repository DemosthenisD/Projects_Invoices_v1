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