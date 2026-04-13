<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# yes

Yes — here is a **one-page checklist version** you can send directly to the intern, plus a clear answer on how `CLAUDE.md` behaves after it is created. Claude Code loads `CLAUDE.md` files at the start of every session, and project `CLAUDE.md` can live either at the repo root or in `.claude/CLAUDE.md`.[^1][^2]

## Intern checklist

### Objective

Set up the MVP repository on GitHub, clone it locally, and configure Claude Code so it can work inside the repo with project rules and safe permissions.[^2][^1]

### Required

- GitHub account.[^2]
- Git installed locally.[^2]
- Terminal access.
- Claude Code installed.
- Access to create a GitHub repository.


### Steps

1. Create a new GitHub repository named `my-mvp`, preferably as a private repo, and initialize it with a README.[^2]
2. Open Terminal and go to your projects folder:
```bash
cd ~/Projects
```

3. Clone the repository locally:
```bash
git clone https://github.com/YOUR-USERNAME/my-mvp.git
cd my-mvp
```

GitHub’s documented cloning flow is to copy the repository URL, run `git clone`, and then work inside the cloned folder.[^2]

4. Create the starting project structure:
```bash
mkdir -p frontend backend shared .claude
touch README.md CLAUDE.md
```

5. Check that Git is working:
```bash
git status
git remote -v
```

6. Create `.claude/settings.json` with the project permission rules. Claude Code uses project settings in `.claude/settings.json` for shared repo behavior.[^2]

Example:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(npm install)",
      "Bash(npm run dev)",
      "Bash(npm run build)",
      "Bash(npm run test *)"
    ],
    "ask": [
      "Bash(git push *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  }
}
```

Claude Code’s settings docs explicitly support `allow`, `ask`, and `deny` permission rules in project settings files.[^2]

7. Add the project rules to `CLAUDE.md`. Claude Code reads `CLAUDE.md` files as persistent project instructions at session start.[^1]

Example:

```md
# Project Instructions

## Repo rules
- Keep the repo small and focused.
- Use `frontend/`, `backend/`, and `shared/` folders unless told otherwise.
- Do not move files unless necessary.

## Code rules
- Keep code organized and readable.
- Prefer small, focused files and functions.
- Reuse existing patterns before creating new ones.

## Workflow rules
- Explain the plan before making major changes.
- Review design and architecture before finalizing implementation.
- Run tests before suggesting completion.
- Ask before pushing to GitHub.
```

8. Save and commit the setup files:
```bash
git add .
git commit -m "Initial project setup"
git push --set-upstream origin HEAD
```

GitHub’s quickstart uses the same basic first-push flow after files are added to the repository.[^2]

9. Start Claude Code from the repo root:
```bash
claude
```

10. Inside Claude Code, use `/config` if needed to review active settings. Claude Code docs state that `/config` opens the settings interface for configuration review and editing.[^2]
11. Report back with:

- GitHub repo URL.
- Output of `git status`.
- Output of `git remote -v`.
- Confirmation that `CLAUDE.md` exists.
- Confirmation that `.claude/settings.json` exists.
- Confirmation that Claude Code opens successfully in the repo.


## What happens after creating `CLAUDE.md`

Once `CLAUDE.md` exists, Claude Code treats it as project memory and loads it into the context of every new session started in that working directory.[^1]

## Do you need to commit it?

You only need to commit `CLAUDE.md` if you want it versioned in Git and shared with the team; Claude does not require a Git commit in order to read it locally.[^1]

## Do you need to reload Claude?

If Claude Code was already running before the file was created, the safest approach is to start a new session or use `/memory` to verify the file is loaded, because `CLAUDE.md` files are guaranteed to load at launch, not necessarily immediately mid-session.[^1]

## Does Claude automatically know about it?

Yes for new sessions: Claude Code reads `CLAUDE.md` automatically at session start, and it also loads matching ancestor `CLAUDE.md` files for the current working directory.[^1]

If you add `CLAUDE.md` during an already-open session, Claude may not reliably behave as if it has fully reloaded that file until you restart the session or explicitly check memory loading with `/memory`.[^1]

## Best practice

Use this sequence after creating or editing `CLAUDE.md`:

- Save the file.
- Commit it if the team should share it.
- Restart Claude Code or start a fresh session in the repo root.
- Run `/memory` if you want to confirm the file is being loaded.[^1]

If you want, I can next give you:

- a **manager version** of this checklist, or
- a **copy-paste onboarding message** you can send to the intern in Slack or email.
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^3][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://www.youtube.com/watch?v=aQvpqlSiUIQ

[^2]: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

[^3]: https://institute.sfeir.com/en/claude-code/claude-code-memory-system-claude-md/deep-dive/

[^4]: https://code.claude.com/docs/en/memory

[^5]: https://www.reddit.com/r/ClaudeCode/comments/1ouaqbq/when_does_claude_read_claudemd_files_and_which/

[^6]: https://github.com/anthropics/claude-code/issues/5442

[^7]: https://news.ycombinator.com/item?id=46098838

[^8]: https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with

[^9]: https://docs.megallm.io/en/agents/claude

[^10]: https://github.com/anthropics/claude-code/issues/7644

[^11]: https://www.humanlayer.dev/blog/writing-a-good-claude-md

[^12]: https://claudecode.jp/en/docs/claudecode/claude-code-settings

[^13]: https://code.claude.com/docs/en/overview

[^14]: https://ccforpms.com/fundamentals/project-memory

[^15]: https://github.com/feiskyer/claude-code-settings

[^16]: https://opencode.ai/docs/rules/

[^17]: https://lobehub.com/ru/skills/hlibkoval-claudemd-memory-doc

