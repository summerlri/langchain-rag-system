"""验证质量门禁标记是否新鲜并对应当前暂存差异。"""

from __future__ import annotations

import hashlib
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


MAX_AGE_SECONDS = 30 * 60


def staged_diff_hash() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def validate(path: Path, expected_hash: str) -> tuple[bool, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "pass":
            return False, "status 不是 pass"
        if data.get("staged_diff_hash") != expected_hash:
            return False, "暂存内容已变化"
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
        if age < 0 or age > MAX_AGE_SECONDS:
            return False, "标记已过期"
        return True, "有效"
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-hash", action="store_true")
    args = parser.parse_args()
    expected_hash = staged_diff_hash()
    if args.print_hash:
        print(expected_hash)
        return 0
    failures = 0
    for name in ("test.pass", "quality.pass"):
        ok, message = validate(Path(".claude/pass") / name, expected_hash)
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {message}")
        failures += int(not ok)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
