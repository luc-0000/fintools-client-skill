# Backtest Design Spec

## Purpose

This document records the first-phase design for adding backtest support to the `fintools-client-skill` repository.

The target flow is:

1. A trading agent run finishes.
2. The agent output is normalized and stored in a local database.
3. A backtest simulator reads the stored agent output and computes simulation results.
4. OpenClaw presents the backtest outcome to the user without requiring a dedicated frontend in the first phase.

This document is a design spec, not a product PRD. It focuses on engineering choices, storage boundaries, and display options.

## Scope

Phase 1 includes:

- Persisting structured trading-agent output.
- Persisting backtest run summaries and trade details.
- Using a database abstraction that supports SQLite first and can later switch to MySQL.
- Returning backtest results in forms OpenClaw can present in chat.
- Optionally generating static report artifacts such as HTML, JSON, or CSV.

Phase 1 excludes:

- Building a standalone web UI.
- Storing market history such as K-line data in the local database.
- Reproducing the entire `fintools_backtests` MySQL schema.
- Designing a multi-user or multi-node deployment.

## Non-Goals

- Replacing Tushare as the source of market data for this phase.
- Making the storage layer optimized for high-concurrency service workloads.
- Building a generic analytics dashboard.

## Key Decisions

### Decision 1: SQLite First, MySQL-Compatible Design

Phase 1 will use SQLite as the default database.

Reasoning:

- This repository is currently a local skill-oriented runtime, not a full backend service.
- SQLite has zero installation cost and fits the first-phase goal of getting the end-to-end path working quickly.
- The first stored data types are relatively small: agent outputs, backtest summaries, and trade records.
- Market history is not being stored locally in this phase, so database volume and query pressure remain limited.

Compatibility requirement:

- The storage layer must be implemented through SQLAlchemy.
- Database configuration must be controlled through a single `DATABASE_URL`.
- Schema and query design should avoid SQLite-only behavior so the system can migrate later to MySQL with limited refactoring.
- Even when SQLite is used, table structure should stay aligned with the existing `fintools_backtests` schema wherever practical so migration cost stays low and existing code can be reused.

### Decision 2: Do Not Store Market History in Phase 1

Phase 1 only stores:

- agent output
- backtest results

Phase 1 does not store:

- daily K-line history
- indicator history
- other large market datasets

Reasoning:

- Current backtest inputs can continue to use Tushare on demand.
- Avoiding market-history storage keeps schema and infrastructure simple.
- This reduces the immediate need for a heavier database such as MySQL.

### Decision 3: No Dedicated UI in Phase 1

Phase 1 will not build a standalone UI.

Instead, OpenClaw will act as the primary presentation layer by showing:

- a short textual summary
- a small Markdown table
- links or paths to generated artifacts such as HTML, JSON, or CSV reports

Reasoning:

- This gets user-visible value faster.
- Chat is suitable for summary and review.
- A dedicated UI adds cost before the result model is stable.

### Decision 4: Agent Result Mapping Uses Existing `agent_trading` Semantics

For the trading agent path in this repository, the agent result is currently boolean:

- `true`
- `false`

That boolean will be mapped into the existing `agent_trading` semantics used by `fintools_backtests`:

- `true -> indicating`
- `false -> not_indicating`

Reasoning:

- This matches the reference repository's mental model.
- This keeps simulator-side reuse simpler.
- This avoids inventing a new signal vocabulary for Phase 1.

The stored record should remain compatible with the existing `agent_trading` table shape and downstream simulator logic.

## Database Choice Discussion

### SQLite Advantages

- No extra install or service bootstrap.
- Very simple local development and local execution.
- Easy to bundle with a skill-oriented workflow.
- Easy to inspect, copy, export, and reset.
- Good fit for single-user or low-concurrency runs.

### SQLite Limitations

- Weak write concurrency compared with MySQL.
- Not appropriate for multi-node shared access.
- Less suitable if the system later becomes a long-running service with many concurrent backtests.
- Some concurrency-oriented patterns from `fintools_backtests`, such as row-lock assumptions, do not translate cleanly.

### Why MySQL Is Not the Default for Phase 1

- The first-phase dataset is small and localized.
- The first-phase workflow does not require a full service database.
- Adding MySQL now would increase setup and operational complexity before the data model is stable.

### Migration Trigger for a Future MySQL Move

Moving to MySQL should be considered when one or more of the following become true:

- multiple workers write results concurrently
- OpenClaw or related services read from a shared deployed database
- backtest volume becomes large enough to stress SQLite
- market history is added to the same storage layer
- the feature becomes a real multi-user service instead of a local skill flow

## Data Model Direction

Phase 1 should keep its table structure as close as practical to the existing `fintools_backtests` schema, even though the runtime database is SQLite by default.

The goal is:

- minimize migration cost to MySQL later
- maximize reuse of existing simulator and query code
- keep naming and storage semantics familiar across repositories

The execution chain is still conceptually:

`agent run -> agent_trading records -> simulator -> simulator_trading records`

But table names and core field semantics should prefer the reference repository where practical.

### Preferred Reused Tables

The most important reusable tables from `fintools_backtests` are:

- `agent_trading`
- `simulator`
- `simulator_trading`
- `simulator_config`

These tables are sufficient for the first-phase persistence boundary.

### `agent_trading`

Purpose:

- Stores trading-agent outputs in the same shape used by the reference repository.

Phase-1 behavior:

- one completed agent evaluation produces a trading record for the given stock and trading date
- boolean agent output is mapped to `trading_type`
- `true -> indicating`
- `false -> not_indicating`

The target semantics are intentionally aligned with `fintools_backtests`.

### `simulator`

Purpose:

- Stores one backtest run summary and its current status.

Phase-1 expectation:

- the schema should stay aligned enough that simulator-side logic from `fintools_backtests` can be migrated with minimal changes

### `simulator_trading`

Purpose:

- Stores detailed backtest-generated trading events.

Phase-1 expectation:

- this remains the main inspectable trade timeline for both OpenClaw summaries and optional report generation

### Optional Additional Metadata Tables

If Phase 1 needs extra local metadata that does not exist in `fintools_backtests`, it should be added carefully and separately rather than changing the reused core table semantics.

Examples:

- local run bookkeeping
- report artifact paths
- host-side execution metadata

These should not break compatibility with the reused backtest tables.

## Relationship to `fintools_backtests`

The reference repository is not just conceptual inspiration. It is the primary compatibility target for this feature.

The reference repository shows that the minimum useful persisted concepts are close to:

- agent trading records
- simulator summary
- simulator trade records

That validates the phase-1 direction.

Phase 1 here should remain smaller in scope, but it should intentionally stay close to the existing storage contract:

- no need to reproduce the full backend system
- yes to reusing the existing table names and core field meanings where practical
- yes to SQLite as the default engine
- yes to MySQL compatibility as a later deployment mode

## Code Reuse Strategy

Phase 1 should prefer reuse over rewrite.

Recommended approach:

- identify reusable code from `fintools_backtests`
- copy it into this repository under `backtests/`
- make only the minimum required changes so it works with this repository's runtime, SQLite default, and local structure

This is preferred over designing a new backtest subsystem from scratch.

Expected reusable areas include:

- SQLAlchemy schema definitions
- simulator logic
- simulator result formatting
- helper query logic around `agent_trading`, `simulator`, and `simulator_trading`

Expected adaptation areas include:

- database initialization for SQLite-first configuration
- repository-local import paths
- removal of unrelated backend dependencies
- minimal adjustments where MySQL-specific assumptions exist

## OpenClaw Presentation Strategy

### Core Principle

OpenClaw should not read raw database rows and improvise presentation logic directly in the chat layer.

Instead, the system should build a presentation-oriented result object from the database and hand that to OpenClaw.

This keeps:

- database schema stable
- display logic explicit
- future UI/report generation easier

### Recommended Phase-1 Presentation Forms

OpenClaw chat should display:

- a short summary paragraph
- a compact metrics block
- a Markdown table of recent or important trades
- artifact paths for deeper inspection

Good chat-level content includes:

- backtest status
- stock code
- backtest period
- initial cash
- final cash
- total return
- max drawdown
- win rate
- trade count
- the most recent trades

### Artifact Strategy

Phase 1 should support optional generated artifacts:

- `report.json`
- `trades.csv`
- `report.html`

Recommended usage:

- OpenClaw shows summary plus table in chat.
- OpenClaw also surfaces the exact artifact path for deeper review.
- The HTML report can carry richer content later without requiring a custom chat UI.

## UI Discussion

### Is a Dedicated UI Required?

No.

A dedicated UI is not required in Phase 1 if OpenClaw can present the summarized result and artifact locations clearly.

### Can OpenClaw Show a Simple UI in Chat?

The current repository only assumes OpenClaw can reliably:

- stream status lines
- show final result lines
- show report paths
- present ordinary chat content

The repository does not currently define a contract for embedded custom frontend components inside the chat window.

Therefore the safe assumption for Phase 1 is:

- yes to summary text
- yes to Markdown tables
- yes to simple structured sections
- yes to artifact paths
- no assumption of a richer embedded custom UI

### Recommended Display Approach

Phase 1 should use this order of presentation:

1. chat summary
2. compact Markdown table
3. report artifact path

This gives users immediate readability while keeping richer detail available outside the chat stream.

## Architecture Guidance

Phase 1 should separate these concerns:

- execution layer: runs the trading agent
- normalization layer: converts agent output into structured signals
- storage layer: persists agent runs, signals, and backtest results
- simulation layer: computes results from stored signals
- presentation layer: builds a user-facing summary object and optional report artifacts

This separation is important because:

- storage should not depend on OpenClaw presentation rules
- simulator should not depend on raw report text format
- OpenClaw should not need direct schema knowledge

## Configuration Direction

Recommended configuration:

- `DATABASE_URL`, defaulting to a SQLite file under the repository runtime area

Example first-phase default:

- `sqlite:///<repo-runtime-path>/backtests.db`

Later deployment options can replace it with MySQL, for example:

- `mysql+pymysql://user:password@host:3306/db_name`

## Risks

### Risk: Signal Normalization Is Underspecified

The largest remaining design risk is not the database engine. It is the shape of the normalized agent signal that becomes the simulator input.

Without a clear signal contract, storage may become too raw or too ad hoc.

### Risk: SQLite Concurrency Limits

If multiple tasks start writing frequently in parallel, SQLite may become a bottleneck sooner than expected.

### Risk: Chat Presentation Becomes Too Heavy

If too much raw detail is pushed directly into OpenClaw chat, the result will be hard to read and hard to maintain.

## Follow-Up Decisions Needed

The next design discussion should define:

1. Which exact files and modules from `fintools_backtests` will be copied into this repository's `backtests/` directory.
2. How `rule_id` will be assigned or configured for reused simulator logic.
3. What summary object shape OpenClaw should consume for display.
4. Which report artifacts are mandatory in Phase 1: JSON only, or JSON plus HTML and CSV.

## Current Recommendation Summary

- Use SQLite in Phase 1.
- Keep the schema aligned with `fintools_backtests` where practical and MySQL-compatible through SQLAlchemy and `DATABASE_URL`.
- Store only agent output and backtest results.
- Do not store K-line or market-history data in this phase.
- Map trading-agent boolean output into `agent_trading.trading_type` using `true -> indicating` and `false -> not_indicating`.
- Reuse and migrate existing `fintools_backtests` code into this repository's `backtests/` directory with minimal changes.
- Do not build a standalone UI yet.
- Let OpenClaw display a summary and small table in chat.
- Generate optional report artifacts for deeper inspection.
