# finance: Market data and analysis

Skills for pulling market data from Interactive Brokers and Yahoo Finance into a normalised
on-disk store, and analysing it with a stdlib Python toolkit. The store is the point: a year of
daily bars is roughly 15KB of JSON, so fetching several instruments straight into the transcript
exhausts the context window before any analysis starts. Fetch once, write to disk, then let the
scripts compute and print only a summary.

Everything here runs from any agent that reads Agent Skills and has a shell. IBKR is reached
through IBKR's official remote MCP server, so any MCP-capable client can be configured to use it.

## What this plugin does not do

It drafts analysis for a human to review. It makes no investment recommendations, and it executes
nothing: no orders, no transfers, no account changes. The IBKR skills read market and account data
only, and never call a write tool. Grant the `mcp.read` scope where your client lets you choose.

## Skills

| Skill | Description |
|-------|-------------|
| `yfinance-data` | Fetch price history and fundamentals from Yahoo Finance into the store, for US tickers and EU listings with a Yahoo venue suffix. |

This plugin ships no agents. There is no `finance/agents/` directory.

## Installation

**Claude Code:**
```
/plugin marketplace add siimvd/agent-plugins
/plugin install finance@agent-plugins
```

**Codex CLI / ChatGPT desktop** (same runtime, one install covers both):
```
codex plugin marketplace add siimvd/agent-plugins
codex plugin add finance@agent-plugins
```

**OpenCode:** run `./finance/scripts/build-opencode.sh` from a checkout of this repo. There is no
distributable install for OpenCode users outside this repo yet.

## Per-agent usage

| Agent | Invoke a skill as | Install | IBKR MCP snippet goes in |
|-------|-------------------|---------|--------------------------|
| Claude Code | `/finance:<skill>` | `/plugin install finance@agent-plugins` | `~/.claude.json` for every project, or a project `.mcp.json` |
| Codex CLI, ChatGPT desktop | `$finance:<skill>` or the `@` picker | `codex plugin add finance@agent-plugins` | `~/.codex/config.toml` |
| OpenCode | `finance-<skill>` command | `./finance/scripts/build-opencode.sh` | `opencode.json` |

## IBKR MCP setup

`finance/mcp/` holds a ready-to-paste snippet per agent, each pointing at IBKR's official remote
server at `https://api.ibkr.com/v1/api/mcp-public`:

- [`mcp/claude-code.json`](./mcp/claude-code.json)
- [`mcp/codex.toml`](./mcp/codex.toml)
- [`mcp/opencode.json`](./mcp/opencode.json)

The server uses OAuth 2.1 with PKCE and dynamic client registration, so a compliant client can log
in without a pre-registered client id. On first connect it opens IBKR's login in a browser. It
advertises two scopes, `mcp.read` and `mcp.write`; approve only `mcp.read`. Remove the `_comment`
key before pasting if your client is strict about unknown fields.

The snippets are not bundled as a plugin `.mcp.json` on purpose. If you already reach IBKR through
the claude.ai connector, bundling would give you the same tool set twice.

## Store layout

The store lives at `~/.finance/`, or at `$FINANCE_STORE` if that is set. It is created on first
write.

```
~/.finance/
  registry.json                              instrument registry, ISIN as the join key
  raw/<...>.json                             raw provider responses, kept for re-ingest
  bars/<source>/<KEY>_<interval>.csv         date,open,high,low,close,volume
  bars/<source>/<KEY>_<interval>.meta.json   source, symbol, exchange, currency, adjusted, ...
  fundamentals/<ticker>.json
```

`<source>` is `ibkr` or `yfinance`. `KEY` is provider-native, so `IBIS2_VWCE` for IBKR and
`VWCE.DE` for Yahoo, which lets ingest run before the registry knows the instrument. The sidecar
carries the ISIN once the registry resolves it, and analysis scripts accept either form.

Nothing under `~/.finance/` is in this repo, and nothing account-specific belongs in it. Lint
scans committed plugin content for IBAN-shaped tokens and fails on a match.

## Adding a skill

1. Create `finance/skills/<name>/SKILL.md` with YAML frontmatter carrying at least `name` and
   `description`. The description is what the model matches against, so write it as trigger
   phrases, not a summary.
2. Put supporting files alongside it and reference them as
   `${CLAUDE_SKILL_DIR}/references/<file>.md`, and toolkit scripts as
   `${CLAUDE_PLUGIN_ROOT}/toolkit/<script>.py`. Claude Code substitutes both; Codex and OpenCode
   do not, so add a one-line fallback note after the first reference telling a model how to
   resolve the path itself.
3. Bump the version in `finance/.claude-plugin/plugin.json`, `finance/.codex-plugin/plugin.json`,
   and the `finance` entry in both `.claude-plugin/marketplace.json` and
   `.agents/plugins/marketplace.json`. Lint fails if any of the four disagree.
4. Run the lint, the tests, and the build:

```bash
bash sdd/scripts/lint.sh
python3 -m unittest discover -s finance/toolkit/tests -v
./finance/scripts/build-opencode.sh
```

## OpenCode portability

```bash
./finance/scripts/build-opencode.sh
```

Generates `.opencode/commands/finance-<skill>.md` from the canonical Claude Code sources.
`.opencode/` is gitignored: it is build output, regenerated on demand.

The script discovers skills by globbing `skills/*/SKILL.md` and the files to inline by reading
each skill's own `${CLAUDE_SKILL_DIR}` references, so a new skill needs no edit to the script.
It also rewrites `${CLAUDE_PLUGIN_ROOT}` to the absolute path of this checkout, because OpenCode
does not substitute the variable and its users run the build from a checkout, where the path is
known. Run against an empty plugin it reports that there is nothing to build and exits 0.

## Codex / ChatGPT portability

`finance/.codex-plugin/plugin.json` is the manifest. No build step: Codex reads
`skills/*/SKILL.md` directly, so a new skill needs no regeneration. `${CLAUDE_PLUGIN_ROOT}` is not
substituted there either, which is why every skill carries the fallback sentence.

## License

MIT
