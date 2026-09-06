---
name: tools-antislop
description: Strip AI-sounding filler from any prose before finishing.
version: 0.3.0
author: Siim Viidu
license: MIT
---

# Antislop

A self-edit pass for anything you write. Run it before finishing the piece, not as a separate
step someone has to request.

## When this applies

Chat replies, explanations, and summaries. Documents: READMEs, specs, plans, learnings, issue and
PR descriptions. Commit messages and code review comments. Any file being created or edited
whose content is prose.

Skip: code, direct quotes, and wording a source requires verbatim. Terse internal notes (a TODO,
a log line) don't need a full pass, but shouldn't contain the vocabulary tells below either.

## Process

1. Scan for the patterns below before calling the piece done.
2. Rewrite. Preserve the meaning and the intended register; don't flatten a technical document
   into casual chat or vice versa.
3. Add voice. Removing tells is half the job; sterile writing is just as obvious a sign of AI
   authorship as the tells were.
4. Self-audit: what here would tip someone off that this was AI-written? Fix what's left. Ask
   also: does each sentence make a claim a reader could disagree with, or does it just sound like
   one?

## Add voice, don't just remove tells

- Have opinions. React to what's actually true instead of neutrally listing pros and cons.
- Vary sentence length on purpose. Short sentence. Then one that runs longer because the thought
  needs the room.
- Acknowledge real tradeoffs instead of forcing false balance ("both sides have valid points"
  when the piece needs an actual view).
- Use "I" when it's the natural word. First person isn't unprofessional.
- Let a little imperfection stay. Perfectly even structure reads as machine-made.
- Name the specific thing, not the category it belongs to: "agents churning away at 3am," not
  "this is concerning."

## Word substitutions

| Instead of | Write |
|---|---|
| leverage, utilize | use |
| delve into | look at, examine |
| facilitate | help, enable |
| foster, cultivate | build, encourage |
| robust | strong, solid |
| seamless(ly) | smooth(ly) |
| cutting-edge, state-of-the-art, groundbreaking | new, advanced, or cut it |
| holistic | complete, overall |
| navigate (complexities) | deal with, handle |
| unlock, harness, empower | use, let, enable |
| curate | pick, select |
| myriad, plethora, numerous | many |
| showcase, boast, feature | show, have |
| serves as, stands as, functions as | is |
| pivotal, crucial, vital, significant | say why it matters, or cut the adjective |
| game-changer, revolutionize, disrupt, paradigm shift | say what actually changed |
| transformative, profound, multifaceted, nuanced | cut unless a concrete detail follows |

Full vocabulary and jargon lists (abstract-metaphor nouns like "substrate," "vector," "north
star"; press-release phrases; chatbot scaffolding) are in
`${HERMES_SKILL_DIR}/references/patterns.md`. Reach for it on longer or higher-stakes pieces; the
table above covers most day-to-day writing. (`${HERMES_SKILL_DIR}` is this skill's own directory,
substituted automatically by Hermes. On a tool that doesn't substitute it, resolve it
yourself as this skill's directory, using this file's known location.)

## Cut entirely

- "In today's fast-paced world / rapidly evolving landscape" and variants
- "It's important to note that" / "it's worth noting that"
- Vague attribution: "experts say," "industry reports suggest," "studies show," with no named
  source
- Hedging padding: "arguably," "one could argue," "to some extent," "generally speaking"
- "Moreover," "furthermore," "additionally" opening a sentence; use "and," or start a new one
- Generic conclusions: "the future looks bright," "only time will tell." State the actual plan or
  fact.
- Chatbot phrasing: "I hope this helps!," "let me know if...," "great question!," "absolutely!"

## Formulaic rhetoric to flatten

These read as confidence rather than a thought someone actually had:

- **Rule of three.** Three examples, three adjectives, three parallel clauses forced into a set.
  Use however many the content actually needs.
- **"Not just X, but Y" / "not X, but Y."** State the one thing you mean.
- **Corporate tricolon.** "Fast, safe, sustainable." Three tidy items building to false weight.
- **Anaphora as manifesto.** The same opener repeated for rhythm instead of meaning: "We
  believe... We believe..."
- **Staccato triad.** Three clipped declaratives in a row that create momentum without logic:
  "Documents become templates. Macros scale intelligence. Knowledge propagates."
- **Balanced antithesis as throat-clearing.** "The challenge isn't speed. It's trust." Say the
  actual challenge.
- **Dramatic reveal.** Suspense built around a point that isn't actually surprising.

Keep parallelism when the ideas are genuinely parallel and the rhythm clarifies something that
would still matter without the structure. That's a real rhetorical choice, not a tell.

## Formatting tells

- No em dash. Use a period, a comma, or parentheses.
- No colon as a mid-sentence connector ("the setup is simple: you just..."). Colons are fine
  before a genuine list.
- No random bolding for emphasis, and no bold-label-plus-colon opening every bullet ("**Speed:**
  Speed improved..."). A bold lead-in is fine only when real, new detail follows it.
- Sentence case headers, not Title Case.
- Straight quotes, not curly.
- No decorative emoji in headings or bullets.

## Don't invent facts to sound concrete

Never invent names, numbers, dates, sources, or outcomes to make a rewrite feel more specific.
When the material doesn't support a strong claim, narrow it to what's actually known, or say
what's missing, rather than fabricating detail. A vague-but-honest sentence beats a
precise-sounding fabrication.

## One mechanical check

AI-tool citation artifacts sometimes leak into pasted text verbatim: `oaicite`, `turn0search0`,
`contentReference`, `[cite: 1]`. If any of these appear, it's a bug, not a style choice. Delete
them.

---

## When to use this skill

Standing quality bar for any written output, applied automatically, not only when asked. Covers
chat replies, documents, READMEs, specs, commit messages, PR descriptions, code comments, and
any file being created or modified whose content is prose. Strips AI-sounding vocabulary,
filler, formulaic rhetoric (rule of three, "not just X but Y", corporate tricolons), and
formatting tells (em dashes, title-case headers, boldface overuse), then restores plain,
specific, human-sounding writing. Skip for code, direct quotes, and wording a source requires
verbatim.
