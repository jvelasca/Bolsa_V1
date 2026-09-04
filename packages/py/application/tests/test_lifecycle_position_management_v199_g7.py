"""V1.99 Golden 7 — T2 crash/replay exactly-once (anchor on V1.97).

Does not reimplement atomicity. Certifies that the V1.97 crash mid-pair test
exists and is labeled as V1.99 Golden 7. Runtime coverage stays in:

  test_lifecycle_t2_atomicity_v197.test_crash_mid_pair_rolls_back_then_retry_exactly_once
  (+ PG lifecycle-pg crash tests)
"""

from __future__ import annotations

from pathlib import Path


def test_v199_g7_anchored_on_v197_crash_retry() -> None:
    anchor = Path(__file__).with_name("test_lifecycle_t2_atomicity_v197.py")
    assert anchor.is_file(), f"missing V1.97 anchor {anchor}"
    text = anchor.read_text(encoding="utf-8")
    assert "async def test_crash_mid_pair_rolls_back_then_retry_exactly_once" in text
    assert "V1.99 Golden 7" in text
    assert "exactly-once" in text or "exactly once" in text.lower()
