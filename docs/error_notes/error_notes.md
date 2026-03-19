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
