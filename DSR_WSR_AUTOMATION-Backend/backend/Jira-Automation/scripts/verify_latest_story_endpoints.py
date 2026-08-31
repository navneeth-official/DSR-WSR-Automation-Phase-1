"""Verify story list endpoints return only latest snapshot per jira_key."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

BASE = "http://127.0.0.1:8000"

EXPECTED_LATEST = {
    "LOC-2812": {"status": "Done", "snapshot_date": date.today().isoformat()},
    "COST-5502": {"status": "Done", "snapshot_date": date.today().isoformat()},
    "PRC-9901": {"status": "Done", "assignee": "Ananya Mehta", "snapshot_date": date.today().isoformat()},
    "SPUR-9902": {"status": "Done", "assignee": "Tom Alves", "snapshot_date": date.today().isoformat()},
}


def get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def assert_latest_only(label: str, data: dict, expect_keys: set[str] | None = None) -> None:
    stories = data["stories"]
    by_key: dict[str, list] = defaultdict(list)
    for s in stories:
        by_key[s["jira_key"]].append(s)

    dupes = {k: v for k, v in by_key.items() if len(v) > 1}
    if dupes:
        raise AssertionError(f"{label}: duplicate jira_keys in response: {list(dupes)}")

    if expect_keys is not None:
        found = {s["jira_key"] for s in stories}
        missing = expect_keys - found
        extra = found - expect_keys
        if missing:
            raise AssertionError(f"{label}: missing keys {missing}")
        if extra:
            raise AssertionError(f"{label}: unexpected keys {extra}")

    for key, expected in EXPECTED_LATEST.items():
        matches = [s for s in stories if s["jira_key"] == key]
        if not matches:
            continue
        row = matches[0]
        for field, value in expected.items():
            actual = row.get(field)
            if actual != value:
                raise AssertionError(
                    f"{label}: {key}.{field} expected {value!r}, got {actual!r}"
                )

    print(f"OK  {label} ({len(stories)} rows, latest-only verified)")


def main() -> int:
    try:
        all_stories = get("/api/stories")
        for key in EXPECTED_LATEST:
            assert any(s["jira_key"] == key for s in all_stories["stories"]), f"/api/stories missing {key}"
        assert_latest_only("GET /api/stories", all_stories)

        loc_track = get("/api/stories/track/1")
        assert_latest_only("GET /api/stories/track/1 (LOC)", loc_track)
        assert "LOC-2812" in {s["jira_key"] for s in loc_track["stories"]}

        cost_track = get("/api/stories/track/2")
        assert_latest_only("GET /api/stories/track/2 (COST)", cost_track)
        assert "COST-5502" in {s["jira_key"] for s in cost_track["stories"]}

        prc_track = get("/api/stories/track/8")
        assert_latest_only("GET /api/stories/track/8 (PRC)", prc_track)
        assert "PRC-9901" in {s["jira_key"] for s in prc_track["stories"]}

        ananya = get("/api/stories/assignee/" + urllib.parse.quote("Ananya Mehta"))
        assert_latest_only("GET /api/stories/assignee/Ananya Mehta", ananya, {"PRC-9901"})

        kevin = get("/api/stories/assignee/" + urllib.parse.quote("Kevin Loh"))
        if any(s["jira_key"] == "PRC-9901" for s in kevin["stories"]):
            raise AssertionError("Kevin Loh filter must not include PRC-9901 (latest assignee is Ananya)")
        print(f"OK  GET /api/stories/assignee/Kevin Loh (PRC-9901 excluded)")

        spur_sprint = get("/api/stories/sprint/14")
        assert_latest_only("GET /api/stories/sprint/14", spur_sprint)
        assert "SPUR-9902" in {s["jira_key"] for s in spur_sprint["stories"]}

        history = get("/api/stories/LOC-2812/history")
        if history["count"] != 3:
            raise AssertionError(f"LOC-2812 history expected 3 snapshots, got {history['count']}")
        print(f"OK  GET /api/stories/LOC-2812/history ({history['count']} snapshots)")

        print("\nAll endpoint checks passed.")
        return 0
    except urllib.error.URLError as exc:
        print(f"API not reachable at {BASE}: {exc}", file=sys.stderr)
        return 1
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
