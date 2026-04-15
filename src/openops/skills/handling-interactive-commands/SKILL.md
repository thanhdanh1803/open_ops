---
name: handling-interactive-commands
description: Handle interactive CLI commands safely using tmux (local execution only)
version: 1.0.0
author: OpenOps Team
risk_level: write
requires:
  cli: tmux
  install: brew install tmux
---

# Handling Interactive Commands

## Goal

Use tmux to run commands that require a real terminal (TTY) so the user can interact (type passwords, confirm prompts, use editors/pagers/TUIs), while still capturing a transcript back into the chat.

This skill provides *guardrails and a preferred workflow*; you can still rely on your general tmux knowledge whenever it helps.

## When to Use (Interactive Signals)

Use interactive mode when you see or expect:
- Commands cannot run or throw error wnen running in non-interactive terminal.
- Password prompts or MFA prompts (`sudo`, `ssh`, `scp`, `sftp`, `git` over SSH, cloud CLIs that open login flows)
- Editors/pagers/TUIs (`vim`, `nano`, `less`, `more`, `top`, `htop`, `fzf`, `git rebase -i`, `git commit` without `-m`)
- Installers / CLIs that ask questions (package managers, `*_init`, `*_configure`, `*_login`)
- Anything that prints “Press any key”, “Select…”, “Continue?”, or waits for input

## Prefer Non-Interactive First (When Possible)

Before using interactive mode, try to make the command non-interactive:
- Add “yes” flags: `--yes`, `-y`, `--confirm`, `--force` (when safe)
- Disable pagers: `--no-pager`, `GIT_PAGER=cat`, `PAGER=cat`, `LESS=-FRX`
- Set CI mode where supported: `CI=1`
- Provide inputs via stdin for simple prompts (only when safe and clear)

If that fails or is risky/unclear, switch to interactive mode.

## How to Use (Preferred)

Use the tool:
- `interactive_execute_tmux(command, timeout_s=...)`

Behavior:
- A temporary tmux session is created.
- The command runs inside tmux.
- Output is captured from the pane into a transcript.
- The user is attached to tmux to interact.
- The user detaches (`Ctrl-b` then `d`) or exits the shell to return.
- The tool returns a transcript so the agent can continue with evidence.

Important:
- The transcript may include sensitive output. Avoid printing secrets; prefer token env vars and masked inputs when possible.

## Simple tmux basics (for the user)

- Attach/detach:
  - Detach: `Ctrl-b` then `d`
  - Exit: type `exit` to close the shell
- List sessions: `tmux ls`
- Kill a session: `tmux kill-session -t <name>`

## Failure Handling

If tmux is missing:
- Ask permission to install it (macOS): `brew install tmux`
- Re-run the interactive flow after tmux is installed.

If the command got stuck:
- Detach and kill the session (`tmux kill-session -t <name>`) and retry with safer flags, or break the task into smaller steps.
