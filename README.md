# SDD — Spec Driven Development Plugin

An opinionated, portable workflow for structured feature development with AI coding tools.

## Workflow

```
setup → brainstorm → plan → build → review → finish
```

| Command | Status | Description |
|---------|--------|-------------|
| `/sdd:setup` | v0.8.0 | Bootstrap SDD in a repo: AGENTS.md, CLAUDE.md import, directories, templates |
| `/sdd:brainstorm` | v0.8.0 | Explore an idea collaboratively, produce a mini-PRD, informed by past learnings |
| `/sdd:plan` | v0.8.0 | Convert mini-PRD or description to full spec + GitHub Issues, informed by past learnings |
| `/sdd:build` | v0.8.0 | Autonomous spec execution — dispatches a tiered agent per task by default, with a 3-round fix loop |
| `/sdd:review` | v0.8.0 | Review implementation or action existing review findings, via tiered dispatch |
| `/sdd:finish` | v0.8.0 | Verify review, merge PR, archive spec, compound learnings (with retrievable frontmatter), cleanup |

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

In the examples below, `<feature>` is the name of your spec (e.g. `notification-preferences`, `fix-login-bug`). This maps to `docs/specs/<feature>.md`.

### Setup

```
/sdd:setup
```

One-time command to bootstrap SDD in your repository. Creates or updates `AGENTS.md` with best practices and SDD workflow instructions, wires `CLAUDE.md` to import it (Claude Code reads `CLAUDE.md`, not `AGENTS.md`), creates `docs/specs/` and `docs/ideas/`, and copies spec templates. If either docs path is gitignored, it warns and offers a fix, since `/sdd:build` and `/sdd:finish` commit them. Safe to run multiple times — skips what already exists.

### Brainstorm

```
/sdd:brainstorm "your idea description here"
/sdd:brainstorm "your idea" --fast
```

Explores an idea through conversation and produces a mini-PRD at `docs/ideas/<name>.md`. If `docs/learnings/` has entries whose tags or files overlap the problem area, surfaces them in the conversation.

### Plan

```
/sdd:plan <feature>                       # from brainstorm output
/sdd:plan "fix login redirect bug"        # from scratch (inline description)
/sdd:plan <feature> --fast                # compressed mode
/sdd:plan <feature> --ticket JIRA-123     # link external tracker
```

Produces a full spec at `docs/specs/<name>.md` with:
- Requirements (problem, users, acceptance criteria, scope)
- Technical design (architecture, key files, decisions, patterns to follow)
- Ordered tasks (logical-unit level, with file paths and acceptance criteria)
- GitHub Issues (epic + sub-issues per task)

Consults `docs/learnings/` before writing the spec and states which learnings it used, or that none applied.

### Build

```
/sdd:build <feature>
/sdd:build <feature> --inline
```

Reads `docs/specs/<name>.md` and executes all tasks autonomously in a 6-phase process:

1. **Setup** — create worktree, branch, draft PR, mark epic in-progress
2. **Execute** — dispatches `sdd-implementer` per task by default, reviews each with `sdd-reviewer`, runs a 3-round fix loop on findings
3. **Verify** — full test suite, lint, typecheck
4. **Polish** — code simplification + security review via subagents
5. **Ship** — update PR body, mark ready for review
6. **Update** — comment on epic, show summary

Every dispatch goes to a tiered agent (`sdd/agents/`) with an explicit model, effort, and turn cap — never the session default at unbounded turns. Artifacts (diffs, specs, briefs) are always handed over as file paths, never pasted inline.

**`--inline`**: implement every task in this session instead of dispatching. Use when tasks are tightly coupled enough that a fresh subagent would spend more turns re-deriving shared context than it saves.

Must run in a **fresh session** — the spec file is complete context.

### Review

```
/sdd:review <feature>
/sdd:review <feature> --all
```

Auto-detects mode based on PR state:

- **Perform Mode** (no existing reviews): writes the diff once, dispatches 4 parallel `sdd-reviewer` agents against that file — spec compliance, bug hunting, security, CLAUDE.md compliance. Posts prioritized findings as a PR comment.
- **Action Mode** (unresolved review comments exist): reads findings from humans/AI agents, fixes P1 (critical) and P2 (high) automatically, replies in comment threads. Use `--all` to also fix P3 (low).

Verifies before implementing — pushes back on technically incorrect suggestions with reasoning.

### Finish

```
/sdd:finish <feature>
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

## Managing Your Own Session

SDD's skills manage the agent's context — worktrees, dispatch, ledgers. Your own conversation is a separate thing to manage:

- **Use `/clear` between unrelated tasks.** Context drift is real; starting fresh after finishing a spec avoids carrying stale assumptions into the next one.
- **Use `/compact` with explicit keep instructions** when a session gets long, so what survives is what you actually still need.

## Agent Tiers

Every subagent SDD dispatches resolves to a definition in `sdd/agents/`, not the session default:

| Agent | Model | Effort | Turn cap | Tools |
|-------|-------|--------|----------|-------|
| `sdd-explorer` | haiku | low | 15 | read-only |
| `sdd-implementer` | sonnet | medium | 40 | full |
| `sdd-reviewer` | sonnet | high | 25 | read-only |
| `sdd-final-reviewer` | opus | high | 30 | read-only |

To override a tier for your own project, define an agent with the same name in your own `.claude/agents/` — it takes precedence over the plugin's.

## Portability

The canonical source is the Claude Code plugin (`skills/*/SKILL.md`, `agents/*.md`). The build script generates equivalent output for other tools:

- **OpenCode**: `scripts/build-opencode.sh` → `.opencode/commands/sdd-*.md` and `.opencode/agents/sdd-*.md`. `effort` and `maxTurns` have no OpenCode equivalent and are dropped, with a comment in the generated file naming what was lost.

## License

MIT
