---
name: finish
description: >-
  This skill should be used when the user invokes "/sdd:finish", says
  "finish this feature", "wrap up", "finalize", "close out", or wants
  to complete a development cycle by verifying review, archiving the
  spec, closing issues, compounding learnings, and cleaning up worktrees.
---

# Finish — Spec Driven Development

Finalize a completed feature: verify code review, merge PR, archive the spec, compound learnings, close issues, and clean up worktrees and branches. This is the last step — everything after this is deployed and documented.

This is the final step of the SDD workflow: **brainstorm -> plan -> build -> review -> finish**.

## Invocation

```
/sdd:finish <name>
```

Parse `$ARGUMENTS` for:
- `<name>` — matches a `docs/specs/<name>.md` spec file

---

## 5-Phase Process

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 1.Verify │─▶│ 2.Sync   │─▶│ 3.Compound│─▶│ 4.Close  │─▶│ 5.Cleanup│
│          │  │          │  │          │  │          │  │          │
│ PR state │  │ Spec     │  │ Knowledge│  │ Issues   │  │ Worktree │
│ Review   │  │ archive  │  │ capture  │  │ PR merge │  │ Branch   │
│ findings │  │ docs     │  │ learnings│  │          │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Phase 1: Verify Readiness

#### 1a. Read Spec and Identify PR

1. Read `docs/specs/<name>.md`
2. Extract: ticket/epic number, branch name, PR number
3. If PR number not in spec, find it: `gh pr list --head <branch> --json number`

#### 1b. Check PR State

```bash
gh pr view <pr> --json state,reviews,mergedAt,mergeable,reviewDecision
```

Determine state:
- **Merged** → proceed to Phase 2
- **Approved but not merged** → ask user: "PR #<pr> is approved but not merged. Merge now?"
  - If yes: `gh pr merge <pr> --squash --delete-branch`
  - If no: stop
- **Open, not approved** → stop: "PR #<pr> is not yet approved. Complete review first."

#### 1c. Check Code Reviews

```bash
# Get all reviews (human and bot) and PR comments
gh pr view <pr> --json reviews,comments
```

Check for completed code reviews from any source — human reviewers, Claude, or other AI agents. Reviews are detected from:
- **GitHub PR reviews**: approved/changes-requested/commented via `reviews` field
- **PR comments**: look for review-style comments from bots or agents (e.g., `@claude`, CI bots, other AI reviewers)

Evaluate review state:
- **At least one approval and no unresolved changes-requested** → proceed
- **No reviews at all** → warn: "No code reviews found on PR. Proceed anyway?" (non-blocking)
- **Unresolved P1/P2 findings in any review** → warn: "Found unresolved P1/P2 findings. Proceed anyway?" (non-blocking)
- **Changes requested but not re-approved** → warn: "Changes were requested but not re-approved. Proceed anyway?" (non-blocking)

---

### Phase 2: Sync Documentation

#### 2a. Update Spec Status

Edit `docs/specs/<name>.md`:
- Set top-level `**Status**:` to `completed`
- Ensure all task checkboxes are checked: `- [x]`
- Ensure all task statuses are `**Status**: done`
- Update `**Progress**:` to show all complete

#### 2b. Archive Spec

```bash
mkdir -p docs/specs/archive
git mv docs/specs/<name>.md docs/specs/archive/<name>.md
```

#### 2c. Commit Documentation Update

```bash
git add docs/specs/archive/<name>.md
git commit -m "docs: archive completed spec for <name>"
git push
```

---

### Phase 3: Compound Learnings

Capture knowledge from the build to make future work easier. This is a lighter version of full knowledge compounding — focused on patterns and gotchas discovered during implementation, not deep problem analysis.

#### 3a. Analyze the Build

Scan the following for learnings:
- Git log on the feature branch: `git log main..<branch> --oneline`
- Any `fix()` commits (indicate mistakes made and corrected)
- The spec's Implementation Notes and any deviations
- PR review findings (patterns that should be documented)

#### 3b. Identify Learnings

Look for:
- **Gotchas**: things that were harder than expected or broke unexpectedly
- **Patterns**: reusable approaches discovered during implementation
- **Mistakes**: errors made and how they were fixed (from `fix()` commits)
- **Missing docs**: things that should have been in CLAUDE.md but weren't

#### 3c. Write Learnings (if any found)

If non-trivial learnings exist, write to `docs/learnings/<category>/<name>.md`:

```bash
mkdir -p docs/learnings/<category>
```

Categories (auto-detected from learnings):
- `patterns/` — reusable implementation approaches
- `gotchas/` — surprising behaviors or hidden complexity
- `mistakes/` — errors and their prevention rules
- `integrations/` — third-party or cross-system lessons

Format:

```markdown
# <Learning Title>

**Date**: YYYY-MM-DD
**Spec**: docs/specs/archive/<name>.md
**Category**: <category>

## Context
[What was being built and why this came up]

## Learning
[The key insight or pattern]

## Prevention / Reuse
[How to apply this knowledge in future work]
```

#### 3d. Update CLAUDE.md (if applicable)

If a gotcha or mistake was found that represents a recurring risk, add it to the Mistakes Log in CLAUDE.md:

```markdown
## Mistakes Log (add new ones with date)
- YYYY-MM-DD: <what went wrong and the rule to prevent it>
```

#### 3e. Commit Learnings

```bash
git add docs/learnings/ CLAUDE.md
git commit -m "docs: compound learnings from <name>"
git push
```

Skip this phase entirely if no meaningful learnings were found — don't create empty files.

---

### Phase 4: Close Tracking

#### 4a. Close Task Issues

For each task sub-issue:

```bash
gh issue close <task-issue> --comment "Completed and merged in PR #<pr>."
```

#### 4b. Close Epic Issue

```bash
gh issue close <epic> --comment "Feature complete. All tasks done.
PR: #<pr> (merged)
Spec: docs/specs/archive/<name>.md
Learnings: docs/learnings/<category>/<name>.md (if created)

Tasks completed:
1. #<issue> — <title>
2. #<issue> — <title>
..."
```

---

### Phase 5: Cleanup

#### 5a. Remove Worktree

```bash
git worktree remove .worktrees/<name>
```

If worktree has uncommitted changes, warn and ask before forcing removal.

#### 5b. Return to Main

```bash
git checkout main
git pull origin main
```

This ensures the working tree is on an up-to-date main with the merged changes.

#### 5c. Delete Local Branch

The remote branch is deleted by PR merge (`--delete-branch`). Clean up local:

```bash
git branch -d <branch>
```

If branch is not fully merged (edge case), warn and ask before force-deleting.

#### 5d. Show Final Summary

```
## Feature Complete

**Spec**: docs/specs/archive/<name>.md
**PR**: #<pr> (merged)
**Epic**: #<epic> (closed)
**Branch**: <branch> (deleted)
**Worktree**: .worktrees/<name> (removed)

### Tasks Completed
1. #<issue> — <title> (closed)
2. #<issue> — <title> (closed)
...

### Learnings
- docs/learnings/<category>/<name>.md (or "No new learnings captured")
- CLAUDE.md updated: yes/no

### Cleanup
- Worktree removed
- Local branch deleted
- Remote branch deleted (by PR merge)

The SDD cycle for <name> is complete.
```

---

## Guardrails

- **Never merge without asking** — always confirm with user before `gh pr merge`
- **Non-blocking warnings** — unresolved review findings and missing reviews warn but don't hard-block
- **Don't fabricate learnings** — only write to `docs/learnings/` if something genuinely non-trivial was discovered. Empty compounding is worse than none
- **Preserve history** — archive specs, don't delete them. The archive is the project's memory
- **Commit on main** — documentation updates and learnings are committed to main after PR merge, not to the feature branch
