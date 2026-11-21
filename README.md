# fastdotcom-ng

[![CI](https://github.com/marcomsousa/fastdotcom-ng/actions/workflows/main.yml/badge.svg)](https://github.com/marcomsousa/fastdotcom-ng/actions/workflows/main.yml)
[![PyPI version](https://img.shields.io/pypi/v/fastdotcom-ng)](https://pypi.org/project/fastdotcom-ng/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastdotcom-ng)](https://pypi.org/project/fastdotcom-ng/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Downloads](https://static.pepy.tech/badge/fastdotcom-ng)](https://pepy.tech/projects/fastdotcom-ng)

A clean-room, modern `asyncio` + `aiohttp` Python library and CLI to measure Internet speed (download, upload, unloaded latency, and loaded latency) using Netflix's [Fast.com](https://fast.com/) API v2 — designed as a **100% drop-in compatible** replacement for `fastdotcom` in Home Assistant.

## Highlights

- **Pure `asyncio` + `aiohttp`**: Zero `requests`, `urllib.request`, `threading`, or `icmplib`.
- **Single API v2 Discovery Call**: Discovers client metadata and targets in one call, with UTF-8 + `latin-1` fallback decoding for non-UTF-8 city names.
- **Rootless HTTP Latency Probes**: Uses `GET /speedtest/range/0-0` keep-alive requests instead of ICMP raw sockets (works unprivileged inside containers and Home Assistant OS).
- **Dynamic Scaling & Clean Cancellation**: Dynamically scales parallel connections (`1 -> 3 -> 5 -> max`) with sliding-window speed tracking and guaranteed task cleanup.
- **Zero-Bottleneck Upload Streaming**: Streams a pre-allocated reusable buffer with explicit `Content-Length` (required by Netflix OCA endpoints) instead of calling `os.urandom()` per loop.
- **Home Assistant Drop-In & Native Async Ready**:
  - `from fastdotcom import fast_com` provides synchronous drop-in compatibility.
  - `async_fast_com(session=...)` and `FastDotComClient(session=...)` accept an external `aiohttp.ClientSession` without ever closing caller-owned sessions.
  - Typed exceptions (`FastDotComError`) replace silent `0` returns.
- **PEP 561 Typed**: Ships `py.typed` with strict `mypy` verification.

## Installation

```bash
uv add fastdotcom-ng
```

Or with `pip`:

```bash
pip install fastdotcom-ng
```

## Usage

### Native Async (Recommended)

```python
import asyncio
import aiohttp
from fastdotcom import async_fast_com


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        result = await async_fast_com(session=session)
        print(
            f"Download: {result.download_speed} Mbps | "
            f"Upload: {result.upload_speed} Mbps | "
            f"Unloaded: {result.unloaded_ping} ms | "
            f"Loaded: {result.loaded_ping} ms"
        )


asyncio.run(main())
```

### Reusable Client

```python
import asyncio
from fastdotcom import FastDotComClient


async def main() -> None:
    async with FastDotComClient() as client:
        result = await client.run_speedtest(max_time=10.0, ping_count=5)
        print(result.to_dict())


asyncio.run(main())
```

### Synchronous Drop-In (Home Assistant Compatible)

```python
from fastdotcom import fast_com

metrics = fast_com()
# {
#     "download_speed": 612.45,
#     "upload_speed": 318.92,
#     "unloaded_ping": 3.41,
#     "loaded_ping": 14.28,
#     "success": 1,
# }
```

### Command-Line Interface

```bash
fastdotcom
fastdotcom --json --max-time 10 --ping-count 5
fastdotcom --no-upload --ipv4
```

## Provenance & License

`fastdotcom-ng` is an independent, clean-room MIT implementation written from scratch by [Marco Sousa](https://github.com/marcomsousa) to replace the unmaintained legacy `fastdotcom` package ([`nkgilley/fast.com`](https://github.com/nkgilley/fast.com)) while preserving its public `fastdotcom` import namespace and Home Assistant dictionary contract.

Licensed under the [MIT License](LICENSE).
