# IBKR MCP tool map

Tool names are bare here. Each client prefixes them with its own name for the server, so the tool
listed in a session is a longer string ending in the bare name. Match on that trailing bare name.

"Used in this slice" says whether the current finance plugin calls the tool. "Later" means the tool
is read-only and available, but nothing here calls it yet.

## Read tools

### Instruments and market data

| Tool | Returns | Used in this slice |
|---|---|---|
| `search_contracts(query, language?)` | Contract rows for a symbol, name or ISIN: `underlying_contract_id`, `exchange`, `symbol`, `description`, `country_code`, `sections[{security_type}]`. Never returns an ISIN. | yes |
| `search_futures` | Futures contracts for a root symbol, with expiries. | later |
| `get_price_history(contract_id, security_type, step, outside_rth, period? \| step_count?, exchange?, include_corporate_actions?)` | OHLCV as parallel arrays plus `chart_step`, `chart_start`, `chart_end`, `expires`, `source`, optional `delayed` and `corp_actions[]`. | yes |
| `get_price_snapshot(contract_id, exchange?, market_data_names?[])` | Current quote fields, hyphenated keys (`bid-ask`, `top-status`). Fields that time out within 10 seconds are omitted. | later |
| `get_option_parameters` | Expiries, strikes and multipliers available for an underlying. | later |
| `get_option_data` | Quote and greeks for a specific option contract. | later |
| `get_combo_identifier` | The identifier for a multi-leg combo, for use in later calls. | later |

### Account and portfolio

| Tool | Returns | Used in this slice |
|---|---|---|
| `get_account_summary` | Account-level figures including net liquidation and `gross_position_value`. | later |
| `get_account_balances` | Cash balances per currency. | later |
| `get_account_positions` | Open positions with quantity, cost basis and market value. | later |
| `get_account_orders` | Open and recently filled orders. | later |
| `get_account_trades` | Executed trades over a recent window. | later |
| `get_pa_allocation(type, currency?, date?)` | Portfolio analyst allocation by asset class, sector or region. Currency labels are unreliable; see `quirks.md`. | later |
| `get_pa_performance_all_periods` | Cumulative performance over standard periods. | later |

### Watchlists, alerts and orders, read side

| Tool | Returns | Used in this slice |
|---|---|---|
| `get_watchlists` | The account's watchlists. | later |
| `get_watchlist` | One watchlist and its instruments. | later |
| `get_alerts` | Configured alerts. | later |
| `get_alert` | One alert's definition and status. | later |
| `get_order_instructions` | Staged order instructions, read only. | later |

### Research and content

| Tool | Returns | Used in this slice |
|---|---|---|
| `get_company_themes` | Investment themes a company belongs to. | later |
| `get_company_connections` | Companies connected to a given one, as suppliers, customers or peers. | later |
| `get_theme_details` | Constituents and description of a theme. | later |
| `search_investment_topics` | Research topics matching a query. | later |
| `whats_new` | Changes to the IBKR MCP server itself. | later |

## Never called by this plugin

These tools write to the account or to IBKR's records. No skill in this plugin calls any of them,
in any circumstance, including when a user asks for it: this plugin drafts analysis, and executing
belongs in the broker's own interface where the user sees the confirmation.

- `create_order_instruction`
- `delete_order_instruction`
- `create_alert`
- `update_alert`
- `delete_alert`
- `set_alert_status`
- `create_watchlist`
- `edit_watchlist`
- `delete_watchlist`
- `provide_customer_feedback`

If a request would need one of these, say what the user would do in IBKR's own interface and stop
there.
