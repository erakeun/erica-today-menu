#!/usr/bin/env python3
"""Deploy UI with the live last-good data; never fetch school or use a snapshot."""
import json
import time
import urllib.request
from pathlib import Path
from artifact import validate

URL = "https://erakeun.github.io/erica-today-menu/menu.json"
OUTPUT = Path(__file__).resolve().parents[1] / "dist" / "menu.json"


def main():
    request = urllib.request.Request(URL, headers={"Cache-Control": "no-cache"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read()
                print(f"Preserve live data: status={response.status} url={response.geturl()} bytes={len(body)}")
            payload = validate(json.loads(body))
            break
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise
            print(f"Live artifact retry: {type(exc).__name__}: {exc}")
            time.sleep(2 ** attempt)
    OUTPUT.write_bytes(body)
    print(f"Preserved date={payload['date']} generated_at={payload['generated_at']}")


if __name__ == "__main__":
    main()

