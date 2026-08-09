---
name: plan
description: >-
  This skill should be used when the user invokes "/sdd:plan", says
  "create a spec", "plan this feature", "write a spec for", "plan the
  implementation", or wants to convert a mini-PRD or idea into a full
  implementation spec with requirements, design, and tasks. Produces
  a spec in docs/specs/.
---

# Plan — Spec Driven Development

Convert an idea into a precise, implementable spec that any AI agent can pick up and execute without asking questions. This is the second step of the SDD workflow: **brainstorm -> plan -> build -> review -> finish**.

**The goal**: produce a single spec file with requirements, technical design, and ordered tasks — grounded in the actual codebase, not theory.

## Invocation

```
/sdd:plan <name>
/sdd:plan "description of bug or change"
/sdd:plan <name> --fast
/sdd:plan <name> --ticket JIRA-123
```

Parse `$ARGUMENTS` for:
- `<name>` — matches a `docs/ideas/<name>.md` mini-PRD from brainstorm
- A quoted description — for small bugs/changes that skip brainstorm
- `--fast` — compress interaction, skip deep research
- `--ticket <REF>` — link to external issue tracker (Jira, Linear, etc.)

---

## 4-Phase Process

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. Ingest   │────▶│ 2. Research  │────▶│  3. Author   │────▶│  4. Publish  │
│              │     │              │     │              │     │              │
│ Read input   │     │ Explore code │     │ Write spec   │     │ Create issues│
│ Clarify gaps │     │ Map patterns │     │ Confirm with │     │ Show summary │
│              │     │ Surface risk │     │ user         │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Phase 1: Ingest

**Goal**: Understand what to plan and fill gaps.

**From brainstorm (mini-PRD exists)**:
1. Read `docs/ideas/<name>.md`
2. Map mini-PRD fields to spec sections:

   | Mini-PRD Field | Spec Section |
   |----------------|--------------|
   | Problem | Requirements > Problem Statement |
   | Who Benefits | Requirements > Target Users |
   | Success Criteria | Requirements > Acceptance Criteria |
   | Proposed Solution | Design > Approach |
   | Scope in/out | Requirements > Scope |
   | Open Questions | Requirements > Open Questions |
   | Approaches Considered | Design > Alternatives Considered |

3. Check for unresolved Open Questions that block planning. If any, ask 1-2 targeted questions now.

**From scratch (no mini-PRD)**:
1. Parse the description
2. Ask 2-3 essential questions: What's the problem? What does success look like? What's out of scope?
3. In `--fast` mode: make reasonable assumptions, present them, ask for confirmation

### Phase 2: Research

**Goal**: Ground the plan in the actual codebase. Understand existing patterns, find integration points, surface hidden complexity.

**When to research**:
- Default: always research
- `--fast`: skip parallel agents, do a single quick scan. Still research if the change touches unfamiliar parts of the codebase

**Learnings retrieval** (before dispatching research threads — no subagent needed, this is cheap):

1. If `docs/learnings/` doesn't exist, skip silently — no error, no output
2. Otherwise glob `docs/learnings/**/*.md` and read only each file's frontmatter (category, tags, files)
3. Open only the learnings whose tags or files overlap this change, capped at 5
4. State which learnings informed the plan, or "No relevant learnings found" if none matched — feed anything used into the spec's Risks or Patterns to Follow sections

**Research threads** (dispatch as parallel Explore subagents):

| Thread | What It Does |
|--------|-------------|
| **Architecture scan** | Map relevant files, modules, data models. Find the "seam" where this feature fits |
| **Pattern matching** | Find similar features already implemented. These become the reference for how to build |
| **Risk surface** | Identify dependencies, migration needs, breaking changes, performance concerns |

**Agent prompt template**:
```
Research this codebase to inform a technical spec.
DO NOT write any files. Read and search only.

**Research question**: [specific question]
**Focus area**: [relevant directories/files]

Return:
1. Key files found (with paths)
2. Patterns identified
3. Risks or complexity surfaced
4. Recommended approach based on what exists
```

After research completes, present key findings to user: "Here's what I found in the codebase. Any surprises?"

**In --fast mode**: Single Explore agent with all three questions combined. Present findings inline without a separate confirmation step.

### Phase 3: Author

**Goal**: Write the spec file. Confirm key decisions with the user.

Write a single `docs/specs/<name>.md` using the template at `${CLAUDE_SKILL_DIR}/spec-template.md`.

Derive `<name>` from the idea or description: lowercase, hyphenated, 2-4 words.

Write sections in order:
1. **Requirements** — write first, confirm with user: "Does this capture the full scope?"
2. **Design** — grounded in research, confirm key decisions: "I'm recommending [approach] because [reason]. Sound good?"
3. **Tasks** — flows from requirements + design

**In --fast mode**: Write the entire spec, present it for approval in one pass.

#### Task Writing Rules

- Each task = one logical unit = one commit boundary
- Include exact file paths (create/modify/test/reference)
- Include acceptance criteria that can be checked mechanically
- Include the reference file to follow (from research)
- Order by dependency — task N should only depend on tasks < N
- 5-12 tasks for a typical feature. If more than 12, the feature should be split into separate specs
- TDD guidance is built into each task, not separate "write test" / "run test" steps

See `${CLAUDE_SKILL_DIR}/references/task-writing-guide.md` for detailed guidance and examples.

#### Progress Tracking

The Tasks section has built-in progress tracking for agents:

1. **Checkbox summary** at the top — quick scan of overall progress:
   ```markdown
   - [x] Task 1: Types and Schema
   - [ ] Task 2: Preferences Service    ← next
   ```

2. **Status field** on each task — agents grep for `**Status**: pending` to find the next task:
   ```markdown
   ### Task 2: Preferences Service
   **Status**: pending | in-progress | done
   ```

3. **Progress counter** — updated as tasks complete:
   ```markdown
   **Progress**: 2/6 complete
   ```

4. **Acceptance criteria checkboxes** — checked off within each task as sub-items complete

When building the Tasks section, initialize all tasks with `**Status**: pending` and unchecked checkboxes. The `/sdd:build` command will update these as it works through the tasks.

### Phase 4: Publish

**Goal**: Create GitHub Issues, update references, show summary.

#### Create GitHub Issues

```bash
# Create epic issue
gh issue create \
  --title "feat: <Feature Name>" \
  --body "<spec summary + link to spec file>"

# Create sub-issues for each task
gh issue create \
  --title "task: <Task title>" \
  --body "<task details + acceptance criteria>"
```

Link sub-issues to epic in the epic body:
```markdown
## Tasks
- [ ] #<issue-1> — Task 1 title
- [ ] #<issue-2> — Task 2 title
```

**If `--ticket` provided**: Include external reference in epic and sub-issues:
```markdown
**External ticket**: JIRA-123
```

**If no `--ticket`**: The GitHub epic IS the ticket.

#### Update References

1. Update the Tasks section in `docs/specs/<name>.md` with issue numbers:
   ```markdown
   ### Task 1: [Component Name] (GH-42)
   ```

2. If `docs/ideas/<name>.md` exists, update its status to `ready-for-spec`

#### Show Summary

```
## Plan Complete

**Spec**: docs/specs/<name>.md
**Epic**: #<epic-number> — <title>
**Tasks**: <N> tasks created

### Task Overview
1. #<issue> — <task title>
2. #<issue> — <task title>
...

**Next step**: Start a **new session** and run `/sdd:build <name>` to implement.
Build must run in a fresh session — the spec file is the complete context.
```

---

## --fast Mode

| Phase | Interactive (default) | Fast (--fast) |
|-------|----------------------|---------------|
| Ingest | Clarify open questions | Make assumptions, confirm once |
| Research | Parallel subagents, present findings | Single quick scan or skip if simple |
| Author | Confirm requirements, then design decisions | Write full spec, present for approval |
| Publish | Identical | Identical |
| Total exchanges | 4-6 | 2-3 |

---

## Multi-Agent Safety

Research subagents in Phase 2 are **read-only** (Explore type) — safe to run in parallel. Each gets a focused prompt with specific research questions.

| Scenario | Safe? | How |
|----------|-------|-----|
| 2-3 Explore agents reading code | Yes | Read-only, no conflicts |
| 1 agent writing spec | Yes | Only one writer at a time |

For future build-phase agents that write code, use worktree isolation or serialize. See the plan document for details.

---

## Guardrails

- **Don't implement** — This phase produces a spec, not code. Save implementation for `/sdd:build`
- **Don't guess file paths** — Research the codebase first, use exact paths from what exists
- **Don't skip confirmation** — Confirm requirements and key design decisions with the user before writing tasks
- **Don't write vague tasks** — Each task needs file paths, acceptance criteria, and a reference file
- **Do use ASCII diagrams** — Visualize architecture in the Design section
- **Do reference existing code** — Every task should point to a similar pattern to follow
- **Do keep it one file** — The spec is a single `docs/specs/<name>.md`, not multiple files
- **Scope discipline** — If the spec grows beyond 12 tasks, suggest splitting into multiple specs

## Additional Resources

### Template
- **`spec-template.md`** — Output template for the spec

### Examples
- **`examples/sample-spec.md`** — Complete reference example

### References
- **`references/task-writing-guide.md`** — How to write effective logical-unit tasks
