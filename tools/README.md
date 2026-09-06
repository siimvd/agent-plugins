# tools: Standalone Developer Utilities

A companion plugin to [`sdd`](../sdd/README.md) for utility skills that don't belong to the
spec-driven workflow. `sdd` is a pipeline (setup, brainstorm, plan, build, review, finish); the
skills here are meant to stand alone and be invoked whenever they're useful.

## Skills

| Skill | Description |
|-------|-------------|
| [`antislop`](./skills/antislop/SKILL.md) | Standing quality bar for anything written: chat replies, docs, commit messages, comments. Strips AI-sounding vocabulary, filler, and formulaic rhetoric, then adds back plain, specific voice. Applies automatically; invoke directly as `/tools:antislop` (Claude Code) or `$tools:antislop` (Codex) to run it on demand. |

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

**OpenCode:** run `./tools/scripts/build-opencode.sh` from a checkout of this repo (see OpenCode
portability below). There is no distributable install for OpenCode users outside this repo yet.

**Hermes:** install from a tap, which needs one config edit for the tap path (see Hermes
portability below).

## Adding a skill

1. Create `tools/skills/<name>/SKILL.md` with YAML frontmatter carrying at least `name` and
   `description`. The description is what the model matches against, so write it as trigger
   phrases, not a summary (see any skill under `sdd/skills/` for the house style). Add a
   `hermes-description` too: one line, at most 57 characters, which is all Hermes shows the model
   in its skill index. Lint requires it for every skill in a plugin that has a
   `scripts/build-hermes.sh`, which `tools` does; a plugin without one is not checked.
2. Put supporting files alongside it and reference them as
   `${CLAUDE_SKILL_DIR}/references/<file>.md`. Keep `SKILL.md` itself short and load detail
   progressively; the reference files are inlined for OpenCode automatically. Claude Code
   substitutes `${CLAUDE_SKILL_DIR}` automatically; Codex and OpenCode don't, so add a one-line
   fallback note after the first reference telling a model how to resolve it itself (see any
   skill under `sdd/skills/` for the pattern).
3. Bump the version in `tools/.claude-plugin/plugin.json`, `tools/.codex-plugin/plugin.json`, and
   the `tools` entry in both `.claude-plugin/marketplace.json` and
   `.agents/plugins/marketplace.json`. Lint fails if any of the four disagree.
4. Run the lint and the build:

```bash
bash sdd/scripts/lint.sh
./tools/scripts/build-opencode.sh
./tools/scripts/build-hermes.sh
```

Commit the `hermes/` output. Lint reruns the generators and fails if the committed tree differs.

The skill becomes `/tools:<name>` in Claude Code, and `$tools:<name>` (or the `@` picker in
ChatGPT) in Codex, which namespaces plugin skills as `<plugin>:<skill>` identically to Claude
Code.

## Adding an agent

Create `tools/agents/<name>.md` with `model`, `effort`, and `maxTurns` in frontmatter. Lint
requires all three, so no dispatch silently inherits the session default at unbounded turns.
Use `disallowedTools: Write, Edit, NotebookEdit` for read-only roles. The `tools/agents/`
directory doesn't exist yet; create it when you need the first agent.

## OpenCode portability

```bash
./tools/scripts/build-opencode.sh
```

Generates `.opencode/commands/tools-<skill>.md` and `.opencode/agents/<agent>.md` from the
canonical Claude Code sources. `.opencode/` is gitignored: it's build output, regenerated
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

`tools/.codex-plugin/plugin.json` is the manifest. No build step: Codex reads
`skills/*/SKILL.md` directly, so a new skill needs no regeneration. `tools/agents/*.md` is not
read by Codex; it only reads `skills/<skill>/agents/openai.yaml` inside a skill, for display
metadata, not dispatch.

## Hermes portability

```bash
./tools/scripts/build-hermes.sh
```

Generates `hermes/skills/tools-<skill>/` from the canonical Claude Code sources. Unlike
`.opencode/`, this output is committed: a tap fetches skills from GitHub, so build output that
exists only on your machine cannot be installed by anyone.

To install:

```bash
hermes skills tap add siimvd/agent-plugins
# taps default to a skills/ root; this repo keeps them under hermes/skills/
# edit ~/.hermes/skills/.hub/taps.json and set "path": "hermes/skills" for this entry
hermes skills install siimvd/agent-plugins/tools-antislop
```

There is no CLI flag for the tap path. Editing `taps.json` is the documented route.

To update, run `hermes skills check` to see what has changed upstream, then `hermes skills update`.
A skill you have edited locally is skipped unless you pass `--force`.

Every hub install is security-scanned. A `dangerous` verdict blocks the install and `--force` does
not override it. A `caution` verdict blocks for community sources, and there `--force` does get you
through.

`${CLAUDE_SKILL_DIR}` becomes `${HERMES_SKILL_DIR}`, which Hermes substitutes. Reference files are
copied rather than inlined, so progressive disclosure through `skill_view` still works.

Hermes shows the model only the first 57 characters of a description in its skill index, so the
generator puts the skill's `hermes-description` there rather than the full `description`. The skill
becomes `/tools-antislop`.

### Fly.io

`HERMES_HOME` is `/opt/data` in the container, bind-mounted to the persistent volume. Installed
skills land in `/opt/data/skills/` and the tap config in `/opt/data/skills/.hub/taps.json`, so both
survive a redeploy as long as the volume stays attached.

Run `fly ssh console` and do the install from inside the container with the three commands above.
The file to edit for the tap path is `/opt/data/skills/.hub/taps.json`.

If tap installs prove awkward, the alternative is to clone this repo onto the volume and add the
path to `skills.external_dirs` in `/opt/data/config.yaml`. That route recurses into subdirectories,
updates with `git pull`, and is also security-scanned, though a `dangerous` skill found there is
quarantined rather than blocked at install.

## License

MIT
