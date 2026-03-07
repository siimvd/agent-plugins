# Task Writing Guide

How to write effective logical-unit tasks for SDD specs.

## What is a Logical Unit?

A logical unit is the smallest piece of work that:
- Produces a meaningful, testable change
- Can be described with a clear commit message (not "WIP" or "partial X")
- Makes sense as a standalone code review diff

## Task Structure

Every task follows this structure:

```markdown
### Task N: [Component/Feature Name]

**Depends on**: [Task N-1, if any]

**Files:**
- Create: `exact/path/to/new-file.ts`
- Modify: `exact/path/to/existing-file.ts`
- Test: `tests/exact/path/to/test-file.ts`
- Reference: `path/to/similar/code.ts` (follow this pattern)

**What to build:**
- [Clear description of what this task produces]
- [Specific behaviors to implement]

**Acceptance criteria:**
- [ ] [Verifiable criterion 1]
- [ ] [Verifiable criterion 2]
- [ ] Tests cover: [specific scenarios]

**Commit**: `feat(<scope>): <description>`
```

## Rules

### File Paths
- Always use exact paths from the codebase research
- Specify action: Create, Modify, Test, Reference
- Include a reference file for every task — the agent should match existing patterns
- If no similar pattern exists, note "New pattern" and describe the convention

### Acceptance Criteria
- Must be mechanically verifiable (an agent can check it)
- Include specific test scenarios, not "tests pass"
- Good: "Tests cover: valid input, missing required field, unauthorized access"
- Bad: "Tests are written"

### Dependencies
- Tasks are ordered by dependency
- Task N should only depend on tasks with lower numbers
- If tasks are independent, note "No dependencies" — these can run in parallel

### Commit Messages
- Use conventional commits: `feat`, `fix`, `test`, `chore`, `refactor`
- Include scope: `feat(auth): add token validation`
- One commit per task, no WIP commits

## Sizing Guide

| Size | Task Count | Example |
|------|-----------|---------|
| Bug fix | 1-2 | Fix + test |
| Small feature | 3-5 | Schema + service + API + UI |
| Medium feature | 6-8 | Types + schema + service + API + UI + navigation + integration test |
| Large feature | 9-12 | Split into sub-features if approaching 12 |
| Too large | 12+ | Split into multiple specs |

## Common Task Patterns

### Data Layer First
1. Types + schema + migration
2. Service/repository layer
3. API routes
4. UI components
5. Integration/navigation
6. End-to-end test

### Fix Pattern
1. Reproduce with failing test
2. Implement fix
3. Verify fix + regression test

### Refactor Pattern
1. Add characterization tests (capture current behavior)
2. Refactor implementation
3. Verify tests still pass

## What NOT to Do

- Don't create separate "write test" and "write implementation" tasks — TDD is built into each task
- Don't include tasks for "set up environment" or "read the codebase" — that's the agent's job
- Don't write tasks that say "add error handling" without specifying which errors
- Don't use vague file paths like "the auth module" — use exact paths
- Don't create tasks without acceptance criteria
- Don't create tasks that can't be described with a clear commit message
