# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-21

### Added
- Clean-room `asyncio` + `aiohttp` implementation of the Fast.com API v2 speedtest client (`FastDotComClient`, `async_fast_com`) under the MIT License.
- Single-call Fast.com API v2 target discovery (`get_targets`) with legacy v1 list fallback and UTF-8 / `latin-1` JSON decoding (`decode_json_bytes`).
- Rootless HTTP `/speedtest/range/0-0` latency measurements for unloaded and concurrent loaded latency (replacing ICMP sockets).
- Dynamically scaling parallel download and upload workers with sliding-window peak Mbps calculation, early stability termination, and leak-free task cancellation.
- Pre-allocated reusable upload buffer streaming with explicit `Content-Length` headers compatible with Netflix OCA servers.
- Frozen slotted dataclasses (`FastLocation`, `FastClientInfo`, `FastTarget`, `FastSpeedtestResult`) and typed exception hierarchy (`FastDotComError`, `FastDotComConnectionError`, `FastDotComTokenError`, `FastDotComTimeoutError`).
- Drop-in synchronous `fast_com(...)` facade compatible with Home Assistant Core's `fastdotcom` integration, safe across executor threads and active event loops.
- `fastdotcom` CLI entry point (`--max-time`, `--min-time`, `--ping-count`, `--no-download`, `--no-upload`, `--no-latency`, `--ipv4`, `--ipv6`, `--json`, `--verbose`).
- PEP 561 `py.typed` marker and offline, Home Assistant compatibility, CLI, and live API test suites.
