# Resilient Issue Tracking

**Date**: 2026-03-09
**Status**: done
**Author**: Claude
**Spec**: docs/specs/resilient-issue-tracking.md
**Ticket**: GH-1
**Idea**: N/A

---

## Requirements

### Problem Statement

The SDD workflow uses GitHub labels (`status:ready`, `status:in-progress`, `status:done`, `epic`, `task`) for issue tracking, but these labels rarely exist on target repos. This causes `gh issue edit --add-label` and `gh issue create --label` to fail with errors like `'status:done' not found`. Labels add complexity for little value — issue comments already provide full tracking. Additionally, GitHub Issues are never assigned to the user running the build, making it unclear who is working on what.

### Target Users

Anyone using the SDD workflow.

### Functional Requirements

1. Remove all `--label` and `--add-label`/`--remove-label` flags from `gh issue` commands across the SDD workflow
2. When `/sdd:build` starts (Phase 1e), the epic issue should be assigned to the current user
3. When `/sdd:build` starts working on a task, the corresponding GitHub Issue should be assigned to the current user (`@me`)

### Non-Functional Requirements

- Simplicity: fewer flags = fewer failure modes

### Acceptance Criteria

- [ ] No `--label`, `--add-label`, or `--remove-label` flags remain in any SDD skill or command file
- [ ] Epic issue is assigned to `@me` when build starts
- [ ] Task issues are assigned to `@me` when each task starts
- [ ] Comments on issues are unaffected (still posted as before)

### Scope

**In scope:**
- Removing all label flags from `sdd/skills/build/SKILL.md`
- Removing all label flags from `sdd/skills/plan/SKILL.md`
- Removing all label flags from `.opencode/commands/sdd-build.md`
- Removing all label flags from `.opencode/commands/sdd-plan.md`
- Adding `--add-assignee @me` to build issue updates
- Removing the "Update issues in real-time — status labels and comments" guardrail reference to labels

**Out of scope:**
- Adding assignment to `/sdd:plan` or `/sdd:finish`
- Changes to `/sdd:review` (the "labeled" reference there is about PR comment severity, not GitHub labels)

### Open Questions

None.

---

## Design

### Approach

1. **Remove labels**: Strip all `--label`, `--add-label`, and `--remove-label` flags from `gh issue create` and `gh issue edit` commands. Issue comments already track status transitions.

2. **Add assignment**: Add `--add-assignee @me` to `gh issue edit` commands when marking issues as in-progress during build.

### Key Files

| File | Action | Purpose |
|------|--------|---------|
| `sdd/skills/build/SKILL.md` | Modify | Remove label flags + add assignment |
| `sdd/skills/plan/SKILL.md` | Modify | Remove label flags from issue creation |
| `.opencode/commands/sdd-build.md` | Modify | Mirror build changes |
| `.opencode/commands/sdd-plan.md` | Modify | Mirror plan changes |

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Labels | Remove entirely | Comments already track status; labels cause errors on repos without them |
| When to assign | Only during build (in-progress transitions) | User requested build-only |
| Assignment target | `@me` | Works universally via gh CLI |

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `@me` not resolved in some gh CLI versions | Assignment silently fails | Non-blocking — comments still track |

### Alternatives Considered

- **Make labels resilient (best-effort)**: Rejected — adds complexity for marginal value. Simpler to remove entirely.

---

## Tasks

**Progress**: 2/2 complete

- [x] Task 1: Remove all label operations
- [x] Task 2: Add issue assignment during build

Tasks are ordered by dependency. Each task is a logical unit that results in one commit.

---

### Task 1: Remove All Label Operations (GH-2)
**Status**: done

**Files:**
- Modify: `sdd/skills/build/SKILL.md`
- Modify: `sdd/skills/plan/SKILL.md`
- Modify: `.opencode/commands/sdd-build.md`
- Modify: `.opencode/commands/sdd-plan.md`
- Reference: `sdd/skills/build/SKILL.md` (current label usage at lines ~100, ~116, ~161, ~323)

**What to build:**

In `sdd/skills/build/SKILL.md`:
- Phase 1e (~line 100): Remove `--add-label "status:in-progress" --remove-label "status:ready"` from the epic `gh issue edit` command
- Phase 2 step 1 (~line 116): Remove `--add-label "status:in-progress" --remove-label "status:ready"` from the task `gh issue edit` command
- Phase 2 step 9 (~line 161): Remove the entire `gh issue edit <task-issue> --add-label "status:done" --remove-label "status:in-progress"` line (the comment on the next line already tracks completion)
- Guardrails (~line 323): Update "status labels and comments" to just "comments"

In `sdd/skills/plan/SKILL.md`:
- Phase 4 (~line 169): Remove `--label "epic,status:ready"` from epic `gh issue create`
- Phase 4 (~line 175): Remove `--label "task,status:ready"` from task `gh issue create`

Mirror the same removals in:
- `.opencode/commands/sdd-build.md` (~lines 100, 115, 376, 874)
- `.opencode/commands/sdd-plan.md` (~lines 424, 430)

**Acceptance criteria:**
- [ ] No `--label`, `--add-label`, or `--remove-label` flags in `sdd/skills/build/SKILL.md`
- [ ] No `--label` flags in `sdd/skills/plan/SKILL.md`
- [ ] No label flags in `.opencode/commands/sdd-build.md`
- [ ] No label flags in `.opencode/commands/sdd-plan.md`
- [ ] `gh issue edit` commands that only had label flags are removed entirely
- [ ] `gh issue comment` commands are untouched

**Commit**: `fix(sdd): remove label operations to avoid errors on repos without labels`

---

### Task 2: Add Issue Assignment During Build (GH-3)
**Status**: done
**Depends on**: Task 1

**Files:**
- Modify: `sdd/skills/build/SKILL.md`
- Modify: `.opencode/commands/sdd-build.md`
- Reference: `sdd/skills/build/SKILL.md` (existing `gh issue edit`/`gh issue comment` patterns in Phase 1e and Phase 2)

**What to build:**

In `sdd/skills/build/SKILL.md`:
- Phase 1e: Add `gh issue edit <epic> --add-assignee @me` (before or combined with the comment command)
- Phase 2 step 1: Add `gh issue edit <task-issue> --add-assignee @me` when starting a task

Mirror in `.opencode/commands/sdd-build.md` at the same two locations.

**Acceptance criteria:**
- [ ] Epic `gh issue edit` in Phase 1e includes `--add-assignee @me`
- [ ] Task `gh issue edit` in Phase 2 step 1 includes `--add-assignee @me`
- [ ] Same changes applied to `.opencode/commands/sdd-build.md`
- [ ] Assignment only happens when starting work, not at completion

**Commit**: `feat(sdd): assign issues to current user during build`

---

## Implementation Notes

- **No TDD**: These are prompt/instruction files (Markdown), not executable code
- **Pattern**: Follow existing `gh issue` command patterns in the SKILL.md files
- **Testing**: Manual verification by running `/sdd:build` on a repo without labels

---
*Generated by `/sdd:plan` — start a new session and run `/sdd:build resilient-issue-tracking` to implement*
