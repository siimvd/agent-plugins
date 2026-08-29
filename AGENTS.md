# AGENTS.md

This file provides guidance to AI Agents such as Claude Code (claude.ai/code), Opencode and others when working with code in this repository.

## CORE PRINCIPLES

- **Context is the bottleneck, not intelligence.** Guard your context window. Trim aggressively. Write state to disk.
- **Plan before you code.** Never implement without a written, approved plan. Thinking is cheaper than debugging.
- **Keep it simple.** Minimal diffs. No unnecessary abstractions. Don't add what wasn't asked for.
- **Verify empirically.** No "it should work." Run it, test it, prove it.
- **Compound your work.** Every task should leave the codebase easier to work with than you found it.

---

## BEFORE WRITING ANY CODE

1. **Read AGENTS.md**, project state files, and recent git history
2. **Restate the goal** and what success looks like if there is any question or intent or clarity (the why or the what)
3. **Ask at most one clarifying question** if genuinely ambiguous — don't pepper the user

---

## PLANNING

For anything beyond a trivial change:

1. Write a plan as a checklist — each task specifies: **files to change, what to do, how to verify, and done criteria**
2. Save the plan to disk so it survives context resets
3. Get approval before implementing

**Size rules — where quality degrades:**

| Scope       | Limit                             |
| ----------- | --------------------------------- |
| Single task | < 200 lines changed               |
| Plan        | 5–8 tasks max (split beyond that) |
| AGENTS.md / CLAUDE.md | < 200 lines each (Anthropic's documented threshold) |
| Single PR   | < 500 lines (human-reviewable)    |

**Anti-overengineering (especially important with Opus):**

- Only make changes that are directly requested or clearly necessary
- Don't add features, refactor, or "improve" beyond the ask
- Don't create abstractions for one-time operations
- Don't add error handling for scenarios that can't happen
- Only validate at system boundaries (user input, external APIs)
- A bug fix doesn't need surrounding code cleaned up

---

## The THREE-FAILURE RULE
If you fail at the same thing 3 times: **stop.** Document what you tried, reassess your approach, and ask for guidance. Do not spiral into circular debugging.

---

## VERIFICATION

Before declaring anything complete:

1. Re-read every changed file via `git diff`
2. Confirm: builds, tests pass, linter passes, types check
3. Check for hardcoded values, missing error handling, security issues
4. Verify the feature actually works end-to-end
5. Summarize what changed, why, and any known limitations

**Never bypass .gitignore.** Do not `git add -f` a gitignored file — it is excluded for a reason. If you believe it should be tracked, ask the user first.

---

## CONTEXT MANAGEMENT

- **Keep AGENTS.md lean.** Overview in root, details in subdirectory AGENTS.md files. Use progressive disclosure.
- **CLAUDE.md imports AGENTS.md.** Claude Code reads `CLAUDE.md`, not `AGENTS.md` — instructions belong in `AGENTS.md` only, so there is a single source.
- **Write state to disk**, not just conversation. Plans, decisions, and progress belong in files.
- **Use subagents for research** — they run in their own context window and return only the distilled result.
- **Use git log for context continuity** — recent commits are the cheapest way to restore context between sessions.

---

## DEBUGGING

1. Reproduce it reliably (write a failing test if possible)
2. Read the error message — the answer is often right there
3. Form a hypothesis about the root cause
4. Verify with the minimal possible change
5. Fix the cause, not the symptom
6. Never shotgun-debug with random changes

---

## COMMUNICATION

- **Starting:** State what you understand and your approach (2–3 sentences)
- **During:** Report at natural checkpoints; flag blockers immediately
- **Done:** Summarize changes with specific files; note follow-ups
- Be concise, direct, and honest about what you did and didn't verify

---

## AFTER COMPLETION

1. **Update AGENTS.md** with anything discovered: new commands, patterns, gotchas, decisions
2. **Document novel solutions** so the next session benefits
3. **Update state/planning files** to reflect actual progress

Each cycle should make the next cycle easier — not harder.

---

## Spec Driven Development (SDD)

This project uses the SDD workflow (https://github.com/siimvd/agent-plugins) for structured feature development. SDD provides a repeatable process from idea to shipped feature.

### Workflow

```
brainstorm -> plan -> build -> review -> finish
```

| Command | Description |
|---------|-------------|
| `/sdd:brainstorm` | Explore an idea collaboratively, produce a mini-PRD |
| `/sdd:plan` | Convert mini-PRD or description to full spec + GitHub Issues |
| `/sdd:build` | Autonomous spec execution with worktrees, commits, and PR |
| `/sdd:review` | Review implementation or action existing review findings |
| `/sdd:finish` | Verify review, merge PR, archive spec, compound learnings, cleanup |

### Directory Structure

```
docs/
  ideas/          <- brainstorm output (mini-PRDs)
  specs/          <- plan output (full specs, the source of truth for builds)
    .templates/   <- spec templates
    archive/      <- finished specs (moved here by /sdd:finish)
  learnings/      <- compounded knowledge (created by /sdd:finish)
```

### Conventions

- **Specs are the source of truth** — `/sdd:build` executes from the spec file, not from conversation context
- **One spec per feature** — each spec lives at `docs/specs/<name>.md`
- **GitHub Issues track progress** — `/sdd:plan` creates an epic + sub-issues; `/sdd:build` updates them
- **Worktrees isolate work** — builds run in `.worktrees/<name>` to avoid disrupting your working tree
- **Learnings compound** — `/sdd:finish` captures patterns, gotchas, and mistakes for future sessions

### Portability

`/sdd:*` is Claude Code's invocation syntax. Working in Codex CLI or the ChatGPT desktop app, use
`$sdd:plan` (or the `@` skill picker) — same skill, different prefix. See the root
[README.md](./README.md#installation) for the full per-tool install matrix and known limits
(OpenCode has no consumer install path yet; Codex doesn't read `sdd/agents/*.md`'s tiered
dispatch).

---

## QUICK MODE (Small Tasks)

For bug fixes, config changes, or anything under 30 minutes:

1. Understand the ask
2. Create a GitHub issue (`gh issue create`) — even for small fixes
3. Search for relevant code
4. Make the minimal change on a dedicated branch
5. Test and lint
6. Commit, push, raise a PR referencing the issue
7. Comment on the issue with the PR link

Skip planning ceremony. Keep quality standards.
