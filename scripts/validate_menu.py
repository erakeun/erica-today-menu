#!/usr/bin/env python3
"""Fail closed on an invalid or non-current deploy artifact."""
import json
from pathlib import Path
try:
    from .artifact import validate
except ImportError:
    from artifact import validate


def main():
    payload = json.loads((Path(__file__).resolve().parents[1] / "dist/menu.json").read_text())
    validate(payload, require_today=True)
    print(f"배포 검증 성공: date={payload['date']} restaurants={len(payload['restaurants'])}")


if __name__ == "__main__":
    main()
