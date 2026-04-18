# Session Restart Prompt
# Copy and paste this into Claude Code at the start of every new session
# after an interruption.
# ─────────────────────────────────────────────────────────────────────

We are resuming an interrupted development session.

Please do the following before anything else:

1. Read `tasks_progress.md` in this project root.
2. Read the `## Resume From Here` section if it exists — that is your starting point.
3. Run `git log --oneline -10` to see the last 10 commits and confirm what was completed.
4. Run `git status` and `git diff` to assess any uncommitted or partial changes.
5. Give me a brief summary of:
   - What has been completed (ticked steps)
   - What is in progress or was interrupted
   - What the next action is
   - Whether any partial changes need to be cleaned up or completed first

Then ask me to confirm before proceeding.

From this point on, follow the task tracking protocol in your global CLAUDE.md:
- Update tasks_progress.md after every sub-step
- Commit after every main step
- If context is nearing its limit, update tasks_progress.md and commit before stopping
