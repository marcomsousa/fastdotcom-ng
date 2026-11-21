# PLAN.md — `fastdotcom-ng` Implementation Roadmap

Clean-room build plan for `marcomsousa/fastdotcom-ng` (PyPI: `fastdotcom-ng`, Python import: `fastdotcom`). Work sequentially phase-by-phase and verify each gate before moving on.

---

## Phase 1: Repository Foundation & `uv` Packaging

1. **Create `LICENSE`**: Standard **MIT License**, `Copyright (c) 2026 Marco Sousa`.
2. **Create `.gitignore`**: Standard Python / `uv` / coverage / cache / `.env` / IDE ignores.
3. **Create `pyproject.toml`**:
   - `[build-system]`: `requires = ["hatchling>=1.27"]`, `build-backend = "hatchling.build"`.
   - `[tool.hatch.build.targets.wheel]`: `packages = ["fastdotcom"]`.
   - `[project]`: `name = "fastdotcom-ng"`, `version = "1.0.0"`, `requires-python = ">=3.11"`, `license = "MIT"`, `license-files = ["LICENSE"]`, `authors = [{ name = "Marco Sousa", email = "marcomsousa@gmail.com" }]`, `dependencies = ["aiohttp>=3.10.0"]`, `[project.scripts] fastdotcom = "fastdotcom.cli:main"`.
   - `[dependency-groups] dev`: `mypy>=1.15.0`, `pre-commit>=4.0.0`, `pytest>=9.0.0`, `pytest-asyncio>=1.0.0`, `pytest-cov>=6.0.0`, `pytest-timeout>=2.3.0`, `ruff>=0.11.0` (do **not** include `pytest-sugar`).
   - Configure `[tool.ruff]`, `[tool.coverage.run]` (`branch = true`, `source = ["fastdotcom"]`), `[tool.coverage.report]` (`fail_under = 95`), `[tool.pytest.ini_options]` (`filterwarnings = ["error"]`, `addopts = "-vv --cov --cov-report term -m 'not real_api_call'"`, `markers = ["real_api_call: Tests making live requests to fast.com (deselected by default)"]`), `[tool.mypy]` (`python_version = "3.11"`, `check_untyped_defs = true` for `fastdotcom.*`).
4. **Create `.pre-commit-config.yaml`**: Standard `pre-commit-hooks` + `ruff-pre-commit`.
5. **Create `README.md` and `CHANGELOG.md`**:
   - Badges: CI, PyPI, Python `3.11–3.15`, PePy (`[![Downloads](https://static.pepy.tech/badge/fastdotcom-ng)](https://pepy.tech/projects/fastdotcom-ng)`).
   - Clear async, sync Home Assistant drop-in, and CLI examples.
6. **Verify**: Run `uv lock && uv sync --all-groups`.

---

## Phase 2: Clean-Room Async Core & CLI (`fastdotcom/`)

1. **`fastdotcom/py.typed`**: Empty PEP 561 marker file.
2. **`fastdotcom/const.py`**:
   - `FAST_COM_URL = "https://fast.com/"`
   - `FAST_API_V2_URL = "https://api.fast.com/netflix/speedtest/v2"`
   - Timeouts, default durations (`DEFAULT_MIN_TIME = 5.0`, `DEFAULT_MAX_TIME = 15.0`), connections (`1..8`), ping defaults (`DEFAULT_PING_COUNT = 5`, `DEFAULT_PING_INTERVAL = 0.5`), chunk sizes (`DEFAULT_DOWNLOAD_CHUNK_SIZE = 128 * 1024`, `DEFAULT_UPLOAD_CHUNK_SIZE = 256 * 1024`, `DEFAULT_UPLOAD_PAYLOAD_SIZE = 4 * 1024 * 1024`).
3. **`fastdotcom/exceptions.py`**:
   - `FastDotComError(Exception)`
   - `FastDotComConnectionError(FastDotComError)`
   - `FastDotComTokenError(FastDotComError)`
   - `FastDotComTimeoutError(FastDotComError)`
4. **`fastdotcom/models.py`**:
   - Frozen slotted dataclasses: `FastLocation`, `FastClientInfo`, `FastTarget`, `FastSpeedtestResult`.
   - `FastSpeedtestResult.to_dict()` returning `{"download_speed": ..., "upload_speed": ..., "unloaded_ping": ..., "loaded_ping": ..., "success": 1}`.
5. **`fastdotcom/client.py`**:
   - `decode_json_bytes(raw: bytes) -> Any`: decode UTF-8 with `latin-1` fallback (handles non-UTF-8 city names in Netflix v2 responses); raise `FastDotComConnectionError` on invalid JSON.
   - `to_range_url(url: str, start: int = 0, end: int = 0) -> str`: rewrite `/speedtest` (or `/speedtest/range/...`) suffix to `/speedtest/range/{start}-{end}` preserving query string.
   - `FastDotComClient`:
     - Accepts `session: aiohttp.ClientSession | None = None`, `timeout: float = ...`, `force_ipv4: bool = False`, `force_ipv6: bool = False` (reject both `True` with `ValueError`; configure `aiohttp.TCPConnector(family=socket.AF_INET / AF_INET6)` when creating internal session).
     - Async context manager (`__aenter__` / `__aexit__`) & `close()` — **only close session if created internally, never close an injected session**.
     - `get_token() -> str`: scrape JS bundle URL from `https://fast.com/` and extract `token:"..."`.
     - `get_targets(token=None, *, url_count=5) -> tuple[FastClientInfo | None, list[FastTarget]]`: single call to v2 API (plus v1 list fallback), check HTTP status, decode cleanly, raise `FastDotComConnectionError` if empty.
     - `measure_latency(url, *, count=5, warmup=True) -> tuple[float, list[float]]`: keep-alive `GET /speedtest/range/0-0` probes timed with `time.perf_counter()`.
     - `measure_download(...) -> tuple[float, int, float, list[float]]`: dynamic parallel async tasks (`1 -> 3 -> 5 -> connections_max`), sliding-window peak Mbps, optional concurrent loaded latency probes triggered by local per-run `download_started` `asyncio.Event`, and `finally:` cancellation + `asyncio.gather(..., return_exceptions=True)`.
     - `measure_upload(...) -> tuple[float, int]`: `POST /speedtest/range/0-0` streaming pre-allocated reusable `bytes(chunk_size)` buffer across dynamically scaled parallel async tasks with `finally:` cancellation.
     - `run_speedtest(...) -> FastSpeedtestResult`: single token+targets fetch, optional `measure_download` / `measure_upload` / `measure_latency`, returning rounded values (2 decimals).
6. **`fastdotcom/__init__.py`**:
   - Export public classes, exceptions, `async_fast_com(...)`, and drop-in sync wrapper `fast_com(...)` accepting legacy kwargs (`verbose`, `max_time`, `ping_count`, `force_ipv4`, `force_ipv6`, `payload_size`, `max_payload_size`) and returning `result.to_dict()`.
7. **`fastdotcom/cli.py`**:
   - Clean `argparse` CLI (`--max-time`, `--min-time`, `--ping-count`, `--no-download`, `--no-upload`, `--no-latency`, `--ipv4`, `--ipv6`, `--json`, `--verbose`) catching `FastDotComError` cleanly.

---

## Phase 3: Offline & Live Test Suites (`tests/`)

1. **`tests/conftest.py`**: Mock `aiohttp` transport / session helpers and sample Fast.com HTML, JS bundle, and v2 API JSON fixtures (including Latin-1 `M\xe1laga` byte `0xe1`).
2. **`tests/test_client.py`**:
   - Token extraction (success, missing script tag, missing token, HTTP non-200 / client error, timeout).
   - Targets parsing (v2 dict with Latin-1 bytes, v1 list fallback, malformed JSON, empty target list, network/timeout errors).
   - `to_range_url` edge cases (with query params, existing `/range/...`, unexpected paths).
   - Unloaded latency (with & without warmup, probe error handling).
   - Download + loaded latency (sliding window, dynamic worker scaling, clean cancellation with zero leaked tasks).
   - Upload (reusable chunk buffer streaming, dynamic scaling, worker failure, clean cancellation).
   - Session ownership (`session` injected stays open vs internally created closes on `__aexit__`), IPv4/IPv6 mutual exclusion & connector family.
   - `async_fast_com` & sync `fast_com` drop-in dictionary contract.
3. **`tests/test_cli.py`**: Human-readable output, `--json` output, and clean error exit status.
4. **`tests/test_real_api_calls.py`**: Marked `@pytest.mark.real_api_call`, tests live `async_fast_com` and `fast_com` end-to-end against `fast.com`.
5. **Verify quality gates**:
   - `uv run ruff check --no-fix .`
   - `uv run ruff format --check .`
   - `uv run mypy fastdotcom tests`
   - `uv run pytest` (100% offline, `>= 95%` branch coverage, zero warnings)
   - `uv build`
   - `uv run pytest -m real_api_call --no-cov`

---

## Phase 4: GitHub Actions CI/CD & PyPI Release (`v1.0.0`)

1. **Create `.github/workflows/main.yml`**:
   - Triggers: `push` to `main`, `pull_request`, `workflow_dispatch`.
   - Matrix: Python `["3.11", "3.12", "3.13", "3.14", "3.15"]`.
   - Use `actions/checkout@v7` and `astral-sh/setup-uv@v10.4.0` (exact semver tag).
   - Steps: `uv sync --locked` → `ruff check` → `ruff format --check` → `mypy` → `pytest --cov-report xml:coverage.xml` → `uv build`.
2. **Create `.github/workflows/publish.yml`**:
   - Triggers: `release: types: [published]`, `workflow_dispatch`.
   - `environment: pypi`, `permissions: id-token: write`.
   - Publish via `pypa/gh-action-pypi-publish@release/v1` with `attestations: true`.
3. **Create `.github/workflows/live_api.yml`**:
   - Triggers: `schedule: [{cron: "0 10 * * 1"}]`, `workflow_dispatch`.
   - Runs `uv run pytest -m real_api_call --no-cov`.
4. **Push & verify workflows**:
   - Commit cleanly (`git config user.name/email` already set to `Marco Sousa <marcomsousa@gmail.com>`), push to `origin main`, and watch `main.yml` and `live_api.yml` pass green via `gh run list --json` + `gh run watch`.
5. **PyPI Trusted Publishing & `v1.0.0` Release**:
   - Register Pending Publisher on `pypi.org` for `fastdotcom-ng` (`marcomsousa/fastdotcom-ng`, `publish.yml`, environment `pypi`).
   - Create GitHub Release `v1.0.0` (`gh release create v1.0.0 ...`) and verify `publish.yml` publishes `fastdotcom-ng` with PEP 740 attestations.

---

## Phase 5: Home Assistant Core Integration PRs (2-PR Strategy)

1. **PR 1 (Minimal Dependency Bump Only):**
   - Branch off `home-assistant/core:dev`.
   - Update only `homeassistant/components/fastdotcom/manifest.json` (`"fastdotcom-ng==1.0.0"`), `requirements_all.txt`, `requirements_test_all.txt` (and `package_constraints.txt` if needed).
   - Audit `git diff` carefully so nothing unrelated changes, run HA component tests & `hassfest`/requirements checks, and open PR 1.
2. **PR 2 (Native Async & Extra Sensors — after PR 1 merges):**
   - Update `homeassistant/components/fastdotcom/coordinator.py` to use `await async_fast_com(session=async_get_clientsession(hass))` directly on the event loop instead of `async_add_executor_job`.
   - Expose **Upload**, **Unloaded Latency**, and **Loaded Latency** sensors in `sensor.py` (with optional `options_flow` toggles to disable upload/latency if desired).
