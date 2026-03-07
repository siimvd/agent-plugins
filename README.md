# SDD — Spec Driven Development Plugin

An opinionated, portable workflow for structured feature development with AI coding tools.

## Workflow

```
setup → brainstorm → plan → build → review → finish
```

| Command | Status | Description |
|---------|--------|-------------|
| `/sdd:setup` | v0.6.0 | Bootstrap SDD in a repo: AGENTS.md, directories, templates |
| `/sdd:brainstorm` | v0.1.0 | Explore an idea collaboratively, produce a mini-PRD |
| `/sdd:plan` | v0.2.0 | Convert mini-PRD or description to full spec + GitHub Issues |
| `/sdd:build` | v0.3.0 | Autonomous spec execution with worktrees, commits, and PR |
| `/sdd:review` | v0.5.0 | Review implementation or action existing review findings |
| `/sdd:finish` | v0.4.0 | Verify review, merge PR, archive spec, compound learnings, cleanup |

## Installation

### Claude Code (plugin)

From within Claude Code, add the marketplace and install the plugin:

```
/plugin marketplace add siimvd/agent-sdd
/plugin install sdd@agent-sdd
```

### OpenCode CLI

Generate the OpenCode command from the canonical skill:

```bash
./sdd/scripts/build-opencode.sh
```

This creates `.opencode/commands/sdd-brainstorm.md`, `sdd-plan.md`, `sdd-build.md`, `sdd-review.md`, and `sdd-finish.md` in the repo root.

## Usage

### Setup

```
/sdd:setup
```

One-time command to bootstrap SDD in your repository. Creates or updates `AGENTS.md` with best practices and SDD workflow instructions, sets up `docs/specs/`, `docs/ideas/`, and copies spec templates. Safe to run multiple times — skips what already exists.

### Brainstorm

```
/sdd:brainstorm "notification preferences for users"
/sdd:brainstorm "notification preferences" --fast
```

Explores an idea through conversation and produces a mini-PRD at `docs/ideas/<name>.md`.

### Plan

```
/sdd:plan notification-preferences              # from brainstorm output
/sdd:plan "fix login redirect bug"              # from scratch
/sdd:plan notification-preferences --fast       # compressed mode
/sdd:plan notification-preferences --ticket JIRA-123  # link external tracker
```

Produces a full spec at `docs/specs/<name>.md` with:
- Requirements (problem, users, acceptance criteria, scope)
- Technical design (architecture, key files, decisions, patterns to follow)
- Ordered tasks (logical-unit level, with file paths and acceptance criteria)
- GitHub Issues (epic + sub-issues per task)

### Build

```
/sdd:build notification-preferences
/sdd:build notification-preferences --isolated-tasks
```

Reads `docs/specs/<name>.md` and executes all tasks autonomously in a 6-phase process:

1. **Setup** — create worktree, branch, draft PR, mark epic in-progress
2. **Execute** — TDD task loop with commits, issue updates, and adaptive reviews
3. **Verify** — full test suite, lint, typecheck
4. **Polish** — code simplification + security review via subagents
5. **Ship** — update PR body, mark ready for review
6. **Update** — comment on epic, show summary

**`--isolated-tasks`**: dispatches a fresh subagent per task with clean context (same worktree, sequential execution). Use for large specs (8+ tasks) or when prior task context could confuse later tasks.

Must run in a **fresh session** — the spec file is complete context.

### Review

```
/sdd:review notification-preferences
/sdd:review notification-preferences --all
```

Auto-detects mode based on PR state:

- **Perform Mode** (no existing reviews): runs 4 parallel review agents — spec compliance, bug hunting, security, CLAUDE.md compliance. Posts prioritized findings as a PR comment.
- **Action Mode** (unresolved review comments exist): reads findings from humans/AI agents, fixes P1 (critical) and P2 (high) automatically, replies in comment threads. Use `--all` to also fix P3 (low).

Verifies before implementing — pushes back on technically incorrect suggestions with reasoning.

### Finish

```
/sdd:finish notification-preferences
```

Finalizes a completed feature in a 5-phase process:

1. **Verify** — check PR is merged/approved, review findings resolved
2. **Sync** — update spec status, archive to `docs/specs/archive/`
3. **Compound** — capture learnings to `docs/learnings/`, update CLAUDE.md mistakes log
4. **Close** — close all task issues and epic with summary comments
5. **Cleanup** — remove worktree, delete local branch

Merges PR if approved but not yet merged (asks first). Warns on unresolved review findings but doesn't hard-block.

## Artifacts

| Step | Output | Location |
|------|--------|----------|
| Brainstorm | Mini-PRD | `docs/ideas/<name>.md` |
| Plan | Spec | `docs/specs/<name>.md` |
| Plan | GitHub Issues | Epic + sub-issues |
| Build | Implementation | Worktree on `feat/<branch>` |
| Build | Pull Request | Draft → ready for review |
| Build | Issue Updates | Real-time status via `gh` CLI |
| Review | PR Comment | Prioritized findings on PR |
| Review | Fixes | P1+P2 resolved, committed, pushed |
| Finish | Archived Spec | `docs/specs/archive/<name>.md` |
| Finish | Learnings | `docs/learnings/<category>/<name>.md` |
| Finish | Closed Issues | Epic + sub-issues closed |

## Portability

The canonical source is the Claude Code plugin (`skills/*/SKILL.md`). The build script generates equivalent commands for other tools:

- **OpenCode**: `scripts/build-opencode.sh` → `.opencode/commands/sdd-*.md`

## License

MIT
