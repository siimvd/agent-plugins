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

Parse `$IDEA` for:
- `<name>` — matches a `docs/specs/<name>.md` spec file
- `--isolated-tasks` — dispatch a fresh subagent per task (clean context per task, same worktree)


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
gh issue comment <epic> --body "Build started. Draft PR: #<pr>"
```


### Phase 2: Execute

Work through tasks sequentially. Commit after each. Update issues in real-time.

#### Task Execution Loop

For each task in dependency order:

**1. UPDATE SPEC** — mark task in-progress
```
**Status**: pending → **Status**: in-progress
```

**2. READ CONTEXT**
- Read reference files listed in the task
## Inlined: references/agent-prompts.md
# Subagent Prompt Templates

Prompt templates for short-lived subagents spawned during the build phase.

## Investigation Subagent (Explore)

Spawn before implementing a task that touches unfamiliar code.

```
Research this part of the codebase to prepare for implementation.
DO NOT write any files. Read and search only.

**Task context**: [paste task description from spec]
**Files to investigate**: [paste file paths from task]

**Questions**:
1. What patterns does the existing code follow?
2. Are there hidden dependencies or complexity?
3. What's the best integration point?
4. Are there existing tests that show expected behavior?

Return:
- Key findings (with exact file paths and line numbers)
- Patterns to follow
- Gotchas or hidden complexity
- Recommended implementation approach
```

## Code Review Subagent

Spawn after implementing a task that triggers an adaptive review.

```
Review the changes for this task against the spec.

**Spec requirements for this task**:
[paste task section from spec including acceptance criteria]

**Changes to review**:
[paste output of: git diff HEAD~1]

Check for:
- Spec compliance — does the implementation match all acceptance criteria?
- Logic errors — incorrect conditions, off-by-one, null handling
- Missing error handling at system boundaries (user input, external APIs)
- Naming consistency with existing codebase patterns
- Test coverage gaps — are all acceptance criteria tested?

Report only issues with HIGH confidence. Skip style and formatting.
If no high-confidence issues found, say "No issues found."
```

## Code Simplifier Subagent

Spawn once at the end (Phase 4a), before PR goes to ready.

```
Review all files changed in this branch compared to main.
Simplify code while preserving ALL existing functionality and tests.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Focus on:
- Reducing nesting and cyclomatic complexity
- Eliminating redundant code or duplicate logic
- Improving variable and function naming for clarity
- Removing dead code or unused imports
- Following project conventions from CLAUDE.md
- Preferring explicit code over clever/compact solutions

DO NOT:
- Add new features or functionality
- Change public APIs or function signatures
- Create abstractions for one-time operations
- Add comments to code that is already clear
- Over-simplify (three similar lines > premature abstraction)

Make the changes directly. Run tests after to verify nothing broke.
```

## Security Review Subagent

Spawn once at the end (Phase 4b), before PR goes to ready.

```
Security review of all files changed in this branch.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Check for OWASP Top 10 vulnerabilities:
- Injection (SQL, XSS, command injection, path traversal)
- Broken authentication or authorization
- Sensitive data exposure (API responses, logs, error messages)
- Security misconfiguration (insecure defaults, missing headers)
- Hardcoded secrets, API keys, or credentials
- Missing input validation at system boundaries
- Insecure deserialization
- Missing rate limiting on new endpoints

Report only HIGH and CRITICAL severity issues.
For each issue, provide:
- File and line number
- Severity (HIGH or CRITICAL)
- Description of the vulnerability
- Recommended fix

If no high-severity issues found, say "No security issues found."
```

## Migration Analysis Subagent

Spawn when a task creates or modifies database migrations.

```
Analyze this database migration for safety.

**Migration file**: [path to migration]
**Migration SQL**:
[paste migration content]

Check for:
- Is this migration reversible? If not, is that acceptable?
- Will it lock tables on large datasets? For how long?
- Are there data loss risks (dropping columns, changing types)?
- Is there a safe rollback strategy?
- Are default values set for new non-nullable columns?
- Does it need to run in a transaction?
- Is there a dependency on application code changes?

Recommend:
- Any changes to make the migration safer
- Whether to split into multiple migrations
- A rollback plan
```

## Task Implementation Subagent (--isolated-tasks mode)

Spawn per task when `--isolated-tasks` is specified. Each gets a clean context.

```
Implement a single task from the spec below.

## Full Spec
[paste entire spec file content]

## Your Task
[paste the specific task section]

## Implementation Notes
[paste the Implementation Notes section from spec]

## Instructions
1. Read the reference files listed in your task
2. Write tests first (TDD) — cover all acceptance criteria
3. Implement the minimal code to pass tests
4. Follow patterns from reference files exactly
5. Run tests: [test command from Implementation Notes]
6. Run lint: [lint command from Implementation Notes]
7. Fix any failures
8. Stage only files related to this task (not git add .)
9. Commit with the message specified in the task
10. Terminate — do not continue to other tasks

DO NOT:
- Implement other tasks
- Modify files not listed in your task
- Change the spec file
- Skip tests
```

**3. IMPLEMENT**
- Write tests first (TDD)
- Implement minimal code to pass tests
- Follow patterns from reference files

**4. RUN TESTS**
- Run focused tests for changed files
- Fix any failures immediately
- Run lint/typecheck

**5. ADAPTIVE REVIEW** (if triggered)
## Inlined: references/review-triggers.md
# Adaptive Review Triggers

Reviews are NOT run after every task. They're triggered by risk signals detected in the task being implemented.

## Risk Signal Matrix

| Signal | Review Type | Why |
|--------|-------------|-----|
| Task touches auth, permissions, or access control | Security review | Auth bugs are critical vulnerabilities |
| Task creates or modifies database migration | Migration analysis | Schema changes are hard to reverse |
| Task modifies > 5 files | Code review | Large changes need a second look for consistency |
| Task touches payment, billing, or financial logic | Security + code review | Financial code is high-stakes |
| Task creates new API endpoint | Security review | New attack surface |
| Task modifies existing public API contract | Code review | Breaking changes affect consumers |
| Task handles user input or external data | Security review | Input validation is a common vulnerability |
| Task is marked "complex" or "risky" in spec | Code review | Spec author flagged it for a reason |
| Task modifies shared utilities or core libraries | Code review | Changes propagate widely |

## No Review Needed

Skip reviews for low-risk tasks:
- Adding navigation links or menu items
- Updating configuration files
- Adding static content or copy changes
- Simple wiring (connecting existing components)
- Test-only changes (adding tests without changing implementation)

## How to Detect

When starting a task, scan for risk signals by checking:

1. **File paths** — do they include `auth`, `permission`, `payment`, `billing`, `migration`?
2. **File count** — will this task modify more than 5 files?
3. **Task description** — does it mention security, access control, or data handling?
4. **Spec flags** — did the spec author mark this task as complex or risky?
5. **API changes** — does the Design section list API changes for this task?

If any signal matches, spawn the corresponding review subagent after implementation but before commit.

## Review Subagent Behavior

- Subagents are **short-lived**: spawn, review, report, terminate
- Report only **HIGH confidence** issues — skip style/formatting
- If issues found: fix them before committing
- If no issues: proceed to commit
- Review adds ~30 seconds per task — only worth it for risky changes
- If triggered, spawn a short-lived review subagent
- Fix any HIGH confidence issues found

**6. COMMIT + PUSH**
```bash
git add <specific files for this task>
git commit -m "<commit message from task spec>"
git push
```

**7. UPDATE SPEC** — mark task done
```
**Status**: in-progress → **Status**: done
**Progress**: N/M complete (increment)
Top checkbox: - [ ] Task N → - [x] Task N
Acceptance criteria: check off completed items
```

**8. UPDATE ISSUE** — mark done
```bash
gh issue comment <task-issue> --body "Completed in <sha>. Files: <list>. Criteria met: <list>"
```

**9. CONTINUE or PAUSE**
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


### Phase 3: Verify

Run full validation suite. Evidence before claims.

```bash
<project test command>    # Full test suite
<project lint command>    # Lint
<project typecheck command>  # Typecheck (if applicable)
```

**Iron Law**: Do NOT claim the build is complete without running these commands fresh and reading the output. If anything fails, fix it, commit as `fix(<scope>): <description>`, push, and re-verify.


### Phase 4: Polish

Run once over all changes, before PR goes to ready.

#### 4a. Code Simplification

## Inlined: references/agent-prompts.md
# Subagent Prompt Templates

Prompt templates for short-lived subagents spawned during the build phase.

## Investigation Subagent (Explore)

Spawn before implementing a task that touches unfamiliar code.

```
Research this part of the codebase to prepare for implementation.
DO NOT write any files. Read and search only.

**Task context**: [paste task description from spec]
**Files to investigate**: [paste file paths from task]

**Questions**:
1. What patterns does the existing code follow?
2. Are there hidden dependencies or complexity?
3. What's the best integration point?
4. Are there existing tests that show expected behavior?

Return:
- Key findings (with exact file paths and line numbers)
- Patterns to follow
- Gotchas or hidden complexity
- Recommended implementation approach
```

## Code Review Subagent

Spawn after implementing a task that triggers an adaptive review.

```
Review the changes for this task against the spec.

**Spec requirements for this task**:
[paste task section from spec including acceptance criteria]

**Changes to review**:
[paste output of: git diff HEAD~1]

Check for:
- Spec compliance — does the implementation match all acceptance criteria?
- Logic errors — incorrect conditions, off-by-one, null handling
- Missing error handling at system boundaries (user input, external APIs)
- Naming consistency with existing codebase patterns
- Test coverage gaps — are all acceptance criteria tested?

Report only issues with HIGH confidence. Skip style and formatting.
If no high-confidence issues found, say "No issues found."
```

## Code Simplifier Subagent

Spawn once at the end (Phase 4a), before PR goes to ready.

```
Review all files changed in this branch compared to main.
Simplify code while preserving ALL existing functionality and tests.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Focus on:
- Reducing nesting and cyclomatic complexity
- Eliminating redundant code or duplicate logic
- Improving variable and function naming for clarity
- Removing dead code or unused imports
- Following project conventions from CLAUDE.md
- Preferring explicit code over clever/compact solutions

DO NOT:
- Add new features or functionality
- Change public APIs or function signatures
- Create abstractions for one-time operations
- Add comments to code that is already clear
- Over-simplify (three similar lines > premature abstraction)

Make the changes directly. Run tests after to verify nothing broke.
```

## Security Review Subagent

Spawn once at the end (Phase 4b), before PR goes to ready.

```
Security review of all files changed in this branch.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Check for OWASP Top 10 vulnerabilities:
- Injection (SQL, XSS, command injection, path traversal)
- Broken authentication or authorization
- Sensitive data exposure (API responses, logs, error messages)
- Security misconfiguration (insecure defaults, missing headers)
- Hardcoded secrets, API keys, or credentials
- Missing input validation at system boundaries
- Insecure deserialization
- Missing rate limiting on new endpoints

Report only HIGH and CRITICAL severity issues.
For each issue, provide:
- File and line number
- Severity (HIGH or CRITICAL)
- Description of the vulnerability
- Recommended fix

If no high-severity issues found, say "No security issues found."
```

## Migration Analysis Subagent

Spawn when a task creates or modifies database migrations.

```
Analyze this database migration for safety.

**Migration file**: [path to migration]
**Migration SQL**:
[paste migration content]

Check for:
- Is this migration reversible? If not, is that acceptable?
- Will it lock tables on large datasets? For how long?
- Are there data loss risks (dropping columns, changing types)?
- Is there a safe rollback strategy?
- Are default values set for new non-nullable columns?
- Does it need to run in a transaction?
- Is there a dependency on application code changes?

Recommend:
- Any changes to make the migration safer
- Whether to split into multiple migrations
- A rollback plan
```

## Task Implementation Subagent (--isolated-tasks mode)

Spawn per task when `--isolated-tasks` is specified. Each gets a clean context.

```
Implement a single task from the spec below.

## Full Spec
[paste entire spec file content]

## Your Task
[paste the specific task section]

## Implementation Notes
[paste the Implementation Notes section from spec]

## Instructions
1. Read the reference files listed in your task
2. Write tests first (TDD) — cover all acceptance criteria
3. Implement the minimal code to pass tests
4. Follow patterns from reference files exactly
5. Run tests: [test command from Implementation Notes]
6. Run lint: [lint command from Implementation Notes]
7. Fix any failures
8. Stage only files related to this task (not git add .)
9. Commit with the message specified in the task
10. Terminate — do not continue to other tasks

DO NOT:
- Implement other tasks
- Modify files not listed in your task
- Change the spec file
- Skip tests
```

Focus: files changed in this branch vs main. Reduce complexity, eliminate redundancy, improve naming. Preserve all functionality.

If changes made: run tests, commit as `refactor(<scope>): simplify implementation`.

#### 4b. Security Review

## Inlined: references/agent-prompts.md
# Subagent Prompt Templates

Prompt templates for short-lived subagents spawned during the build phase.

## Investigation Subagent (Explore)

Spawn before implementing a task that touches unfamiliar code.

```
Research this part of the codebase to prepare for implementation.
DO NOT write any files. Read and search only.

**Task context**: [paste task description from spec]
**Files to investigate**: [paste file paths from task]

**Questions**:
1. What patterns does the existing code follow?
2. Are there hidden dependencies or complexity?
3. What's the best integration point?
4. Are there existing tests that show expected behavior?

Return:
- Key findings (with exact file paths and line numbers)
- Patterns to follow
- Gotchas or hidden complexity
- Recommended implementation approach
```

## Code Review Subagent

Spawn after implementing a task that triggers an adaptive review.

```
Review the changes for this task against the spec.

**Spec requirements for this task**:
[paste task section from spec including acceptance criteria]

**Changes to review**:
[paste output of: git diff HEAD~1]

Check for:
- Spec compliance — does the implementation match all acceptance criteria?
- Logic errors — incorrect conditions, off-by-one, null handling
- Missing error handling at system boundaries (user input, external APIs)
- Naming consistency with existing codebase patterns
- Test coverage gaps — are all acceptance criteria tested?

Report only issues with HIGH confidence. Skip style and formatting.
If no high-confidence issues found, say "No issues found."
```

## Code Simplifier Subagent

Spawn once at the end (Phase 4a), before PR goes to ready.

```
Review all files changed in this branch compared to main.
Simplify code while preserving ALL existing functionality and tests.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Focus on:
- Reducing nesting and cyclomatic complexity
- Eliminating redundant code or duplicate logic
- Improving variable and function naming for clarity
- Removing dead code or unused imports
- Following project conventions from CLAUDE.md
- Preferring explicit code over clever/compact solutions

DO NOT:
- Add new features or functionality
- Change public APIs or function signatures
- Create abstractions for one-time operations
- Add comments to code that is already clear
- Over-simplify (three similar lines > premature abstraction)

Make the changes directly. Run tests after to verify nothing broke.
```

## Security Review Subagent

Spawn once at the end (Phase 4b), before PR goes to ready.

```
Security review of all files changed in this branch.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Check for OWASP Top 10 vulnerabilities:
- Injection (SQL, XSS, command injection, path traversal)
- Broken authentication or authorization
- Sensitive data exposure (API responses, logs, error messages)
- Security misconfiguration (insecure defaults, missing headers)
- Hardcoded secrets, API keys, or credentials
- Missing input validation at system boundaries
- Insecure deserialization
- Missing rate limiting on new endpoints

Report only HIGH and CRITICAL severity issues.
For each issue, provide:
- File and line number
- Severity (HIGH or CRITICAL)
- Description of the vulnerability
- Recommended fix

If no high-severity issues found, say "No security issues found."
```

## Migration Analysis Subagent

Spawn when a task creates or modifies database migrations.

```
Analyze this database migration for safety.

**Migration file**: [path to migration]
**Migration SQL**:
[paste migration content]

Check for:
- Is this migration reversible? If not, is that acceptable?
- Will it lock tables on large datasets? For how long?
- Are there data loss risks (dropping columns, changing types)?
- Is there a safe rollback strategy?
- Are default values set for new non-nullable columns?
- Does it need to run in a transaction?
- Is there a dependency on application code changes?

Recommend:
- Any changes to make the migration safer
- Whether to split into multiple migrations
- A rollback plan
```

## Task Implementation Subagent (--isolated-tasks mode)

Spawn per task when `--isolated-tasks` is specified. Each gets a clean context.

```
Implement a single task from the spec below.

## Full Spec
[paste entire spec file content]

## Your Task
[paste the specific task section]

## Implementation Notes
[paste the Implementation Notes section from spec]

## Instructions
1. Read the reference files listed in your task
2. Write tests first (TDD) — cover all acceptance criteria
3. Implement the minimal code to pass tests
4. Follow patterns from reference files exactly
5. Run tests: [test command from Implementation Notes]
6. Run lint: [lint command from Implementation Notes]
7. Fix any failures
8. Stage only files related to this task (not git add .)
9. Commit with the message specified in the task
10. Terminate — do not continue to other tasks

DO NOT:
- Implement other tasks
- Modify files not listed in your task
- Change the spec file
- Skip tests
```

Focus: OWASP Top 10 on changed files. Report HIGH and CRITICAL only.

If critical issues found: fix, test, commit as `fix(<scope>): address security review findings`.


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


## Guardrails

- **Spec is the source of truth** — implement what the spec says, not what seems better. If the spec is wrong, pause and suggest an update
- **One task, one commit** — each task produces exactly one commit (plus fix commits if tests fail)
- **Push after every commit** — backup and visibility
- **Update issues in real-time** — comments after every task, not batched at end
- **Evidence before claims** — run full test suite before claiming build is complete
- **Don't skip polish** — code simplification and security review run before every PR
- **Pause on blockers** — never guess when blocked. Comment on the issue and ask
- **Don't modify the spec without asking** — if the spec needs changes, pause and suggest. The user decides

## Additional Resources

### References
- **`references/review-triggers.md`** — When to trigger adaptive reviews (risk signals)
- **`references/agent-prompts.md`** — Prompt templates for all subagents

### Examples
- **`examples/build-session-log.md`** — Example output from a build session
