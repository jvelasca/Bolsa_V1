#!/usr/bin/env python3
"""Print warm-up audit matrix (Q0.3).

  python scripts/research/warmup_audit_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py" / "analytics" / "src"))

from bolsa_analytics.warmup_matrix import warmup_audit_rows  # noqa: E402


def main() -> int:
    print("=== WARM-UP AUDIT (Q0.3) ===")
    print(f"{'family':12} {'minBars':>8}  defaults")
    for row in warmup_audit_rows():
        print(
            f"{row['family']:12} {row['minBars']:>8}  {row['defaultParams']}"
            + (f"  # {row['notes']}" if row["notes"] else "")
        )
    print(
        "\nPolicy: OOS/grids must use IS warm-up (trade_from_index); "
        "see scripts/research/verify_oos_warmup.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
