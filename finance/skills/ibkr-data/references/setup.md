# Connecting to IBKR's remote MCP server

## The server

```
https://api.ibkr.com/v1/api/mcp-public
```

It is a remote HTTP MCP server run by Interactive Brokers, the same one that sits behind the
claude.ai IBKR connector. There is no local IB Gateway or TWS to install, and no API key to paste.

Authentication is OAuth 2.1 with PKCE (S256) and dynamic client registration, which means any
compliant MCP client can register itself and log in without a pre-issued client id. The endpoints,
for reference when a client asks or a login has to be debugged:

| Purpose | Endpoint |
|---|---|
| Protected-resource metadata | `https://api.ibkr.com/v1/api/mcp-public/.well-known/oauth-protected-resource` |
| Dynamic client registration | `https://api.ibkr.com/oauth2/register` |
| Authorization | `https://api.ibkr.com/oauth2/authorize` |
| Token | `https://api.ibkr.com/oauth2/api/v1/token` |

The server advertises two scopes: `mcp.read` and `mcp.write`.

## The login, as a user sees it

1. Add the server to the client's MCP configuration (see the per-agent table below).
2. Start or restart the client, or run its connect command. The client registers itself and opens
   IBKR's login page in a browser.
3. Log in with the IBKR username and password, and complete two-factor authentication in the IBKR
   mobile app if the account has it enabled.
4. IBKR shows a consent screen listing what the client is asking for. Approve it, or approve only
   the read scope if the screen lets you deselect the write one.
5. The browser hands control back to the client, which reports the server as connected.

Tokens are held by the client, not by this plugin. A session that expires repeats the browser step.

## Per-agent configuration

Ready-to-paste snippets ship in `finance/mcp/`; the plugin README carries the same table with
install commands.

| Agent | Config file | Snippet |
|---|---|---|
| Claude Code | `~/.claude.json` for every project, or a project `.mcp.json` | `finance/mcp/claude-code.json` |
| Codex CLI, ChatGPT desktop | `~/.codex/config.toml` | `finance/mcp/codex.toml` |
| OpenCode | `opencode.json` | `finance/mcp/opencode.json` |

Each snippet carries a `_comment` describing the login step. Remove that key before pasting if the
client rejects unknown fields. Claude Code users who already reach IBKR through the claude.ai
connector do not need the snippet at all: the connector points at this same server, and adding both
gives the same tools twice under two prefixes.

## Checking which scope was granted

Whether a given client lets you request `mcp.read` alone is not something this document can assert:
it depends on the client's OAuth implementation and on what IBKR's consent screen offers, and it
has not been verified per agent here. Check after logging in rather than assuming.

- The consent screen during login is the first place the requested scopes appear. Read it before
  approving.
- After connecting, open the client's MCP status or authentication view and look at the entry for
  this server. In Claude Code that is `/mcp`, which lists each server, its connection state and its
  authentication details; other clients have an equivalent status or list command. The exact
  wording and how much scope detail each view shows varies, so read what is there rather than
  expecting a particular field.
- The tool list is the practical check. If write tools appear (`create_order_instruction`,
  `create_alert`, `create_watchlist` and the rest in `tool-map.md`), the client holds `mcp.write`,
  whether or not it asked for it.

If the client cannot be limited to `mcp.read`, read-only stays a rule of this plugin rather than a
property of the token: no skill here calls a write tool. Revoking access entirely is done from
IBKR's Client Portal, under the third-party application settings for the account.

### Not verified

Whether any client can request only `mcp.read` at OAuth time is still unverified as of 2026-09-06.
The live checks were run through an already-authorised connection, so the consent screen's options
were not exercised. Treat the steps above as how to find out, not as a claim about what any
particular client does.

## When the tools are absent

Say so and stop. The failure modes look different but the response is the same:

- No IBKR tools in the session at all: the server is not configured, or the client was not
  restarted after the config was edited.
- Tools listed but every call fails with an authentication error: the OAuth session expired.
  Re-running the client's login or connect command starts the browser flow again.
- Tools present, `search_contracts` returns nothing for a symbol: that is an instrument problem,
  not a setup problem. See `venue-rules.md`.

Never fill the gap with remembered prices or with a different instrument. Offer `yfinance-data`,
which needs no account and covers US tickers and EU listings with a Yahoo venue suffix, and say
plainly that it carries no account data and no IBKR contract ids.
