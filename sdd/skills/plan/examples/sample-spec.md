# Notification Preferences

**Date**: 2026-03-07
**Status**: approved
**Author**: Siim
**Spec**: docs/specs/notification-preferences.md
**Ticket**: GH-42
**Idea**: docs/ideas/notification-preferences.md

---

## Requirements

### Problem Statement

Users receive all notifications by default and have no way to control which ones they see. This leads to notification fatigue — important updates get buried in noise, and power users either mute everything or disengage.

### Target Users

Active daily users who interact with the product frequently. Currently they either mute all notifications (missing critical ones) or tolerate the noise (reducing engagement over time).

### Functional Requirements

1. Users can view their notification preferences organized by category
2. Users can toggle notifications on/off per category
3. Users can select delivery channel (in-app, email, push) per category
4. New users get sensible defaults (critical: all channels, social: in-app only)
5. Preferences persist across sessions and devices

### Non-Functional Requirements

- Performance: preferences API responds within 200ms
- Security: users can only read/write their own preferences

### Acceptance Criteria

- [ ] Preferences page loads with all categories and current settings
- [ ] Toggling a category on/off takes effect immediately
- [ ] Channel selection persists after page reload
- [ ] New user sees default preferences without manual setup
- [ ] API validates category exists before updating
- [ ] Unauthorized access returns 401

### Scope

**In scope:**
- Category-based notification preferences UI
- Per-category channel selection (in-app, email, push)
- Default preference values for new users
- Preferences API (GET + PUT)
- Database schema for preferences

**Out of scope:**
- Per-item notification rules (e.g., "notify only for this project")
- Notification scheduling (quiet hours, digest mode)
- Notification history/archive
- Admin-level notification policies

### Open Questions

- [x] How many categories at launch? — Start with 4: critical, updates, social, marketing
- [ ] Should we add a "mute all" global toggle? — Defer to v2

---

## Design

### Approach

Add a preferences service backed by a new `notification_preferences` table. Expose via REST API (GET/PUT). Build a settings page component that follows the existing settings UI pattern in `src/app/settings/`. Use Drizzle ORM for data access and Zod for input validation.

### Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Settings    │────▶│  Preferences     │────▶│  notification_   │
│  Page UI     │     │  API Route       │     │  preferences     │
│  (React)     │     │  (GET/PUT)       │     │  (Drizzle)       │
└──────────────┘     └──────────────────┘     └──────────────────┘
                            │
                     ┌──────┴──────┐
                     │ Preferences │
                     │ Service     │
                     │ (validate,  │
                     │  defaults)  │
                     └─────────────┘
```

### Key Files

| File | Action | Purpose |
|------|--------|---------|
| `src/lib/db/schema/notification-preferences.ts` | Create | Drizzle schema for preferences table |
| `src/lib/services/notification-preferences.ts` | Create | Business logic: get, update, defaults |
| `src/app/api/preferences/route.ts` | Create | REST API handlers |
| `src/app/settings/notifications/page.tsx` | Create | Settings page UI |
| `src/lib/types/notifications.ts` | Create | Shared types + Zod schemas |
| `drizzle/migrations/0005_notification_preferences.sql` | Create | DB migration |

### Data Model

```sql
CREATE TABLE notification_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  category TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT true,
  channels TEXT[] NOT NULL DEFAULT '{in_app}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, category)
);
```

### API Changes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/preferences` | Returns all preferences for authenticated user |
| PUT | `/api/preferences` | Updates preferences for a category |

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | Postgres table, not JSON column | Queryable, indexable, follows existing patterns |
| Defaults | Seeded on first access, not on user creation | Simpler, no migration for existing users |
| Categories | Hardcoded enum, not DB-driven | Simpler, categories change rarely |
| Channels | Array column | Flexible, supports multiple channels per category |

### Patterns to Follow

- `src/app/settings/profile/page.tsx` — follow this pattern for the settings page layout
- `src/app/api/settings/route.ts` — follow this pattern for the API route structure
- `src/lib/services/user-settings.ts` — follow this pattern for the service layer

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Migration on large users table | Slow deploy | Separate table, no FK on users |
| Default seeding on every GET | Performance | Cache after first seed, check before insert |

### Alternatives Considered

**JSON column on users table**: Simpler schema but not queryable, harder to add new categories, doesn't follow existing pattern of separate tables for concerns.

**Rule-based engine**: Powerful but complex — users define conditions like "notify if priority > high." High complexity for an MVP, deferred to future iteration.

---

## Tasks

**Progress**: 0/6 complete

- [ ] Task 1: Types and Schema
- [ ] Task 2: Preferences Service
- [ ] Task 3: API Routes
- [ ] Task 4: Settings Page UI
- [ ] Task 5: Navigation Integration
- [ ] Task 6: Integration Test

Tasks are ordered by dependency. Each task is a logical unit that results in one commit.

---

### Task 1: Types and Schema
**Status**: pending

**Files:**
- Create: `src/lib/types/notifications.ts`
- Create: `src/lib/db/schema/notification-preferences.ts`
- Create: `drizzle/migrations/0005_notification_preferences.sql`
- Test: `tests/lib/types/notifications.test.ts`
- Reference: `src/lib/db/schema/user-settings.ts` (follow this pattern)

**What to build:**
- Zod schemas for notification categories (critical, updates, social, marketing) and channel types (in_app, email, push)
- Drizzle table definition for `notification_preferences`
- Database migration

**Acceptance criteria:**
- [ ] Zod schemas validate correct categories and channels
- [ ] Zod schemas reject invalid input
- [ ] Drizzle schema matches the SQL migration
- [ ] Migration runs without errors on dev database
- [ ] Tests cover: valid input, invalid category, invalid channel

**Commit**: `feat(notifications): add types and database schema for preferences`

---

### Task 2: Preferences Service
**Status**: pending
**Depends on**: Task 1

**Files:**
- Create: `src/lib/services/notification-preferences.ts`
- Test: `tests/lib/services/notification-preferences.test.ts`
- Reference: `src/lib/services/user-settings.ts` (follow this pattern)

**What to build:**
- `getPreferences(userId)` — returns all preferences, seeds defaults if none exist
- `updatePreference(userId, category, update)` — validates and updates a single category
- Default preferences: critical (all channels), updates (in_app + email), social (in_app), marketing (disabled)

**Acceptance criteria:**
- [ ] First call for new user seeds defaults and returns them
- [ ] Subsequent calls return existing preferences without re-seeding
- [ ] Update validates category exists and channels are valid
- [ ] Update rejects invalid input with descriptive error
- [ ] Tests cover: first access, repeat access, valid update, invalid category, invalid channel

**Commit**: `feat(notifications): add preferences service with defaults`

---

### Task 3: API Routes
**Status**: pending
**Depends on**: Task 2

**Files:**
- Create: `src/app/api/preferences/route.ts`
- Test: `tests/api/preferences.test.ts`
- Reference: `src/app/api/settings/route.ts` (follow this pattern)

**What to build:**
- GET handler: authenticate user, call service, return preferences
- PUT handler: authenticate user, validate body with Zod, call service, return updated preference
- Error handling: 401 for unauthenticated, 400 for invalid input, 404 for unknown category

**Acceptance criteria:**
- [ ] GET returns 200 with preferences array
- [ ] PUT returns 200 with updated preference
- [ ] Unauthenticated request returns 401
- [ ] Invalid body returns 400 with validation errors
- [ ] Tests cover: happy path GET, happy path PUT, auth failure, validation failure

**Commit**: `feat(notifications): add preferences API routes`

---

### Task 4: Settings Page UI
**Status**: pending
**Depends on**: Task 3

**Files:**
- Create: `src/app/settings/notifications/page.tsx`
- Test: `tests/app/settings/notifications/page.test.tsx`
- Reference: `src/app/settings/profile/page.tsx` (follow this layout pattern)

**What to build:**
- Page showing all notification categories with toggles and channel selectors
- Fetches preferences on load via GET /api/preferences
- Updates on toggle/channel change via PUT /api/preferences
- Loading and error states

**Acceptance criteria:**
- [ ] Page renders all 4 categories with current settings
- [ ] Toggle updates preference immediately (optimistic UI)
- [ ] Channel selector allows multi-select (in_app, email, push)
- [ ] Loading state shown while fetching
- [ ] Error state shown if API fails
- [ ] Tests cover: render with data, toggle interaction, error state

**Commit**: `feat(notifications): add notification preferences settings page`

---

### Task 5: Navigation Integration
**Status**: pending
**Depends on**: Task 4

**Files:**
- Modify: `src/app/settings/layout.tsx`
- Reference: existing nav items in `src/app/settings/layout.tsx`

**What to build:**
- Add "Notifications" link to settings sidebar navigation
- Position after existing settings items

**Acceptance criteria:**
- [ ] "Notifications" link appears in settings sidebar
- [ ] Link navigates to /settings/notifications
- [ ] Active state shows when on notifications page

**Commit**: `feat(notifications): add notifications to settings navigation`

---

### Task 6: Integration Test
**Status**: pending
**Depends on**: Task 5

**Files:**
- Create: `tests/integration/notification-preferences.test.ts`
- Reference: `tests/integration/user-settings.test.ts` (follow this pattern)

**What to build:**
- End-to-end test: create user, verify default preferences, update a preference, verify persistence
- Test the full stack: API -> Service -> Database

**Acceptance criteria:**
- [ ] New user gets default preferences on first API call
- [ ] Updated preference persists across API calls
- [ ] Full round-trip works: seed -> read -> update -> read

**Commit**: `test(notifications): add integration tests for preferences flow`

---

## Implementation Notes

- **TDD**: Write tests first for each task, then implement
- **Pattern**: Follow `src/app/settings/profile/page.tsx` for UI, `src/lib/services/user-settings.ts` for service layer
- **Testing command**: `pnpm vitest run`
- **Lint command**: `pnpm lint`
- **DB push**: `pnpm db:push`

---
*Generated by `/sdd:plan` — start a new session and run `/sdd:build notification-preferences` to implement*
