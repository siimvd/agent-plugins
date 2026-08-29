# agent-plugins

A general-purpose marketplace of plugins for personal and work productivity, coding workflows, and related tools.

## Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [`sdd`](./sdd/README.md) | 0.8.0 | Spec Driven Development: setup, brainstorm, plan, build, review, finish |
| [`tools`](./tools/README.md) | 0.2.0 | Standalone developer utilities |

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

## License

MIT
