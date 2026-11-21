# AGENTS.md — `fastdotcom-ng`

## 1. Project Identity & Mission

**`fastdotcom-ng`** is a **clean-room, from-scratch** asynchronous Python library and CLI for measuring Internet speed (download, upload, unloaded latency, and loaded latency) using Netflix's [Fast.com](https://fast.com/) API v2.

- **Why starting from scratch (`0`-legacy codebase):** The upstream [`nkgilley/fast.com`](https://github.com/nkgilley/fast.com) (`fastdotcom`) package suffers from fundamental architectural and legal/maintenance issues:
  - Mixes synchronous `urllib.request`, `requests.Session`, daemon `threading.Thread`s (which leak past download completion and pollute the subsequent upload test), and `asyncio.run(async_ping(...))` inside worker threads.
  - Uses a module-global `download_started = Event()` that is never reset across runs.
  - Relies on `icmplib` ICMP sockets (which fail without raw-socket privileges inside containers/Home Assistant OS), calls `api.fast.com/netflix/speedtest` 4 redundant times per test, bottlenecks Raspberry Pi CPUs with `os.urandom()` inside the upload loop, swallows exceptions returning `0` (causing false `0 Mbps` drops in HA), and uses `setup.py` + `distutils` fallback with zero unit tests.
  - Carries mixed `LICENSE` (LGPL-3.0 from `sanderjo/fast.com`) vs `setup.py`/`README.md` (`MIT`) metadata.
- **Mission:** Build a modern, 100% original, MIT-licensed `asyncio` + `aiohttp` implementation from a clean slate with zero legacy code, while staying **100% drop-in compatible** with Home Assistant Core's `fastdotcom` integration.
- **Repository & License:** Public repository at `https://github.com/marcomsousa/fastdotcom-ng` under the **MIT License** (`Copyright (c) 2026 Marco Sousa`).
- **Package vs Import Name:** PyPI distribution name is **`fastdotcom-ng`**, while the Python import package remains **`fastdotcom`** (`[tool.hatch.build.targets.wheel] packages = ["fastdotcom"]`) for seamless Home Assistant drop-in replacement.

---

## 2. Empirical Fast.com Protocol Specification & Design Goals

All protocol behaviors below were empirically verified against live `fast.com` and `api.fast.com` endpoints (`2026-11-21`):

1. **Pure `asyncio` + `aiohttp>=3.10.0` (Zero Sync HTTP / Zero ICMP):**
   - Python `>=3.11` stdlib (`asyncio.timeout`, built-in `TimeoutError`, `asyncio.Event`, `asyncio.TaskGroup`/task lifecycle) + `aiohttp>=3.10.0`.
   - No `requests`, no `urllib.request`, no `threading`, no `icmplib`.

2. **Public Token Discovery:**
   - `GET https://fast.com/` → parse HTML for the bundle `<script[^>]+src="([^"]+\.js)"` (note: bare `urllib` can receive HTTP `403 Forbidden`; `aiohttp` succeeds cleanly — wrap non-200 or missing matches in typed exceptions).
   - `GET https://fast.com<js_path>` → extract token via `token:"([^"]+)"` regex.

3. **Targets Discovery via API v2 (Single Call per Speedtest Run):**
   - `GET https://api.fast.com/netflix/speedtest/v2?https=true&token=<token>&urlCount=5`
   - Returns JSON dict with `"client"` (`ip`, `asn`, `isp`, `location: {city, country}`) and `"targets"` (`[{name, url, location}]`), plus optional support for legacy v1 list payloads (`[{"url": ...}]`).
   - **CRITICAL Encoding Gotcha (Verified Live):** Despite `Content-Type: application/json`, Netflix's v2 endpoint can return Latin-1 encoded city/location bytes (e.g., byte `0xe1` for `á`) that crash strict `.decode("utf-8")` with `UnicodeDecodeError`. Always decode raw response bytes using UTF-8 with `latin-1` fallback before `json.loads`.

4. **HTTP Unloaded & Loaded Latency (No ICMP / No Root Privileges):**
   - Rewrite target URL path trailing `/speedtest` (or `/speedtest/range/...`) to `/speedtest/range/0-0` using `urllib.parse.urlsplit`/`urlunsplit`, preserving all query parameters (`c=...`, `n=...`, `tok=...`).
   - Send 1 keep-alive warmup `GET /speedtest/range/0-0` so TCP+TLS handshake overhead does not inflate RTT, then measure `count` sequential `GET /speedtest/range/0-0` requests (`HTTP 200`, 1-byte body; empirically ~3–4 ms on fiber).
   - Measure **loaded latency** via an async probe coroutine running concurrently during `measure_download` after a per-run local `download_started: asyncio.Event` fires (never a module-level global).

5. **Download & Upload Engines with Dynamic Scaling & Leak-Free Cancellation:**
   - **Download:** Parallel `asyncio.Task` workers (`connections_min=1` scaling dynamically `1 -> 3 -> 5 -> connections_max=8` based on moving-window speed thresholds `>1 Mbps`, `>10 Mbps`, `>50 Mbps`) streaming `128 KiB` chunks until `stop_event` is set. Peak speed is calculated over a sliding window (default 3 snapshots of ~0.5s each).
   - **Upload:** `POST` to `/speedtest/range/0-0` (`HTTP 200` verified live) with `Content-Type: application/octet-stream`, streaming chunks from a **single pre-allocated reusable buffer** (`bytes(chunk_size)`, e.g., `256 KiB` up to `4 MiB` per request) via an async generator so there is **zero `os.urandom()` CPU bottleneck**. Same dynamic parallel worker scaling and sliding-window speed tracking.
   - **Cleanup Guarantee:** Both download and upload wrap worker + latency probe orchestration in `try ... finally` that sets `stop_event`, cancels every worker/probe task, and awaits `asyncio.gather(*tasks, return_exceptions=True)` so zero tasks or open HTTP streams leak between phases or runs.

6. **Typed Models & Errors (No Silent `0` Swallowing):**
   - Frozen slotted dataclasses (`FastLocation`, `FastClientInfo`, `FastTarget`, `FastSpeedtestResult`).
   - Explicit exception hierarchy: `FastDotComError` → `FastDotComConnectionError`, `FastDotComTokenError`, `FastDotComTimeoutError`.

---

## 3. Target Repository Architecture

```text
fastdotcom-ng/
├── fastdotcom/
│   ├── __init__.py       # Public exports, async_fast_com, drop-in sync fast_com wrapper
│   ├── const.py          # Endpoints, default timings, chunk sizes, connection bounds
│   ├── exceptions.py     # FastDotComError hierarchy
│   ├── models.py         # Frozen dataclasses (FastSpeedtestResult, FastTarget, FastClientInfo, FastLocation)
│   ├── client.py         # FastDotComClient (session lifecycle, token, v2 targets, latency, download, upload)
│   ├── cli.py            # CLI entrypoint (`fastdotcom` console script with --json, --no-upload, etc.)
│   └── py.typed          # PEP 561 typed package marker
├── tests/
│   ├── conftest.py       # Offline aiohttp mock fixtures & sample v2 (including Latin-1) payloads
│   ├── test_client.py    # Unit tests: token, v2 decoding, latency, download, upload, cancellation, IPv4/6, fast_com
│   ├── test_cli.py       # CLI tests (human output, JSON output, error exit codes)
│   └── test_real_api_calls.py  # Marked `real_api_call` (deselected by default)
├── .github/workflows/
│   ├── main.yml          # CI: ruff, mypy, pytest (>=95% branch cov), uv build across Python 3.11-3.15
│   ├── publish.yml       # Release-triggered PyPI publish via OIDC Trusted Publishing + PEP 740 attestations
│   └── live_api.yml      # Weekly cron + workflow_dispatch live fast.com smoke test
├── pyproject.toml        # PEP 621 / 639 / 735 metadata, hatchling backend, ruff, pytest, coverage, mypy
├── uv.lock               # Reproducible uv lockfile
├── .pre-commit-config.yaml
├── LICENSE               # MIT License (Marco Sousa)
├── README.md
└── CHANGELOG.md
```

---

## 4. Home Assistant Compatibility Invariants (Must Not Break)

- **Drop-In Sync Contract (for HA Core PR 1):**
  - `from fastdotcom import fast_com` must work cleanly in HA's executor (`hass.async_add_executor_job(fast_com)`) and accept legacy keyword parameters (`verbose`, `max_time`, `ping_count`, `force_ipv4`, `force_ipv6`, `payload_size`, `max_payload_size`).
  - `fast_com()` / `FastSpeedtestResult.to_dict()` returns:
    ```python
    {
        "download_speed": float,  # Mbps rounded to 2 decimals
        "upload_speed": float,  # Mbps rounded to 2 decimals
        "unloaded_ping": float,  # ms rounded to 2 decimals
        "loaded_ping": float,  # ms rounded to 2 decimals
        "success": 1,
    }
    ```
  - On network/API/timeout errors, raise `FastDotComError` instead of silently returning `0` — HA's `FastdotcomDataUpdateCoordinator._async_update_data` catches `Exception` and converts it to `UpdateFailed`, eliminating fake `0 Mbps` drops in HA history.
- **Native Async Contract (for HA Core PR 2):**
  - `FastDotComClient(session=...)` and `async_fast_com(session=...)` accept an external `aiohttp.ClientSession` (HA's `async_get_clientsession(hass)`).
  - **Session Ownership Rule:** **NEVER** close an externally injected `session` in `close()` or `__aexit__()`; only close sessions created internally by `FastDotComClient`.
  - Support selective flags (`measure_download`, `measure_upload`, `measure_latency`) so HA can expose **Download**, **Upload**, **Unloaded Latency**, and **Loaded Latency** sensors with optional bandwidth-saving toggles.
- **2-PR Home Assistant Core Strategy:**
  - **PR 1:** Minimal dependency bump only (`homeassistant/components/fastdotcom/manifest.json`, `requirements_all.txt`, `requirements_test_all.txt`, and `package_constraints.txt` if needed). Audit `git diff` to ensure no unrelated lines change.
  - **PR 2 (only after PR 1 merges):** Migrate `fastdotcom` coordinator to native async `async_fast_com` and add Upload + Unloaded/Loaded Latency sensors, options flow, etc.

---

## 5. Development, Testing, CI/CD & Release Guidelines

- **Toolchain (`uv` + `hatchling`):**
  - Use `uv lock`, `uv sync --all-groups`, `uv run ...`, and `uv build`. Never use `poetry`, `pip`, or `pytest-sugar` (`pytest-sugar` crashes under `pytest 9.x`).
  - Keep dependency lower bounds conservative (`aiohttp>=3.10.0`) rather than pinning cutting-edge minimums.
- **Quality Gates:**
  - `uv run ruff check --no-fix .` and `uv run ruff format --check .` (line length `88`, strict lint rule set including `ASYNC`, `B`, `C4`, `I`, `PTH`, `RUF`, `SIM`, `TCH`).
  - `uv run mypy fastdotcom tests` (`check_untyped_defs = true` for `fastdotcom.*`).
  - `uv run pytest` runs offline by default (`-m 'not real_api_call'`), treats all warnings as errors (`filterwarnings = ["error"]`), and enforces **>= 95% branch coverage** (`branch = true`, `fail_under = 95`).
  - `uv run pytest -m real_api_call --no-cov` validates live `fast.com` endpoints manually and in `.github/workflows/live_api.yml`.
- **GitHub Actions:**
  - Use `actions/checkout@v7` and **pin `astral-sh/setup-uv` to an exact semver tag** (e.g., `astral-sh/setup-uv@v10.4.0` — never a floating major tag like `@v10`, which fails tag resolution).
  - Matrix test `python-version: ["3.11", "3.12", "3.13", "3.14", "3.15"]`.
  - Gate PyPI publishing strictly on `release: types: [published]` + `workflow_dispatch` using OIDC Trusted Publishing (`permissions: id-token: write`, `environment: pypi`, `pypa/gh-action-pypi-publish@release/v1` with `attestations: true`).
  - **PyPI Immutable Filenames:** PyPI permanently rejects re-uploading any deleted version filename — always bump the patch version before retrying.
- **README & Badges:**
  - Include GitHub Actions CI, PyPI, Python versions, and PePy downloads badge (`[![Downloads](https://static.pepy.tech/badge/fastdotcom-ng)](https://pepy.tech/projects/fastdotcom-ng)`).
- **Git Conventions:**
  - Commit as `Marco Sousa <marcomsousa@gmail.com>` under GitHub user `marcomsousa`.
  - Use clean, atomic Conventional Commits (`feat(...)`, `fix(...)`, `refactor(...)`, `test(...)`, `ci(...)`, `docs(...)`, `chore(...)`).
