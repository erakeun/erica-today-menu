"""Scheduled entry point: expected source failures skip publishing, bugs fail CI."""
import os
from pathlib import Path

try:
    from .fetch_menu import main, SourceUnavailable
except ImportError:
    from fetch_menu import main, SourceUnavailable


def run():
    try:
        main()
    except SourceUnavailable as exc:
        refreshed = False
        message = f"원본 조회/데이터 검증 실패로 배포를 건너뛰었습니다. 마지막 정상 운영본은 유지됩니다.\n\n{type(exc).__name__}: {exc}"
        print(f"::warning::{type(exc).__name__}: {exc}")
    else:
        refreshed = True
        message = "오늘(KST) 메뉴 검증을 통과했습니다. 새 메뉴를 Pages에 배포합니다."
    print(message)
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"refreshed={str(refreshed).lower()}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
            summary.write("## 메뉴 갱신\n\n" + message + "\n")
    return refreshed


if __name__ == "__main__":
    run()
