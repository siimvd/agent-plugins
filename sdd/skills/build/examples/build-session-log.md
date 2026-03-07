# Build Session Log — Example

This shows what a typical `/sdd:build notification-preferences` session looks like.

---

## Phase 1: Setup

```
Reading spec: docs/specs/notification-preferences.md
  6 tasks found, all pending
  No unresolved open questions
  Ticket: GH-42

Creating branch: feat/GH-42-notification-preferences
Creating worktree: .worktrees/notification-preferences
Installing dependencies: pnpm install

Committing spec and pushing...
Opening draft PR...

Working in worktree on branch feat/GH-42-notification-preferences
Draft PR: #87
Epic GH-42 marked in-progress
```

## Phase 2: Execute

```
## Task 1/6: Types and Schema
   Issue GH-43 → in-progress
   Reading reference: src/lib/db/schema/user-settings.ts
   Writing tests... implementing... running tests...
   Tests: 5 passed
   Lint: clean
   Committed: feat(notifications): add types and database schema for preferences
   Pushed to origin
   Spec updated: 1/6 complete
   Issue GH-43 → done (commented with files + criteria)

## Task 2/6: Preferences Service
   Issue GH-44 → in-progress
   Reading reference: src/lib/services/user-settings.ts
   Writing tests... implementing... running tests...
   Tests: 8 passed
   Lint: clean
   Committed: feat(notifications): add preferences service with defaults
   Pushed to origin
   Spec updated: 2/6 complete
   Issue GH-44 → done

## Task 3/6: API Routes
   Issue GH-45 → in-progress
   Reading reference: src/app/api/settings/route.ts
   Writing tests... implementing... running tests...
   Tests: 6 passed
   Lint: clean
   ⚡ Adaptive review triggered: new API endpoint
   Spawning security review subagent...
   Security review: No issues found.
   Committed: feat(notifications): add preferences API routes
   Pushed to origin
   Spec updated: 3/6 complete
   Issue GH-45 → done

## Task 4/6: Settings Page UI
   Issue GH-46 → in-progress
   Reading reference: src/app/settings/profile/page.tsx
   Writing tests... implementing... running tests...
   Tests: 4 passed
   Lint: clean
   Committed: feat(notifications): add notification preferences settings page
   Pushed to origin
   Spec updated: 4/6 complete
   Issue GH-46 → done

## Task 5/6: Navigation Integration
   Issue GH-47 → in-progress
   Modifying: src/app/settings/layout.tsx
   Writing tests... implementing... running tests...
   Tests: 2 passed
   Lint: clean
   Committed: feat(notifications): add notifications to settings navigation
   Pushed to origin
   Spec updated: 5/6 complete
   Issue GH-47 → done

## Task 6/6: Integration Test
   Issue GH-48 → in-progress
   Reading reference: tests/integration/user-settings.test.ts
   Writing integration tests... running...
   Tests: 3 passed
   Lint: clean
   Committed: test(notifications): add integration tests for preferences flow
   Pushed to origin
   Spec updated: 6/6 complete
   Issue GH-48 → done
```

## Phase 3: Verify

```
Running full test suite: pnpm vitest run
  42 tests passed, 0 failed

Running lint: pnpm lint
  No issues

Running typecheck: pnpm typecheck
  No errors

All verification passed.
```

## Phase 4: Polish

```
Spawning code simplifier...
  Reviewed 8 changed files
  Simplified: src/lib/services/notification-preferences.ts
    - Extracted repeated validation into helper
    - Simplified default seeding logic
  Running tests after simplification: 42 passed
  Committed: refactor(notifications): simplify implementation

Spawning security reviewer...
  Reviewed 8 changed files
  No security issues found.
```

## Phase 5: Ship

```
Updating PR #87 body with completion details...
Marking PR #87 as ready for review...
PR #87 is now ready for review.
```

## Phase 6: Update

```
Commented on epic GH-42: all tasks complete, PR ready

Requesting Claude review on PR #87...
Commented: "@claude please review this PR and comment prioritized findings back here."

## Build Complete

**Spec**: docs/specs/notification-preferences.md
**Branch**: feat/GH-42-notification-preferences
**PR**: #87 (ready for review)
**Epic**: #42

### Tasks Completed
1. #43 — Types and Schema
2. #44 — Preferences Service
3. #45 — API Routes
4. #46 — Settings Page UI
5. #47 — Navigation Integration
6. #48 — Integration Test

### Quality
- Tests: 42 passing
- Lint: clean
- Code simplified: yes
- Security reviewed: yes

### Links
- PR: https://github.com/owner/repo/pull/87
- Spec: docs/specs/notification-preferences.md
- Epic: https://github.com/owner/repo/issues/42

Claude review requested on PR. Next step: address review findings or merge.
```
