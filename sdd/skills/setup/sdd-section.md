
---

## Spec Driven Development (SDD)

This project uses the SDD workflow (https://github.com/siimvd/agent-sdd) for structured feature development. SDD provides a repeatable process from idea to shipped feature.

### Workflow

```
brainstorm -> plan -> build -> review -> finish
```

| Command | Description |
|---------|-------------|
| `/sdd:brainstorm` | Explore an idea collaboratively, produce a mini-PRD |
| `/sdd:plan` | Convert mini-PRD or description to full spec + GitHub Issues |
| `/sdd:build` | Autonomous spec execution with worktrees, commits, and PR |
| `/sdd:review` | Review implementation or action existing review findings |
| `/sdd:finish` | Verify review, merge PR, archive spec, compound learnings, cleanup |

### Directory Structure

```
docs/
  ideas/          <- brainstorm output (mini-PRDs)
  specs/          <- plan output (full specs, the source of truth for builds)
    .templates/   <- spec templates
    archive/      <- finished specs (moved here by /sdd:finish)
  learnings/      <- compounded knowledge (created by /sdd:finish)
```

### Conventions

- **Specs are the source of truth** — `/sdd:build` executes from the spec file, not from conversation context
- **One spec per feature** — each spec lives at `docs/specs/<name>.md`
- **GitHub Issues track progress** — `/sdd:plan` creates an epic + sub-issues; `/sdd:build` updates them
- **Worktrees isolate work** — builds run in `.worktrees/<name>` to avoid disrupting your working tree
- **Learnings compound** — `/sdd:finish` captures patterns, gotchas, and mistakes for future sessions
