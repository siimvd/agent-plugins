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
/sdd:build <name> --isolated-tasks
```

Parse `$ARGUMENTS` for:
- `<name>` — matches a `docs/specs/<name>.md` spec file
- `--isolated-tasks` — dispatch a fresh subagent per task (clean context per task, same worktree)

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

Work through tasks sequentially. Commit after each. Update issues in real-time.

#### Task Execution Loop

For each task in dependency order:

**1. UPDATE ISSUE** — assign to current user
```bash
gh issue edit <task-issue> --add-assignee @me
```

**2. UPDATE SPEC** — mark task in-progress
```
**Status**: pending → **Status**: in-progress
```

**3. READ CONTEXT**
- Read reference files listed in the task
- If task touches unfamiliar code, spawn a short-lived Explore subagent to investigate first (see `${CLAUDE_SKILL_DIR}/references/agent-prompts.md`)

**4. IMPLEMENT**
- Write tests first (TDD)
- Implement minimal code to pass tests
- Follow patterns from reference files

**5. RUN TESTS**
- Run focused tests for changed files
- Fix any failures immediately
- Run lint/typecheck
- **Max 3 attempts**: if a fix → re-verify cycle fails 3 times, stop and reassess. The approach is likely wrong — pause, investigate root cause, or ask the user

**6. ADAPTIVE REVIEW** (if triggered)
- Check risk signals against `${CLAUDE_SKILL_DIR}/references/review-triggers.md`
- If triggered, spawn a short-lived review subagent
- Fix any HIGH confidence issues found

**7. COMMIT + PUSH**
```bash
git add <specific files for this task>
git commit -m "<commit message from task spec>"
git push
```

**8. UPDATE SPEC** — mark task done
```
**Status**: in-progress → **Status**: done
**Progress**: N/M complete (increment)
Top checkbox: - [ ] Task N → - [x] Task N
Acceptance criteria: check off completed items
```

**9. UPDATE ISSUE** — mark done
```bash
gh issue comment <task-issue> --body "Completed in <sha>. Files: <list>. Criteria met: <list>"
```

**10. CONTINUE or PAUSE**
- Dependencies met → continue to next task
- Blocked → pause, comment on issue, ask user
- Design flaw discovered → pause, suggest spec update

#### Pause vs Continue

**Pause and ask** when:
- Task is unclear or ambiguous
- Implementation reveals a design flaw in the spec
- Tests fail in a way that suggests a spec issue
- A dependency outside the spec is broken

**Fix and continue** for:
- Normal test failures during TDD
- Lint/typecheck issues
- Minor deviations from spec (note them, continue)

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

Run once over all changes, before PR goes to ready.

#### 4a. Code Simplification

Spawn a code-simplifier subagent (see `${CLAUDE_SKILL_DIR}/references/agent-prompts.md` for prompt).

Focus: files changed in this branch vs main. Reduce complexity, eliminate redundancy, improve naming. Preserve all functionality.

If changes made: run tests, commit as `refactor(<scope>): simplify implementation`.

#### 4b. Security Review

Spawn a security review subagent (see `${CLAUDE_SKILL_DIR}/references/agent-prompts.md` for prompt).

Focus: OWASP Top 10 on changed files. Report HIGH and CRITICAL only.

If critical issues found: fix, test, commit as `fix(<scope>): address security review findings`.

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

## --isolated-tasks Mode

When specified, the execution model changes for Phase 2 only:

1. **Orchestrator** (main agent) manages the loop, reads spec, updates issues/spec
2. Each task is dispatched to a **fresh subagent** with clean context
3. All subagents work in the **same worktree, same branch, sequentially**
4. Each subagent commits before the next starts — zero conflict risk
5. The isolation is **conversation context** (clean window per task), not git state

Each task subagent gets injected:
- Full spec file content
- The specific task section to implement
- Reference files listed in the task
- Implementation Notes section (test/lint commands)
- Instructions: implement with TDD, run tests, commit, terminate

After each subagent completes:
- Orchestrator reviews the diff
- Runs adaptive review check
- Updates spec + issues
- Dispatches next subagent

**When to use**: Large specs (8+ tasks), tasks touching very different parts of the codebase, or when prior tasks' context could confuse implementation of later tasks.

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

## Additional Resources

### References
- **`references/review-triggers.md`** — When to trigger adaptive reviews (risk signals)
- **`references/agent-prompts.md`** — Prompt templates for all subagents

### Examples
- **`examples/build-session-log.md`** — Example output from a build session
