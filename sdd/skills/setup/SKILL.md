---
name: setup
description: >-
  This skill should be used when the user invokes "/sdd:setup", says
  "set up SDD", "initialize SDD", "add SDD to my project", "bootstrap SDD",
  or wants to onboard a repository to the Spec Driven Development workflow.
  Creates AGENTS.md with best practices and SDD instructions, sets up
  directory structure and spec templates.
---

# Setup — Spec Driven Development

One-time onboarding command that bootstraps the SDD workflow in a repository. Creates AGENTS.md with best practices and SDD workflow instructions, sets up directory structure, and copies spec templates.

This is the zero step — run it once before starting the SDD workflow: **setup -> brainstorm -> plan -> build -> review -> finish**.

## Invocation

```
/sdd:setup
```

No arguments required. Operates on the current working directory.

---

## 4-Phase Process

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 1.Detect │─▶│ 2.Preview│─▶│ 3.Execute│─▶│ 4.Summary│
│          │  │          │  │          │  │          │
│ AGENTS.md│  │ Show plan│  │ Write    │  │ Next     │
│ dirs     │  │ confirm  │  │ files    │  │ steps    │
│ templates│  │          │  │ dirs     │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Phase 1: Detect

Check the current state of the repository:

1. **Check AGENTS.md** — does it exist at the repo root?
2. **Check for existing SDD section** — if AGENTS.md exists, search for `## SDD` or `## Spec Driven Development` to detect prior setup
3. **Check directory structure** — do `docs/specs/`, `docs/ideas/`, `docs/specs/.templates/` exist?
4. **Check templates** — do spec templates already exist in `docs/specs/.templates/`?

### Phase 2: Preview

Show the user exactly what will be created or modified:

```
## SDD Setup Plan

The following changes will be made:

- [ ] Create AGENTS.md with best practices (or: AGENTS.md exists, will append SDD section)
- [ ] Add SDD workflow section to AGENTS.md (or: SDD section already exists, skipping)
- [ ] Create docs/specs/ directory
- [ ] Create docs/ideas/ directory
- [ ] Create docs/specs/.templates/ with spec templates

Proceed? (y/n)
```

Adjust the checklist based on what Phase 1 detected — only show items that will actually change. If everything is already set up, say so and stop.

Ask the user for confirmation before writing anything.

### Phase 3: Execute

Based on detection results, perform the needed actions:

#### 3a. AGENTS.md

Three possible states:

**No AGENTS.md exists:**
1. Read the best-practices template from `${CLAUDE_SKILL_DIR}/agents-template.md`
2. Read the SDD section from `${CLAUDE_SKILL_DIR}/sdd-section.md`
3. Create `AGENTS.md` at the repo root with the template content followed by the SDD section

**AGENTS.md exists but no SDD section:**
1. Read the existing `AGENTS.md`
2. Read the SDD section from `${CLAUDE_SKILL_DIR}/sdd-section.md`
3. Append the SDD section to the end of `AGENTS.md`

**AGENTS.md exists with SDD section:**
- Skip — already set up

#### 3b. Directory Structure

Create directories if they don't exist:

```bash
mkdir -p docs/specs/.templates
mkdir -p docs/ideas
```

#### 3c. Spec Templates

Copy templates from the plugin into the repo if they don't already exist:

Source templates (in the plugin repo):
- `${CLAUDE_SKILL_DIR}/../../plan/spec-template.md` — the full spec template
- `${CLAUDE_SKILL_DIR}/../../plan/references/task-writing-guide.md` — task writing reference

Also check for existing templates in `docs/specs/.templates/`:
- `docs/specs/.templates/requirements.md`
- `docs/specs/.templates/design.md`
- `docs/specs/.templates/tasks.md`

If the individual section templates already exist, keep them. If they don't exist, copy the full spec template as `docs/specs/.templates/spec-template.md`.

### Phase 4: Summary

Display what was done and the next step:

```
## SDD Setup Complete

### Changes Made
- Created AGENTS.md with best practices and SDD workflow instructions
- Created docs/specs/ and docs/ideas/ directories
- Added spec templates to docs/specs/.templates/

### Directory Structure
docs/
  ideas/          <- brainstorm output (mini-PRDs)
  specs/          <- plan output (full specs)
    .templates/   <- spec templates
    archive/      <- finished specs (created by /sdd:finish)
  learnings/      <- compounded knowledge (created by /sdd:finish)

### Next Steps
1. Review and commit the changes
2. Start with: /sdd:brainstorm "your idea here"

### Workflow
  setup -> brainstorm -> plan -> build -> review -> finish
  (you are here)
```

---

## Guardrails

- **Never overwrite existing content** — append to AGENTS.md, don't replace it. Skip files that already exist
- **Idempotent** — safe to run multiple times. Detects existing state and skips what's already done
- **No auto-commit** — the user decides when to commit the setup changes
- **Ask before writing** — always show the preview and get confirmation
- **Respect existing templates** — if the repo already has spec templates, don't overwrite them
