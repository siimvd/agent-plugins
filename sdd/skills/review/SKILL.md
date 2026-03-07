---
name: review
description: >-
  This skill should be used when the user invokes "/sdd:review", says
  "review this implementation", "check against spec", "action review
  comments", "fix review findings", or wants to verify that implemented
  code matches the spec and address code review feedback. Handles both
  performing reviews and actioning existing review comments.
---

# Review — Spec Driven Development

Review implementation against the spec and project standards, or action existing review comments from humans and AI agents. Auto-detects mode: if unresolved review comments exist, action them. Otherwise, perform a comprehensive review.

This is the fourth step of the SDD workflow: **brainstorm -> plan -> build -> review -> finish**.

## Invocation

```
/sdd:review <name>
/sdd:review <name> --all
```

Parse `$ARGUMENTS` for:
- `<name>` — matches a `docs/specs/<name>.md` spec file
- `--all` — also fix P3 (low criticality) findings, not just P1+P2

---

## Mode Detection

Read the spec and identify the PR, then determine mode:

```bash
gh pr view <pr> --json reviews,comments
```

- **Reviews or comments with unresolved findings exist** → Action Mode
- **No reviews or all findings resolved** → Perform Mode

Announce which mode is active before proceeding.

---

## Perform Mode

Perform a comprehensive code review when no existing review needs actioning.

### Step 1: Gather Context

1. Read `docs/specs/<name>.md` — extract acceptance criteria, task list, key files, design decisions
2. Read `CLAUDE.md` — extract project conventions
3. Get the diff: `git diff main...HEAD`
4. Get changed files: `git diff --name-only main...HEAD`

### Step 2: Launch Review Agents

Spawn 4 parallel review subagents. Each receives the diff, changed file list, and its specific focus area.

#### Agent 1: Spec Compliance

```
Review the implementation against the spec acceptance criteria.

**Spec acceptance criteria:**
[paste all acceptance criteria from spec]

**Task list with per-task criteria:**
[paste each task's acceptance criteria]

**Diff to review:**
[paste diff]

Check for:
- Every acceptance criterion is implemented and testable
- No spec requirements were skipped or partially implemented
- Implementation matches the design decisions in the spec
- Edge cases mentioned in the spec are handled

For each finding, assign severity:
- P1 (critical): acceptance criterion not met, spec requirement missing
- P2 (high): partial implementation, design deviation without justification
- P3 (low): minor deviation, cosmetic mismatch

Report findings with file path, line number, severity, and which spec criterion is affected.
If all criteria are met, say "All spec criteria satisfied."
```

#### Agent 2: Bug Hunter

```
Review the diff for logic errors, bugs, and edge cases.

**Diff to review:**
[paste diff]

Focus on:
- Logic errors: incorrect conditions, off-by-one, wrong operator
- Null/undefined handling at boundaries
- Missing error handling for external calls (API, DB, filesystem)
- Race conditions or state management issues
- Incorrect type coercions or implicit conversions

DO NOT flag:
- Style or formatting issues (linter catches these)
- Missing tests (separate concern)
- Pre-existing issues in unchanged code
- Import order or naming preferences

For each finding, assign severity:
- P1: will cause runtime errors, data corruption, or crashes
- P2: will cause incorrect behavior under specific conditions
- P3: unlikely edge case, defensive improvement

Report only findings with HIGH confidence. Skip anything uncertain.
```

#### Agent 3: Security Review

```
Security review of changed files.

**Changed files:**
[paste file list]

**Diff to review:**
[paste diff]

Check for OWASP Top 10:
- Injection (SQL, XSS, command injection, path traversal)
- Broken authentication or authorization
- Sensitive data exposure (API responses, logs, error messages)
- Security misconfiguration (insecure defaults, missing headers)
- Hardcoded secrets, API keys, or credentials
- Missing input validation at system boundaries
- Insecure deserialization
- Missing rate limiting on new endpoints

For each finding, assign severity:
- P1: exploitable vulnerability, data exposure, auth bypass
- P2: defense-in-depth gap, missing validation, insecure default
- P3: hardening suggestion, best practice improvement

Report only P1 and P2 findings. Skip P3 unless pattern is widespread.
```

#### Agent 4: CLAUDE.md Compliance

```
Review the diff for compliance with project conventions.

**CLAUDE.md contents:**
[paste CLAUDE.md]

**Diff to review:**
[paste diff]

Check for:
- Code style violations specified in CLAUDE.md
- Architectural pattern violations (e.g., wrong layer for logic)
- Naming convention mismatches
- Import/export style deviations
- Missing Zod validation where required
- Direct DB access instead of ORM
- Any other explicit rules from CLAUDE.md

For each finding, assign severity:
- P1: architectural violation (wrong layer, raw SQL, missing validation)
- P2: convention violation (naming, imports, patterns)
- P3: minor style deviation

Report findings with the specific CLAUDE.md rule being violated.
If fully compliant, say "No CLAUDE.md violations found."
```

### Step 3: Synthesize Findings

Collect results from all 4 agents. Deduplicate overlapping findings. Organize by severity:

| Severity | Label | Meaning |
|----------|-------|---------|
| P1 | Critical | Blocks merge — spec gaps, bugs, security vulnerabilities, architectural violations |
| P2 | High | Should fix — edge cases, convention violations, defense-in-depth gaps |
| P3 | Low | Nice to have — hardening, cosmetic, minor improvements |

### Step 4: Post Review to PR

```bash
gh pr comment <pr> --body "<review comment>"
```

Format:

```markdown
### Code Review — SDD

**Spec**: docs/specs/<name>.md
**Reviewed**: <N> files changed

#### P1 — Critical (<count>)
1. **[Spec Compliance]** <description>
   <file link with line range>

2. **[Security]** <description>
   <file link with line range>

#### P2 — High (<count>)
1. **[Bug]** <description>
   <file link with line range>

#### P3 — Low (<count>)
1. **[Convention]** <description>
   <file link with line range>

---
Reviewed against spec `docs/specs/<name>.md` and project CLAUDE.md.
```

If no findings: post "No issues found. Spec compliance verified, security and conventions checked."

---

## Action Mode

Action existing review comments — fix P1 and P2 findings, skip P3 (unless `--all`).

### Step 1: Collect Review Findings

```bash
gh pr view <pr> --json reviews,comments
```

Parse all review sources:
- GitHub PR reviews (approved, changes_requested, commented)
- PR comments from humans, Claude, or other AI agents
- Inline review comments on specific lines

Extract each finding with:
- Source (who left the comment)
- Severity (P1/P2/P3) — infer from language if not explicitly labeled
- File and line reference (if inline comment)
- Description of the requested change

### Step 2: Classify and Plan

Organize findings by severity. Determine fix order:
1. P1 (critical) — fix first
2. P2 (high) — fix second
3. P3 (low) — fix only if `--all` flag is set

For each finding, before implementing:
- **Verify**: check if the suggestion is technically correct for this codebase
- **YAGNI check**: is the suggested change actually needed, or is it speculative?
- **Conflict check**: does it conflict with the spec or CLAUDE.md conventions?

If a finding is technically incorrect or conflicts with the spec:
- Do NOT implement it
- Reply in the PR comment thread explaining why, with technical reasoning
- Move to next finding

### Step 3: Implement Fixes

For each valid finding (P1, then P2, then P3 if `--all`):

1. Read the relevant file and understand context
2. Implement the fix
3. Run tests for changed files
4. If tests pass, continue to next finding
5. If tests fail, fix the regression before moving on

### Step 4: Commit and Push

```bash
git add <changed files>
git commit -m "fix(<scope>): address code review findings

Resolved:
- <P1 finding summary>
- <P2 finding summary>"
git push
```

### Step 5: Reply on PR

For each actioned finding, reply in the comment thread:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies \
  -f body="Fixed in <sha>. <brief description of what changed>."
```

For findings that were skipped (P3 without `--all`):

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies \
  -f body="Acknowledged. Deferred as low priority (P3)."
```

For findings that were pushed back on:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies \
  -f body="<technical reasoning for not implementing>."
```

### Step 6: Summary

```
## Review Action Complete

**PR**: #<pr>
**Findings processed**: <total>

### Resolved
- [P1] <finding> — fixed in <sha>
- [P2] <finding> — fixed in <sha>

### Deferred (P3)
- <finding> — acknowledged, low priority

### Pushed Back
- <finding> — <reason>

All P1 and P2 findings resolved. PR is ready for re-review or `/sdd:finish <name>`.
```

---

## Guardrails

- **Spec is the highest-value check** — spec compliance is the primary review concern in SDD, above general code quality
- **Verify before implementing** — never blindly apply review suggestions. Check against codebase reality, spec, and CLAUDE.md
- **Push back when wrong** — if a reviewer's suggestion conflicts with the spec or is technically incorrect, respond with reasoning instead of implementing
- **No performative agreement** — state the fix or the technical reason for pushback. Skip "great point" and "you're right"
- **P1+P2 by default** — action mode fixes critical and high findings automatically. P3 requires `--all` flag
- **Reply in threads** — respond to inline comments in their thread via API, not as top-level PR comments
- **Run tests after every fix** — never commit review fixes without verifying tests still pass
