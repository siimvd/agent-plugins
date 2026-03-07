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
