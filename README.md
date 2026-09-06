# agent-plugins

A general-purpose marketplace of plugins for personal and work productivity, coding workflows, and related tools.

## Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [`sdd`](./sdd/README.md) | 0.8.0 | Spec Driven Development: setup, brainstorm, plan, build, review, finish |
| [`tools`](./tools/README.md) | 0.3.0 | Standalone developer utilities |
| [`finance`](./finance/README.md) | 0.1.0 | Market data providers, on-disk price store, analysis toolkit |

Each plugin's own README has full usage docs. This file covers the marketplace itself.

## Installing a plugin

Add the marketplace once, then install any plugin from it. Swap `sdd` for another plugin name to
install a different one.

**Claude Code**
```
/plugin marketplace add siimvd/agent-plugins
/plugin install sdd@agent-plugins
```

**Codex CLI / ChatGPT desktop** (same plugin runtime, one install covers both)
```
codex plugin marketplace add siimvd/agent-plugins
codex plugin add sdd@agent-plugins
```

**Hermes** (tap install, one config edit needed for the tap path)
```
hermes skills tap add siimvd/agent-plugins
hermes skills install siimvd/agent-plugins/tools-antislop
```
Hermes installs individual skills, not plugins, and taps look for a `skills/` root while this repo
keeps its generated Hermes trees under `hermes/skills/`. See [`tools/README.md`](./tools/README.md#hermes-portability)
for the `taps.json` edit that install needs, the security-scan rules, and the Fly.io setup. Only
plugins with a `scripts/build-hermes.sh` ship a Hermes tree; today that is `tools`.

**OpenCode**: no marketplace install yet. Each plugin ships a build script that generates
OpenCode commands and agents locally; see its README.

Neither marketplace is submitted to a public plugin directory. Both install directly from this
GitHub repo.

## Contributing a plugin

Each plugin is a top-level directory with its own `.claude-plugin/plugin.json` and
`.codex-plugin/plugin.json`, registered in `.claude-plugin/marketplace.json` (Claude Code) and
`.agents/plugins/marketplace.json` (Codex). Before committing, run:

```bash
bash sdd/scripts/lint.sh
```

It checks structure across every registered plugin: skill frontmatter, file references, version
agreement between a plugin's manifests and its marketplace entries, and that generated OpenCode
output is deterministic. It does not check that a skill behaves correctly when invoked.

A plugin that also targets Hermes needs a `scripts/build-hermes.sh` and a `hermes-description` on
every one of its skills; lint then also checks that description's 57-character budget and that the
committed `hermes/` tree matches what the generator produces.

## License

MIT
