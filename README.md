# agent-plugins

Opinionated plugins for AI coding tools.

| Plugin | Version | Description |
|--------|---------|-------------|
| `sdd` | 0.8.0 | Spec Driven Development workflow — the rest of this README |
| [`tools`](./tools/README.md) | 0.1.0 | Standalone developer utilities. Scaffold; no skills yet |

Works in Claude Code, Codex CLI, and the ChatGPT desktop app natively; OpenCode via a generated
build step. See Installation and Portability below for exact commands and per-tool limits.

---

# sdd — Spec Driven Development

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
/plugin marketplace add siimvd/agent-plugins
/plugin install sdd@agent-plugins
```

`tools` installs the same way (`/plugin install tools@agent-plugins`), but it is still an
empty scaffold — see [tools/README.md](./tools/README.md).

### Codex CLI / ChatGPT desktop

Codex CLI and the ChatGPT desktop app share the same plugin runtime — one install covers both:

```
codex plugin marketplace add siimvd/agent-plugins
codex plugin add sdd@agent-plugins
codex plugin add tools@agent-plugins
```

Codex namespaces plugin skills as `<plugin>:<skill>`. Invoke with `$sdd:plan` in Codex CLI, or
pick from the `@` skill picker in ChatGPT — names match Claude Code's `/sdd:plan` exactly.

Verified end-to-end with `codex-cli 0.150.1`: both plugins install cleanly from this repo, and the
model-visible skill list shows `sdd:brainstorm`, `sdd:build`, `sdd:plan`, `sdd:review`,
`sdd:setup`, `sdd:finish` (`tools` correctly contributes none). This installs the marketplace
directly from GitHub — the plugins are not submitted to OpenAI's public plugin directory.

**What doesn't come along**: `sdd/agents/*.md` — the tiered-dispatch definitions `/sdd:build`
reads for its per-task agent tiers — are Claude-Code-specific and not read by Codex. Codex only
reads `skills/<skill>/agents/openai.yaml` inside a skill, which is presentation metadata (display
name, icon), not a dispatch definition. Codex does have its own subagent delegation
(`spawn_agent`, with `model` and `reasoning_effort` parameters), but `/sdd:build`'s dispatch
instructions are written for Claude Code's agent tiers and haven't been adapted to it — so
`/sdd:build` under Codex runs without the tiered dispatch, not with an equivalent one.

### OpenCode CLI

Generate the OpenCode command from the canonical skill:

```bash
./sdd/scripts/build-opencode.sh
```

This creates `.opencode/commands/sdd-brainstorm.md`, `sdd-plan.md`, `sdd-build.md`, `sdd-review.md`, and `sdd-finish.md` in the repo root.

This only helps someone working inside a checkout of *this* repo — `.opencode/` is gitignored
build output, not a distributable install. There is currently no consumer install path for
OpenCode users outside this repo; see Known Limits below.

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

The canonical source is the Claude Code plugin (`skills/*/SKILL.md`, `agents/*.md`), read directly
by Codex and ChatGPT, plus a build script that generates equivalent output for tools that don't
read the source format natively:

- **Codex / ChatGPT**: `.codex-plugin/plugin.json` per plugin, catalogued in
  `.agents/plugins/marketplace.json` at the repo root. No build step — Codex reads
  `skills/*/SKILL.md` directly. See Installation above for commands and what doesn't port.
- **OpenCode**: `scripts/build-opencode.sh` → `.opencode/commands/sdd-*.md` and
  `.opencode/agents/sdd-*.md`. `maxTurns` maps to OpenCode's documented `steps` field. `effort` has
  no verified equivalent for the Anthropic models these agents use (OpenCode's provider-parameter
  passthrough is documented for OpenAI reasoning models, not Anthropic's) and is dropped, with a
  comment in the generated file naming what was lost and why.

Each plugin owns its own build script. `tools/scripts/build-opencode.sh` does the same job for
`tools`, discovering skills and inline files instead of listing them.

Skill-internal file references use Claude Code's `${CLAUDE_SKILL_DIR}` and `${CLAUDE_PLUGIN_ROOT}`
variables, which Claude Code substitutes automatically. Codex and OpenCode don't substitute them,
so each reference carries a one-line fallback instruction for a model to resolve it itself.
Verified live on Claude Code 2.1.251 that a bare relative path — the alternative — fails on first
read and only recovers by the model guessing the real location, so the variables are kept rather
than replaced.

## Known Limits

- **No OpenCode consumer install.** `build-opencode.sh` output only helps someone working inside
  this repo. OpenCode discovers skills only at fixed paths with no configurable directory; a
  distributable install would need an OpenCode JS plugin (the pattern `obra/superpowers` uses:
  `"plugin": ["name@git+https://..."]` in `opencode.json`), which does not exist here yet.
- **Codex doesn't read `sdd/agents/*.md`.** See the Codex section under Installation — the tiered
  dispatch `/sdd:build` relies on is Claude-Code-specific and has no Codex port yet, even though
  Codex has its own (differently-shaped) subagent delegation.
- **No public directory listing.** Both marketplaces install directly from this GitHub repo.
  Neither plugin is submitted to Anthropic's or OpenAI's public plugin directories.

## Linting

```bash
bash sdd/scripts/lint.sh
```

Structural lint for every plugin registered in `.claude-plugin/marketplace.json` — frontmatter shape, `${CLAUDE_SKILL_DIR}`/`${CLAUDE_PLUGIN_ROOT}` references, leftover paste markers, required agent fields, per-plugin version agreement between `plugin.json` and both the Claude Code and Codex marketplace entries, Codex marketplace membership, and build determinism. When Codex's own bundled validator is installed locally, lint runs it against every plugin too. It checks structure, not behavior.

## License

MIT
