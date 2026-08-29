# sdd: Spec Driven Development

A portable workflow for structured feature development with AI coding tools.

## Workflow

```
setup → brainstorm → plan → build → review → finish
```

| Command | Description |
|---------|-------------|
| `/sdd:setup` | Bootstrap SDD in a repo: AGENTS.md, CLAUDE.md import, directories, templates |
| `/sdd:brainstorm` | Explore an idea collaboratively, produce a mini-PRD, informed by past learnings |
| `/sdd:plan` | Convert mini-PRD or description to full spec + GitHub Issues, informed by past learnings |
| `/sdd:build` | Autonomous spec execution: dispatches a tiered agent per task by default, with a 3-round fix loop |
| `/sdd:review` | Review implementation or action existing review findings, via tiered dispatch |
| `/sdd:finish` | Verify review, merge PR, archive spec, compound learnings, cleanup |

## Installation

### Claude Code

```
/plugin marketplace add siimvd/agent-plugins
/plugin install sdd@agent-plugins
```

### Codex CLI / ChatGPT desktop

Codex CLI and the ChatGPT desktop app share the same plugin runtime, so one install covers both:

```
codex plugin marketplace add siimvd/agent-plugins
codex plugin add sdd@agent-plugins
```

Codex namespaces plugin skills as `<plugin>:<skill>`. Invoke with `$sdd:plan` in Codex CLI, or
pick from the `@` skill picker in ChatGPT. Names match Claude Code's `/sdd:plan` exactly.

`sdd/agents/*.md` (the tiered dispatch `/sdd:build` uses) is Claude Code-specific and not read by
Codex. Codex only reads `skills/<skill>/agents/openai.yaml` inside a skill, which is display
metadata, not a dispatch definition. Codex has its own subagent delegation (`spawn_agent`, with
`model` and `reasoning_effort` parameters), but `/sdd:build`'s dispatch instructions are written
for Claude Code's agent tiers and haven't been adapted to it, so `/sdd:build` under Codex runs
without tiered dispatch.

### OpenCode CLI

```bash
./sdd/scripts/build-opencode.sh
```

Generates `.opencode/commands/sdd-*.md` and `.opencode/agents/sdd-*.md` in the repo root, from
the canonical skill and agent definitions. Only helps someone working inside a checkout of this
repo: `.opencode/` is gitignored build output, not a distributable install. There is no
OpenCode marketplace install for this plugin yet (see Known Limits).

## Usage

In the examples below, `<feature>` is the name of your spec (e.g. `notification-preferences`,
`fix-login-bug`), mapping to `docs/specs/<feature>.md`.

### Setup

```
/sdd:setup
```

One-time command to bootstrap SDD in your repository. Creates or updates `AGENTS.md` with best
practices and SDD workflow instructions, wires `CLAUDE.md` to import it (Claude Code reads
`CLAUDE.md`, not `AGENTS.md`), creates `docs/specs/` and `docs/ideas/`, and copies spec templates.
Warns and offers a fix if either docs path is gitignored, since `/sdd:build` and `/sdd:finish`
commit them. Safe to run multiple times; skips what already exists.

### Brainstorm

```
/sdd:brainstorm "your idea description here"
/sdd:brainstorm "your idea" --fast
```

Explores an idea through conversation and produces a mini-PRD at `docs/ideas/<name>.md`. Surfaces
`docs/learnings/` entries whose tags or files overlap the problem area.

### Plan

```
/sdd:plan <feature>                       # from brainstorm output
/sdd:plan "fix login redirect bug"        # from scratch (inline description)
/sdd:plan <feature> --fast                # compressed mode
/sdd:plan <feature> --ticket JIRA-123     # link external tracker
```

Produces a full spec at `docs/specs/<name>.md` with requirements (problem, users, acceptance
criteria, scope), technical design (architecture, key files, decisions, patterns to follow),
ordered tasks (file paths and acceptance criteria per task), and GitHub Issues (epic + sub-issue
per task). Consults `docs/learnings/` before writing and states which learnings it used, or that
none applied.

### Build

```
/sdd:build <feature>
/sdd:build <feature> --inline
```

Reads `docs/specs/<name>.md` and executes all tasks autonomously in a 6-phase process:

1. **Setup**: create worktree, branch, draft PR, mark epic in-progress
2. **Execute**: dispatch `sdd-implementer` per task by default, review each with `sdd-reviewer`,
   run a 3-round fix loop on findings
3. **Verify**: full test suite, lint, typecheck
4. **Polish**: code simplification and security review via subagents
5. **Ship**: update PR body, mark ready for review
6. **Update**: comment on epic, show summary

Every dispatch goes to a tiered agent (`sdd/agents/`) with an explicit model, effort, and turn
cap, not the session default at unbounded turns. Artifacts (diffs, specs, briefs) are always
handed over as file paths, never pasted inline.

`--inline` implements every task in the current session instead of dispatching. Use it when
tasks are coupled enough that a fresh subagent would spend more turns re-deriving shared context
than it saves.

Must run in a fresh session: the spec file is complete context.

### Review

```
/sdd:review <feature>
/sdd:review <feature> --all
```

Auto-detects mode from PR state. **Perform mode** (no existing reviews) writes the diff once,
dispatches 4 parallel `sdd-reviewer` agents against it (spec compliance, bug hunting, security,
CLAUDE.md compliance), and posts prioritized findings as a PR comment. **Action mode**
(unresolved review comments exist) reads findings from humans or AI agents, fixes P1 and P2
automatically, and replies in comment threads; `--all` also fixes P3.

Verifies before implementing: pushes back on technically incorrect suggestions with reasoning.

### Finish

```
/sdd:finish <feature>
```

Finalizes a completed feature in a 5-phase process: verify (PR merged/approved, review findings
resolved), sync (update spec status, archive to `docs/specs/archive/`), compound (capture
learnings to `docs/learnings/`, update CLAUDE.md mistakes log), close (close all task issues and
the epic with summary comments), cleanup (remove worktree, delete local branch).

Merges the PR if approved but not yet merged (asks first). Warns on unresolved review findings
but doesn't hard-block.

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

## Managing your own session

SDD's skills manage the agent's context (worktrees, dispatch, ledgers). Your own conversation is
a separate thing to manage: use `/clear` between unrelated tasks so stale assumptions from a
finished spec don't carry into the next one, and `/compact` with explicit keep instructions when
a session runs long.

## Agent tiers

Every subagent SDD dispatches resolves to a definition in `sdd/agents/`, not the session default:

| Agent | Model | Effort | Turn cap | Tools |
|-------|-------|--------|----------|-------|
| `sdd-explorer` | haiku | medium | 15 | read-only |
| `sdd-implementer` | sonnet | medium | 40 | full |
| `sdd-reviewer` | sonnet | high | 25 | read-only |
| `sdd-final-reviewer` | opus | high | 30 | read-only |

To override a tier for your own project, define an agent with the same name in your own
`.claude/agents/`; it takes precedence over the plugin's.

## Portability

The canonical source is the Claude Code plugin (`skills/*/SKILL.md`, `agents/*.md`), read
directly by Codex and ChatGPT. `scripts/build-opencode.sh` generates equivalent output for
OpenCode, which doesn't read the source format natively:

- `.opencode/commands/sdd-*.md` and `.opencode/agents/sdd-*.md`
- `maxTurns` maps to OpenCode's documented `steps` field
- `effort` has no verified equivalent for the Anthropic models these agents use (OpenCode's
  provider-parameter passthrough is documented for OpenAI reasoning models, not Anthropic's) and
  is dropped, with a comment in the generated file naming what was lost and why

Skill-internal file references use Claude Code's `${CLAUDE_SKILL_DIR}` and `${CLAUDE_PLUGIN_ROOT}`
variables, substituted automatically by Claude Code. Codex and OpenCode don't substitute them, so
each reference carries a one-line fallback telling a model how to resolve it itself: as this
skill's own directory, or the plugin's root, using the file's known location.

## Known limits

- **No OpenCode consumer install.** `build-opencode.sh` output only helps someone working inside
  this repo. OpenCode discovers skills only at fixed paths with no configurable directory; a
  distributable install would need an OpenCode JS plugin (the pattern `obra/superpowers` uses:
  `"plugin": ["name@git+https://..."]` in `opencode.json`), which doesn't exist here yet.
- **Codex doesn't read `sdd/agents/*.md`.** See Installation above.
- **No public directory listing.** Both marketplaces install directly from this GitHub repo.

## Linting

```bash
bash sdd/scripts/lint.sh
```

Structural lint for every plugin registered in the marketplace: frontmatter shape,
`${CLAUDE_SKILL_DIR}`/`${CLAUDE_PLUGIN_ROOT}` references, leftover paste markers, required agent
fields, version agreement across a plugin's `plugin.json` files and both marketplace entries, and
build determinism. Runs Codex's own plugin validator too, when it's installed locally. Checks
structure, not behavior.

## License

MIT
