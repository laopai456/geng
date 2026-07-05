# src/geng/__main__.py
"""CLI 入口: geng [date]"""
import sys
import logging
from .pipeline import run_daily

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    date = sys.argv[1] if len(sys.argv) > 1 else None
    n = run_daily(date=date)
    print(f"完成: 入库 {n} 条")
    return 0

if __name__ == "__main__":
    sys.exit(main())
