# Global Claude Code Instructions
# Save this file at: C:\Users\d.demosthenous\.claude\CLAUDE.md
# These instructions apply to ALL projects automatically.

## Task Tracking & Progress Protocol

These rules apply to every development task, in every project, every session.

### At the Start of Any New Task

Before writing a single line of code, create or update `tasks_progress.md` in the
project root with the full plan structured as follows:

```
# Task: <short title>
# Started: <date>
# Status: IN PROGRESS

## Main Steps
- [ ] 1. <Main Step Title>
  - [ ] 1.1 <sub-step>
  - [ ] 1.2 <sub-step>
- [ ] 2. <Main Step Title>
  - [ ] 2.1 <sub-step>
  ...

## Log
| Timestamp | Step | Action | Notes |
|-----------|------|---------|-------|
```

If `tasks_progress.md` already exists in the project, read it first and continue
from the last incomplete step — do not start over.

### After Every Sub-Step

Immediately after completing any sub-step (e.g. 1.1, 1.2):
1. Mark it `[x]` in `tasks_progress.md`
2. Add a row to the Log table with a brief description of what was done
3. Save the file

Do not proceed to the next sub-step until `tasks_progress.md` is updated.

### After Every Main Step

After all sub-steps of a main step are complete:
1. Mark the main step `[x]` in `tasks_progress.md`
2. Stage and commit all changes:
   ```
   git add .
   git commit -m "complete: <main step title> — <one line summary>"
   ```
3. Then continue to the next main step

### When Approaching Usage Limits (~95% through context)

When you estimate the context window is nearly full:
1. Immediately stop any in-progress code changes at a safe breakpoint
2. Update `tasks_progress.md`: mark completed sub-steps, add a log entry
   noting exactly where work was interrupted and what the next action is
3. Make a git commit even if mid-main-step:
   ```
   git commit -m "wip: <step title> — interrupted, see tasks_progress.md"
   ```
4. Write a clear `## Resume From Here` section at the top of `tasks_progress.md`
   describing the exact next action needed

### Tasks Progress File Format

Keep `tasks_progress.md` in the project root. Never delete it between sessions —
it is the source of truth for resuming work. Archive completed tasks at the bottom
under `## Completed Tasks` rather than deleting them.
