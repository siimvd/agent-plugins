# tools — Standalone Developer Utilities

A companion plugin to [`sdd`](../sdd/README.md) for utility skills that don't belong to the
spec-driven workflow. Where `sdd` is a pipeline — setup, brainstorm, plan, build, review,
finish — the skills here are meant to stand alone and be invoked whenever they're useful.

**Status: scaffold.** The plugin structure, manifest, and OpenCode build are in place and
verified, but no skills have been added yet. Installing it today gives you nothing to run.

## Installation

**Claude Code:**
```
/plugin marketplace add siimvd/agent-plugins
/plugin install tools@agent-plugins
```

**Codex CLI / ChatGPT desktop** (same runtime, one install covers both):
```
codex plugin marketplace add siimvd/agent-plugins
codex plugin add tools@agent-plugins
```

**OpenCode:** run `./tools/scripts/build-opencode.sh` from a checkout of this repo — see
OpenCode portability below. There is no distributable install for OpenCode users outside this
repo yet.

## Adding a skill

1. Create `tools/skills/<name>/SKILL.md` with YAML frontmatter carrying at least `name` and
   `description`. The description is what the model matches against, so write it as trigger
   phrases, not a summary — see any skill under `sdd/skills/` for the house style.
2. Put supporting files alongside it and reference them as
   `${CLAUDE_SKILL_DIR}/references/<file>.md`. Keep `SKILL.md` itself short and load detail
   progressively; the reference files are inlined for OpenCode automatically. Claude Code
   substitutes `${CLAUDE_SKILL_DIR}` automatically; Codex and OpenCode don't, so add a one-line
   fallback note after the first reference telling a model how to resolve it itself — see any
   skill under `sdd/skills/` for the pattern.
3. Delete `tools/skills/.gitkeep` once the first real skill lands.
4. Bump the version in `tools/.claude-plugin/plugin.json`, `tools/.codex-plugin/plugin.json`, and
   the `tools` entry in both `.claude-plugin/marketplace.json` and
   `.agents/plugins/marketplace.json`. Lint fails if any of the four disagree.
5. Run the lint and the build:

```bash
bash sdd/scripts/lint.sh
./tools/scripts/build-opencode.sh
```

The skill becomes `/tools:<name>` in Claude Code, and `$tools:<name>` (or the `@` picker in
ChatGPT) in Codex — Codex namespaces plugin skills as `<plugin>:<skill>`, identically to Claude
Code.

## Adding an agent

Create `tools/agents/<name>.md` with `model`, `effort`, and `maxTurns` in frontmatter — lint
requires all three, so no dispatch silently inherits the session default at unbounded turns.
Use `disallowedTools: Write, Edit, NotebookEdit` for read-only roles. The `tools/agents/`
directory does not exist yet; create it when you need the first agent.

## OpenCode portability

```bash
./tools/scripts/build-opencode.sh
```

Generates `.opencode/commands/tools-<skill>.md` and `.opencode/agents/<agent>.md` from the
canonical Claude Code sources. `.opencode/` is gitignored — it is build output, regenerated
on demand.

Unlike `sdd/scripts/build-opencode.sh`, which names each skill and its inline files
explicitly, this script discovers both: skills by globbing `skills/*/SKILL.md`, and the files
to inline by reading each skill's own `${CLAUDE_SKILL_DIR}` references. A new skill needs no
edit to the build script. Run against an empty plugin it reports that there is nothing to
build and exits 0.

`maxTurns` maps to OpenCode's documented `steps` field. `effort` has no verified equivalent for
Anthropic models and is dropped, with an HTML comment in the generated file naming what was lost
and why.

## Codex / ChatGPT portability

`tools/.codex-plugin/plugin.json` is the manifest; no build step — Codex reads
`skills/*/SKILL.md` directly, so a new skill needs no regeneration. `tools/agents/*.md` is not
read by Codex; it only reads `skills/<skill>/agents/openai.yaml` inside a skill, for display
metadata, not dispatch.

## License

MIT
