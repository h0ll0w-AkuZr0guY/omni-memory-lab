import json
import sys
from collections import Counter
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/summarize_batch.py artifacts/progress.jsonl")
    path = Path(sys.argv[1])
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    statuses = Counter(record.get("status") for record in records)
    issues = Counter(
        code
        for record in records
        for code in record.get("issue_codes", [])
    )
    print(json.dumps({
        "record_count": len(records),
        "statuses": dict(statuses),
        "issue_codes": dict(issues),
        "committed_count": sum(record.get("committed_count", 0) for record in records),
        "candidate_count": sum(record.get("candidate_count", 0) for record in records),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
