"""Invite eval: check every drafted invite, then merge drafts into output/partners.csv.

Run:  python checks.py
Reads output/drafts.json (written by Claude), data/channels.json (cached uploads)
and output/partners.csv. Plain code, no API calls, no AI.

drafts.json format: [{"channel_id": "...", "tier": 1, "invite": "...", "attempt": 1}, ...]
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "output"
sys.path.insert(0, str(ROOT))
from score import CSV_COLUMNS  # noqa: E402

MAX_WORDS = 80
HYPE = ["revolutionary", "game changer", "game changing", "unlock", "skyrocket",
        "ultimate", "insane", "crushing"]
EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                   "\U00002B00-\U00002BFF️‍]")
QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')
STATUS_OK = "draft – needs approval"
STATUS_FAIL = "failed check – rewrite"


def normalise(s):
    """Lower-case, drop punctuation and symbols, collapse spaces."""
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return " ".join(s.replace("_", " ").split())


def named_title(invite, upload_titles):
    """Return the upload title the invite quotes, or None."""
    titles = {normalise(t): t for t in upload_titles}
    for a, b in QUOTED.findall(invite):
        if normalise(a or b) in titles:
            return titles[normalise(a or b)]
    return None


def check_invite(invite, tier, upload_titles):
    """Return a list of failure notes (empty list = pass)."""
    notes = []
    words = len(invite.split())
    if words > MAX_WORDS:
        notes.append(f"{words} words (max {MAX_WORDS})")
    if EMOJI.search(invite):
        notes.append("contains an emoji")
    flat = re.sub(r"[-–—]", " ", invite.lower())
    hype = [w for w in HYPE if re.search(r"\b" + w, flat)]
    if hype:
        notes.append("hype words: " + ", ".join(hype))
    quoted = [a or b for a, b in QUOTED.findall(invite)]
    if not quoted:
        notes.append("no video title in quotes")
    elif not named_title(invite, upload_titles):
        notes.append("quoted title not found in channel's uploads: " + "; ".join(quoted))
    if tier == 1 and not re.search(r"50\s?%|50 percent|fifty percent", invite, re.I):
        notes.append("Tier 1 invite doesn't mention the 50% commission")
    if tier == 2 and not re.search(r"free\b[\w\s]{0,20}\baccount", invite, re.I):
        notes.append("Tier 2 invite doesn't mention the free account")
    return notes


def main():
    drafts = json.loads((OUT / "drafts.json").read_text())
    channels = {c["channel_id"]: c for c in json.loads((ROOT / "data" / "channels.json").read_text())["channels"]}
    with open(OUT / "partners.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_id = {r["channel_id"]: r for r in rows}

    passed = 0
    results = []
    for d in drafts:
        ch = channels.get(d["channel_id"], {})
        notes = check_invite(d["invite"], int(d["tier"]), [v["title"] for v in ch.get("uploads", [])])
        ok = not notes
        passed += ok
        name = ch.get("channel_name", d["channel_id"])
        print(f"{'PASS' if ok else 'FAIL'}  T{d['tier']}  {name}  ({len(d['invite'].split())} words)"
              + ("" if ok else "  -> " + " | ".join(notes)))
        results.append({"channel_id": d["channel_id"], "tier": d["tier"], "passed": ok,
                        "notes": notes, "attempt": d.get("attempt", 1)})
        row = by_id.get(d["channel_id"])
        if row:
            # Keep the CSV's best video in sync with the video the invite names.
            title = named_title(d["invite"], [v["title"] for v in ch.get("uploads", [])])
            if title:
                vid = next(v for v in ch["uploads"] if v["title"] == title)
                row["best_video_title"] = title
                row["best_video_url"] = f"https://www.youtube.com/watch?v={vid['video_id']}"
            row["invite_draft"] = d["invite"]
            row["status"] = STATUS_OK if ok else STATUS_FAIL
            row["check_notes"] = "" if ok else "; ".join(notes)

    with open(OUT / "partners.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    (OUT / "check_results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(f"\nTotal: {passed}/{len(drafts)} passed, {len(drafts) - passed} failed")
    print("Merged into output/partners.csv; details in output/check_results.json")


if __name__ == "__main__":
    main()
