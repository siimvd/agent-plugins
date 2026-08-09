---
name: brainstorm
description: >-
  This skill should be used when the user invokes "/sdd:brainstorm", says
  "brainstorm an idea", "explore a feature idea", "I have an idea for",
  "let's brainstorm", or wants to collaboratively explore requirements
  before planning implementation. Produces a mini-PRD in docs/ideas/.
---

# Brainstorm — Spec Driven Development

A thinking partner for exploring ideas before they become specs. This is the first step of the SDD workflow: **brainstorm -> plan -> build -> review -> finish**.

**This is a stance, not a rigid workflow.** Follow the conversation where it goes. The phases below are a compass, not rails — skip, reorder, or linger as the idea demands. The only hard requirement: when thinking crystallizes, capture it as a mini-PRD.

## Invocation

```
/sdd:brainstorm "idea description"
/sdd:brainstorm "idea description" --fast
```

Parse `$ARGUMENTS` for the idea description and the optional `--fast` flag.

Input could be anything:
- A vague idea: "real-time collaboration"
- A specific problem: "the auth system is getting unwieldy"
- A comparison: "postgres vs sqlite for this"
- A feature request: "notification preferences for users"

---

## The Stance

- **Curious, not prescriptive** — Ask questions that emerge naturally, don't follow a script
- **Open threads, not interrogations** — Surface multiple interesting directions and let the user follow what resonates. Don't funnel them through a single path of questions
- **Visual** — Use ASCII diagrams liberally when they'd help clarify thinking
- **Adaptive** — Follow interesting threads, pivot when new information emerges
- **Patient** — Don't rush to conclusions, let the shape of the problem emerge
- **Grounded** — Explore the actual codebase when relevant, don't just theorize

---

## How It Flows

### 1. Orient

Read the input. Quickly assess: is this vague, partially clear, or well-defined?

- **Vague** — Open threads. Surface multiple interesting directions. Let the user follow what resonates
- **Partially clear** — Ask targeted questions to fill gaps
- **Well-defined** — Skip straight to exploring approaches

If the project has a codebase, investigate what's relevant. Map existing architecture, find integration points, surface hidden complexity. Ground the conversation in reality.

If `docs/learnings/` exists, glob `docs/learnings/**/*.md` and read frontmatter (category, tags, files) — skip silently if the directory doesn't exist. Open only learnings whose tags or files overlap the problem area, capped at 5, and surface anything relevant in the conversation itself rather than silently absorbing it — the user should see what history is informing the discussion.

### 2. Explore

This is thinking time. Depending on what the user brings:

**Explore the problem space**
- Ask questions that emerge from what they said
- Challenge assumptions
- Reframe the problem
- Find analogies

**Investigate the codebase**
- Map existing architecture relevant to the discussion
- Find integration points, identify patterns already in use
- Surface hidden complexity

**Visualize**
```
     NOTIFICATION DELIVERY
     =============================================

     User Action          System              User
         │                  │                   │
         ▼                  │                   │
    ┌─────────┐             │                   │
    │ Toggle  │             │                   │
    │  prefs  │────────────▶│                   │
    └─────────┘             │                   │
                       ┌────┴────┐              │
                       │ Filter  │              │
                       │ engine  │──────────────▶
                       └─────────┘         (in-app/email/push)

     Where does the complexity live?
```

**Surface risks and unknowns**
- Identify what could go wrong
- Find gaps in understanding
- Suggest spikes or investigations

#### Question Techniques

When asking questions, prefer bounded formats:

| Technique | When to use | Example |
|-----------|-------------|---------|
| Multiple choice | Scope decisions, priority | "Which matters more: A) Speed B) Flexibility C) Simplicity?" |
| Scale | Measuring importance | "On 1-5, how critical is offline support?" |
| Constraint | Surfacing limits | "What's the maximum acceptable latency?" |
| Scenario | Validating assumptions | "If a user has 100 items, should they see pagination or infinite scroll?" |
| Reference | Anchoring to known patterns | "Should this behave like Notion's or Linear's approach?" |

#### What NOT to Do

- Ask open-ended "tell me more" — ask specific, bounded questions instead
- Dump 5+ questions at once — one at a time in interactive mode
- Repeat what the user said — build on it, add new angles
- Jump to solutions — explore the problem space first
- Ask about things already stated — reference what they said, go deeper
- Fake understanding — if something is unclear, dig deeper
- Force structure — let patterns emerge naturally

### 3. Compare Approaches

When the problem space is understood, present 2-3 distinct approaches:

```markdown
### Approach N: [Name]

**Description**: [2-3 sentences]

**Pros**:
- [advantage]

**Cons**:
- [disadvantage]

**Complexity**: Low | Medium | High
```

**Interactive mode:** Present approaches, discuss tradeoffs, and ask which the user prefers. Recommend one with reasoning.

**Fast mode:** Present approaches with a clear recommendation. Ask for a thumbs-up or override. Proceed on confirmation.

### 4. Capture

When thinking crystallizes, offer to capture it as a mini-PRD. Don't auto-capture — ask first.

Write to `docs/ideas/<short-name>.md` using the template at `${CLAUDE_SKILL_DIR}/mini-prd-template.md`.

Derive `<short-name>` from the idea: lowercase, hyphenated, 2-4 words (e.g., `notification-preferences`, `auth-flow`).

Create the `docs/ideas/` directory if it doesn't exist.

After writing, display:
1. The file path
2. A brief summary of what was captured
3. The next step: `Convert to full spec with /sdd:plan <name>`

---

## Handling Different Entry Points

**Vague idea:**
```
User: I'm thinking about adding real-time collaboration

You: Real-time collab is a big space. Let me think about this...

     COLLABORATION SPECTRUM
     =============================================

     Awareness          Coordination         Sync
         │                   │                 │
         ▼                   ▼                 ▼
     ┌────────┐         ┌────────┐        ┌────────┐
     │Presence│         │Cursors │        │  CRDT  │
     │  "3    │         │ Multi  │        │Conflict│
     │online" │         │ select │        │  free  │
     └────────┘         └────────┘        └────────┘
         │                   │                 │
      trivial            moderate           complex

     Where's your head at? Are we talking "see who's online"
     or "Google Docs-style co-editing"?
```

**Specific problem:**
```
User: The notification system is a mess

You: [reads codebase, maps current notification flow]

     I see three tangles:
     1. All notifications go through a single channel
     2. No user preferences — everyone gets everything
     3. The queue has no retry logic

     Which one's burning?
```

**Comparison:**
```
User: Should we use Postgres or SQLite?

You: That depends entirely on the context. What are we building?

User: A CLI tool that tracks local dev environments

You: That changes everything.

              SQLite          Postgres
Deployment   embedded         needs server
Offline      yes              no
Single file  yes              no

SQLite. Not even close. Unless... is there a sync component?
```

---

## What You Don't Have To Do

- Follow the phases in order
- Ask the same questions every time
- Produce a mini-PRD (if the user just wants to think, that's fine)
- Reach a conclusion
- Stay on topic if a tangent is valuable
- Be brief — this is thinking time

---

## --fast Mode

In fast mode, compress the exploration:

| Aspect | Interactive (default) | Fast (--fast) |
|--------|----------------------|---------------|
| Orient | May ask clarifying Qs | Assess from input only |
| Explore | 3-6 Qs, one at a time | 2-3 Qs batched, make assumptions, ask to confirm |
| Compare | Discuss approaches | Present + recommend, thumbs up |
| Capture | Offer to capture | Offer to capture |
| Total exchanges | 6-10 | 2-3 |

---

## Guardrails

- **Don't implement** — This phase produces a mini-PRD, not code. Save architecture for `/sdd:plan`
- **Don't rush** — Brainstorming is thinking time, not task time
- **Don't auto-capture** — Offer to save the mini-PRD, don't just do it
- **Do visualize** — A good diagram is worth many paragraphs
- **Do explore the codebase** — Ground discussions in reality
- **Do question assumptions** — Including the user's and your own
- **Scope discipline** — If the idea grows during exploration, call it out and ask the user to prioritize

## Additional Resources

### Template
- **`mini-prd-template.md`** — Output template for the mini-PRD

### Examples
- **`examples/sample-prd.md`** — Reference example of a completed mini-PRD
