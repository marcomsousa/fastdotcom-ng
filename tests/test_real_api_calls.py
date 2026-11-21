"""Live integration tests against real Fast.com endpoints (deselected by default)."""

from __future__ import annotations

import pytest

from fastdotcom import async_fast_com, fast_com


@pytest.mark.real_api_call
async def test_real_async_fast_com() -> None:
    """Run an end-to-end async speedtest against live fast.com."""
    result = await async_fast_com(min_time=3.0, max_time=8.0, ping_count=3)
    assert result.download_speed > 0
    assert result.upload_speed > 0
    assert result.unloaded_ping > 0
    assert result.loaded_ping > 0
    assert result.bytes_downloaded > 0
    assert result.bytes_uploaded > 0
    assert len(result.targets) >= 1


@pytest.mark.real_api_call
def test_real_sync_fast_com() -> None:
    """Run the drop-in synchronous fast_com wrapper against live fast.com."""
    metrics = fast_com(max_time=5.0, ping_count=3)
    assert metrics["success"] == 1
    assert metrics["download_speed"] > 0
    assert metrics["upload_speed"] > 0
    assert metrics["unloaded_ping"] > 0
    assert metrics["loaded_ping"] > 0
