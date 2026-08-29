---
name: build
description: >-
  This skill should be used when the user invokes "/sdd:build", says
  "build this feature", "implement the spec", "execute the plan",
  "start building", or wants to implement all tasks from a spec file.
  Reads docs/specs/<name>.md and executes tasks autonomously with
  commits, issue updates, and a PR at the end.
---

# Build — Spec Driven Development

Execute a spec autonomously: create an isolated worktree, work through tasks, commit after each, update issues in real-time, and open a PR when done. The human reviews the PR, not the process.

This is the third step of the SDD workflow: **brainstorm -> plan -> build -> review -> finish**.

## Fresh Session Requirement

**Build MUST run in a fresh session.** The spec file is the complete context — no prior conversation history needed. The single-file spec design exists for exactly this: one read, full context, clean execution.

## Invocation

```
/sdd:build <name>
/sdd:build <name> --inline
```

Parse `$ARGUMENTS` for:
- `<name>` — matches a `docs/specs/<name>.md` spec file
- `--inline` — implement every task in this session instead of dispatching a fresh `sdd-implementer` per task (see `--inline Mode` below)

---

## 6-Phase Process

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 1.Setup  │─▶│ 2.Execute│─▶│ 3.Verify │─▶│ 4.Polish │─▶│ 5.Ship   │─▶│ 6.Update │
│          │  │          │  │          │  │          │  │          │  │          │
│ Worktree │  │ Task     │  │ Full     │  │ Simplify │  │ PR       │  │ Spec     │
│ Branch   │  │ loop     │  │ test     │  │ Security │  │ ready    │  │ Issues   │
│ Draft PR │  │ Commits  │  │ suite    │  │ review   │  │          │  │ Cleanup  │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Phase 1: Setup

#### 1a. Read and Validate Spec

1. Read `docs/specs/<name>.md`
2. Verify tasks exist and have `**Status**: pending`
3. Check for unresolved Open Questions (`- [ ]` in Open Questions section) — if any, stop and ask user
4. Extract: task list with dependencies, file paths, reference files, test/lint commands from Implementation Notes

#### 1b. Create Branch + Worktree

**Branching**: `main` is always releasable. Each spec gets one branch.

Branch prefix by type:
- `feat/<ticket>-<name>` — new features (default)
- `fix/<ticket>-<name>` — bug fixes
- `chore/<ticket>-<name>` — non-behavioral changes (deps, docs, CI)

```bash
# Sync main
git checkout main && git pull origin main

# Derive branch name from spec metadata
# Ticket field determines <ticket>: GH-42, JIRA-123, etc.
# Default prefix is feat/, use fix/ or chore/ based on spec context
git checkout -b feat/<ticket>-<name>

# Create worktree — each branch gets its own worktree
git worktree add .worktrees/<name> feat/<ticket>-<name>
cd .worktrees/<name>
```

Announce: "Working in worktree on branch `feat/<ticket>-<name>`"

#### 1c. Install Dependencies

Run the project's install command from CLAUDE.md (e.g., `pnpm install`).

#### 1d. Commit Spec + Push + Draft PR

```bash
git add docs/specs/<name>.md
git commit -m "spec: add <name> implementation spec"
git push -u origin feat/<branch-name>

gh pr create --draft \
  --title "feat: <Feature Name>" \
  --body "<spec summary + task checklist>"
```

#### 1e. Update GitHub Issues

```bash
gh issue edit <epic> --add-assignee @me
gh issue comment <epic> --body "Build started. Draft PR: #<pr>"
```

---

### Phase 2: Execute

Dispatch one task at a time to `sdd-implementer` (see `sdd/agents/sdd-implementer.md`). Never dispatch implementers in parallel — that risks worktree conflicts. For tightly coupled tasks, use `--inline` mode instead (see below).

#### Task Dispatch Loop

For each task in dependency order:

**1. UPDATE ISSUE + SPEC** — assign the task issue to self if one exists; mark `**Status**: in-progress`

**2. RECORD BASE** — `BASE=$(git rev-parse HEAD)`. Never substitute `HEAD~1` later — it silently drops all but the last commit of a multi-commit task.

**3. DISPATCH** `sdd-implementer` with the task's full text and acceptance criteria, its reference files, interfaces produced by earlier tasks it consumes, and a report path (`.sdd/task-<N>-report.md`). Never paste the whole spec — the implementer reads `docs/specs/<name>.md` itself if it needs more.

**4. HANDLE STATUS** — `DONE`: continue to review. `DONE_WITH_CONCERNS`: address correctness concerns before reviewing, note observations and continue. `NEEDS_CONTEXT`: provide it, re-dispatch. `BLOCKED`: assess whether it needs more context, a tier bump, or is a genuine spec problem to escalate.

**5. REVIEW** — write the diff once, dispatch `sdd-reviewer` (see `sdd/agents/sdd-reviewer.md`):
```bash
mkdir -p .sdd && git diff $BASE...HEAD > .sdd/task-diff.md
```
Give it the diff path and the task's acceptance criteria. Check risk signals against `${CLAUDE_SKILL_DIR}/references/review-triggers.md` for whether a security- or migration-focused pass is also warranted.
(`${CLAUDE_SKILL_DIR}` is this skill's own directory, substituted automatically by Claude Code.
On a tool that doesn't, resolve it yourself as this skill's directory, using this file's known
location.)

**6. FIX LOOP** — run it if the review finds anything above trivial (see below).

**7. COMMIT + PUSH** — stage only this task's files, commit with the task's message, push.

**8. UPDATE SPEC + ISSUE** — mark done, increment Progress, check the top-level box and met acceptance criteria; comment the commit sha, files, and criteria met on the task issue if one exists.

**9. CONTINUE** to the next task, or **PAUSE** per below.

#### Fix Loop

Triggered by any review finding above trivial, or a spec-compliance gap. Cap: **3 rounds**. Never a 4th.

- **Rounds 1-2**: send the findings back to the same implementer dispatch — same context, same task. It fixes, re-runs its own tests, reports back.
- **Round 3**: dispatch a fresh `sdd-implementer` one tier up (override `model: opus`), with the open findings and a note that a prior attempt did not resolve them.
- **Every round**: re-review scoped to the fix only — `git diff $FIX_BASE...HEAD`, dispatched to `sdd-reviewer` against that range, never the whole task again.
- Never fix a finding in the orchestrator itself — that skips review and pollutes coordination context. Resume or re-dispatch the implementer.

#### Breaker

At the cap, resolve every remaining finding — never leave one open silently:

- **Reviewer wrong, or contestable** → park it: note the finding and why the code stands, in the task's spec section, then continue
- **Real, but nothing else depends on it** → park it the same way, as a deferred improvement
- **Real and load-bearing** — a later task depends on the broken behavior, or the spec itself is flawed → **stop the build**, comment the finding and fix history on the task's issue if one exists, and ask the user

#### Pause vs Continue

**Pause and ask** when:
- Task is unclear or ambiguous
- The breaker finds a load-bearing issue
- A dependency outside the spec is broken

**Fix and continue** for:
- Normal test failures during TDD, lint/typecheck issues
- Minor deviations from spec (note them, continue)
- Findings resolved within the fix loop's 3-round cap

---

### Phase 3: Verify

Run full validation suite. Evidence before claims.

```bash
<project test command>    # Full test suite
<project lint command>    # Lint
<project typecheck command>  # Typecheck (if applicable)
```

**Iron Law**: Do NOT claim the build is complete without running these commands fresh and reading the output. If anything fails, fix it, commit as `fix(<scope>): <description>`, push, and re-verify. Max 3 fix → re-verify cycles — if still failing after 3 attempts, pause and ask the user rather than brute-forcing.

---

### Phase 4: Polish

Run once over all changes, before PR goes to ready. Both passes dispatch `sdd-final-reviewer` (see `sdd/agents/sdd-final-reviewer.md`) — it's read-only, so it reports findings and the orchestrator applies them, not the other way around.

#### 4a. Code Simplification

Write `.sdd/branch-files.md` and dispatch with the simplifier prompt (see `${CLAUDE_SKILL_DIR}/references/agent-prompts.md`). Focus: reduce complexity, eliminate redundancy, improve naming, preserve all functionality.

If it reports changes: apply them, run tests, commit as `refactor(<scope>): simplify implementation`.

#### 4b. Security Review

Dispatch again with the security prompt, reusing `.sdd/branch-files.md`. Focus: OWASP Top 10 on changed files, HIGH and CRITICAL only.

If critical issues found: apply the fix, test, commit as `fix(<scope>): address security review findings`.

---

### Phase 5: Ship

#### 5a. Update PR Body

```bash
gh pr edit <pr> --body "<full PR body with:
- Summary (what + why)
- Spec link
- Changes by task
- Testing evidence
- Task completion checklist with issue links
- Post-deploy monitoring plan>"
```

#### 5b. Mark PR Ready

```bash
gh pr ready <pr>
```

---

### Phase 6: Update

#### 6a. Update Epic Issue

```bash
gh issue comment <epic> --body "All tasks complete. PR ready: #<pr>
Tasks: <N> completed. Tests: passing. Code simplified. Security reviewed."
```

#### 6b. Request Claude Review

```bash
gh pr comment <pr> --body "@claude please review this PR and comment prioritized findings back here."
```

#### 6c. Show Summary

Display the final build summary to the user:

```
## Build Complete

**Spec**: docs/specs/<name>.md
**Branch**: feat/<ticket>-<name>
**PR**: #<pr> (ready for review)
**Epic**: #<epic>

### Tasks Completed
1. #<issue> — <title>
2. #<issue> — <title>
...

### Quality
- Tests: passing
- Lint: clean
- Code simplified: yes
- Security reviewed: yes

### Links
- PR: <full PR URL>
- Spec: docs/specs/<name>.md
- Epic: <full epic URL>

Claude review requested on PR. Next step: address review findings or merge.
```

---

## --inline Mode

Phase 2 runs without dispatching `sdd-implementer` — the orchestrator implements each task directly, in the same loop shape (step 3 becomes "do it yourself" instead of "dispatch"). The fix loop and breaker still apply: rounds 1-2 are the orchestrator retrying its own work; round 3 still dispatches a fresh `sdd-implementer` one tier up, same as the default.

**When to use**: tasks are tightly coupled enough that a fresh subagent per task would spend more turns re-deriving shared context than it saves, or the spec has very few tasks.

---

## Guardrails

- **Spec is the source of truth** — implement what the spec says, not what seems better. If the spec is wrong, pause and suggest an update
- **One task, one commit** — each task produces exactly one commit (plus fix commits if tests fail)
- **Push after every commit** — backup and visibility
- **Update issues in real-time** — comments after every task, not batched at end
- **Evidence before claims** — run full test suite before claiming build is complete
- **Don't skip polish** — code simplification and security review run before every PR
- **Max 3 attempts** — if fix → re-verify fails 3 times, the approach is wrong. Stop, reassess, or ask the user. Never brute-force
- **Pause on blockers** — never guess when blocked. Comment on the issue and ask
- **Don't modify the spec without asking** — if the spec needs changes, pause and suggest. The user decides
- **Never fix a review finding in the orchestrator** — resume or re-dispatch the implementer; a self-fix skips review
- **No silent discards** — every fix-loop finding is fixed, parked with a reason, or blocks the build. Never dropped

## Additional Resources

### References
- **`references/review-triggers.md`** — When to trigger adaptive reviews (risk signals)
- **`references/agent-prompts.md`** — Prompt templates for all subagents

### Examples
- **`examples/build-session-log.md`** — Example output from a build session
