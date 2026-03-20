# Error Notes

## 2026-03-19

### 1. Agent-only boundary was written too narrowly

- Symptom: the skill started telling the host that it could only call agents and could not download skills.
- Root cause: wrapper/docs were mistakenly narrowed to an agent-only contract.
- Fix: restore dual capability at the repository level, then split entrypoints so agent execution stays in `scripts/run_agent_client.py` and skill downloads move to `scripts/download_skill.py`.

### 2. Agent and skill download responsibilities were mixed in one script

- Symptom: `run_agent_client.py` name and contract no longer matched the combined behavior.
- Root cause: skill download logic was added directly into the agent runner.
- Fix: move public skill archive download into `scripts/download_skill.py`, keep `run_agent_client.py` agent-only, and split tests/docs accordingly.

### 3. Layout validation was too broad for the download entrypoint

- Symptom: download flow reused a layout check that required `agents_client/`, even though downloading a public skill does not depend on it.
- Root cause: `validate_skill_layout()` represented agent runtime needs, not shared bundle needs.
- Fix: rename the agent-side check to `validate_agent_layout()` and add `validate_download_layout()` in `scripts/download_skill.py` that only requires `requirements.txt`.

### 4. Download filename parsing was incorrect

- Symptom: downloaded archive names could include raw `Content-Disposition` header fragments instead of a clean filename.
- Root cause: filename parsing used manual string splitting on `filename=` and did not properly handle standard header forms such as `filename*=` or more complex parameter layouts.
- Fix: parse `Content-Disposition` via `email.message.Message.get_filename()` and fall back to `skill-<id>.zip` only when no usable filename is provided.

### 5. Download path expectation vs. actual path

- Observation: a run was written under `/private/tmp/...`.
- Verified behavior: `scripts/download_skill.py` still defaults to `skill_root/.runtime/runs/` when `--work-dir` is not provided, because it uses `ensure_work_dir(args.work_dir)`.
- Interpretation: the `/private/tmp/...` path is consistent with an explicit or host-provided `--work-dir`, not with a broken default path implementation.

## 2026-03-21

### 1. Initial database placement ignored the requested repository boundary

- Symptom: the first implementation attempt tried to place SQLite-related code under `agents_client/`.
- Root cause: the solution followed the nearest runtime code path instead of the user's explicit boundary that `agents_client/` should not be touched.
- Fix: move database logic into a separate top-level `database/` directory and keep persistence integration in the wrapper script layer.

### 2. Initial database naming was too abstract

- Symptom: the first proposed module names (`trading_store`, `sqlite_store`) did not communicate clearly that the code represented the project database layer.
- Root cause: naming optimized for implementation intent instead of reviewer readability.
- Fix: rename the module to `database/trading_agent_database.py` and keep path naming explicit.

### 3. Streaming persistence was initially designed against the wrong return shape

- Symptom: streaming runs completed successfully but never wrote a database row.
- Root cause: wrapper logic assumed streaming would return a structured dict with `result`, while the actual client returned only `bool`, and later only `{"event_count", "success"}` without a decision payload.
- Fix: change the streaming client wrapper to return the full response object and then extract the trading action before attempting persistence.

### 4. Streaming contract was treated as if it already carried the final trading decision

- Symptom: even after returning a dict, streaming still produced no database write because there was no `buy/sell/hold` field to persist.
- Root cause: the server-side streaming path emitted progress text and execution stats, but not a stable structured trading decision contract.
- Fix: normalize the final server-side streaming result to `buy/sell/hold` text, parse that final message on the client, and only persist when an action is actually present.

### 5. Persistence logging was misleading

- Symptom: run logs printed `正在写入 trading sqlite database` even when no row was ultimately written.
- Root cause: the status line was emitted before checking whether the streaming payload actually contained a persistable result.
- Fix: split the messages into `正在尝试写入...` before the call and `...写入完成` only after a real row is saved.

### 6. Raw result storage was too verbose for the minimal schema

- Symptom: rows stored `raw_result` as JSON like `{"action": "buy"}` even when the only meaningful payload was the action itself.
- Root cause: raw payload serialization treated all dict payloads uniformly.
- Fix: when the payload is exactly `{"action": "<value>"}`, store `raw_result` as the plain action string and migrate existing rows on initialization.

### 7. Display labels were mistaken for database column names

- Symptom: query output shown with labels such as `操作类型` and `创建时间` created the impression that the database schema itself used Chinese column names.
- Root cause: human-facing display text was conflated with the actual SQLite schema.
- Fix: verify schema directly before changing structure; confirmed columns were already English (`id`, `run_id`, `stock_code`, `mode`, `action`, `created_at`, `updated_at`, `raw_result`).
