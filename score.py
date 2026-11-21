"""Tier, filter and score channels; write output/partners.csv and output/to_draft.json.

Run:  python score.py
Reads data/channels.json (from fetch.py). Plain rules, no AI.
"""
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "channels.json"
OUT = ROOT / "output"

BLOTATO = re.compile(r"blotato", re.I)
# Tier 2 topic words. "Make" is matched as Make.com / Integromat / "Make scenario"
# so ordinary uses of the verb "make" don't count.
TOPIC = re.compile(
    r"\bn8n\b|make\.com|integromat|\bMake (?:scenario|automation)s?\b|\bzapier\b|automation"
    r"|auto[- ]?post|scheduling|repurpos", re.I)
TEACHING = re.compile(r"tutorial|how to|step by step|step-by-step|guide", re.I)
DEPTH = re.compile(r"\bn8n\b|make\.com|integromat|\bMake\b|\bzapier\b|\bAPI\b|automation", re.I)
AGENCY = re.compile(r"\bagency\b|\bagencies\b|\bclients?\b", re.I)
BUILDER = re.compile(r"\bn8n\b|make\.com|\bMake\b|\bzapier\b|\bAPI\b", re.I)

# Channels that aren't partner prospects. Edit these lists as needed.
# Any channel name containing "Blotato" is treated as Blotato's own/staff channel.
EXCLUDE_NAME = re.compile(r"blotato", re.I)
EXCLUDE_EXACT = {  # lower-cased channel name -> reason
    "sabrina ramonov 🍄": "Blotato's founder",
    "sabrina ramonov": "Blotato's founder",
    "n8n": "tool vendor's official channel",
    "make": "tool vendor's official channel",
    "veed studio": "tool vendor's official channel",
}

TOP_N = 10
CSV_COLUMNS = ["tier", "channel_id", "channel_name", "channel_url", "subscribers",
               "relevant_videos", "first_video_date", "latest_video_date", "best_video_title",
               "best_video_url", "partner_type", "score", "invite_draft", "status", "check_notes"]


def text(v):
    return f"{v.get('title', '')}\n{v.get('description', '')}"


def parse_date(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date()


def blotato_videos(ch):
    return [v for v in ch.get("uploads", []) if v.get("published_at") and BLOTATO.search(text(v))]


def topic_videos(ch):
    latest50 = sorted((v for v in ch.get("uploads", []) if v.get("published_at")),
                      key=lambda v: v["published_at"], reverse=True)[:50]
    return [v for v in latest50 if TOPIC.search(text(v))]


def assign_tier(ch):
    """Any Blotato video makes a channel Tier 1, whichever search found it."""
    return 1 if blotato_videos(ch) else 2


def span_days(videos):
    dates = [parse_date(v["published_at"]) for v in videos]
    return (max(dates) - min(dates)).days if dates else 0


def excluded(ch):
    name = ch.get("channel_name", "")
    if EXCLUDE_NAME.search(name):
        return "excluded: Blotato's own channel"
    reason = EXCLUDE_EXACT.get(name.strip().lower())
    return f"excluded: {reason}" if reason else None


def filter_channel(ch):
    """Return (tier, relevant_videos, drop_reason or None)."""
    tier = assign_tier(ch)
    if excluded(ch):
        return tier, [], excluded(ch)
    if tier == 1:
        vids = blotato_videos(ch)
        if len(vids) < 2:
            return tier, vids, "fewer than 2 Blotato videos"
        if span_days(vids) < 90:
            return tier, vids, f"Blotato videos only {span_days(vids)} days apart (<90)"
        return tier, vids, None
    vids = topic_videos(ch)
    if ch.get("subscribers", 0) < 1000:
        return tier, vids, "under 1,000 subscribers"
    if len(vids) < 3:
        return tier, vids, f"only {len(vids)} topic videos in latest 50 (<3)"
    if span_days(vids) < 90:
        return tier, vids, f"topic videos only {span_days(vids)} days apart (<90)"
    return tier, vids, None


def audience_score(subs):
    if subs < 100:
        return 0.0
    return round(min(30.0, 10 * math.log10(subs / 100)), 1)


def consistency_score(n):
    return float(min(25, max(0, 10 + 5 * (n - 2)))) if n >= 1 else 0.0


def recency_score(latest, today):
    age = (today - latest).days
    return 25 if age <= 30 else 15 if age <= 90 else 5 if age <= 180 else 0


def score_channel(ch, vids, today):
    latest = max(parse_date(v["published_at"]) for v in vids)
    parts = {
        "audience": audience_score(ch.get("subscribers", 0)),
        "consistency": consistency_score(len(vids)),
        "recency": recency_score(latest, today),
        "teaching": 10 if any(TEACHING.search(v["title"]) for v in vids) else 0,
        "depth": 10 if any(DEPTH.search(text(v)) for v in vids) else 0,
    }
    return round(sum(parts.values()), 1), parts


def partner_type(ch):
    desc = ch.get("description", "")
    if AGENCY.search(desc):
        return "Agency"
    if BUILDER.search(desc):
        return "Automation builder"
    return "Creator"


def best_video(vids, tier):
    """Pick the video an invite should name.

    Prefer the subject in the title (Blotato for Tier 1, a topic word for Tier 2),
    then a teaching-style title, then the most recent.
    """
    subject = BLOTATO if tier == 1 else TOPIC
    return max(vids, key=lambda v: (bool(subject.search(v["title"])),
                                    bool(TEACHING.search(v["title"])), v["published_at"]))


def dedupe(channels):
    seen = {}
    for ch in channels:
        cid = ch["channel_id"]
        if cid in seen:
            for k in ("found_by", "queries"):
                seen[cid][k] = sorted(set(seen[cid].get(k, [])) | set(ch.get(k, [])))
        else:
            seen[cid] = dict(ch)
    return list(seen.values())


def build_rows(channels, today):
    rows, log = [], {1: {"found": 0, "passed": 0, "dropped": []}, 2: {"found": 0, "passed": 0, "dropped": []}}
    for ch in dedupe(channels):
        tier, vids, reason = filter_channel(ch)
        log[tier]["found"] += 1
        if reason:
            log[tier]["dropped"].append({"channel": ch["channel_name"], "reason": reason})
            continue
        log[tier]["passed"] += 1
        score, parts = score_channel(ch, vids, today)
        best = best_video(vids, tier)
        dates = sorted(parse_date(v["published_at"]) for v in vids)
        url = (f"https://www.youtube.com/{ch['custom_url']}" if ch.get("custom_url")
               else f"https://www.youtube.com/channel/{ch['channel_id']}")
        rows.append({
            "tier": tier, "channel_id": ch["channel_id"], "channel_name": ch["channel_name"],
            "channel_url": url, "subscribers": ch.get("subscribers", 0),
            "relevant_videos": len(vids), "first_video_date": dates[0].isoformat(),
            "latest_video_date": dates[-1].isoformat(), "best_video_title": best["title"],
            "best_video_url": f"https://www.youtube.com/watch?v={best['video_id']}",
            "partner_type": partner_type(ch), "score": score, "invite_draft": "",
            "status": "", "check_notes": "", "_parts": parts, "_videos": vids,
            "_description": ch.get("description", ""),
        })
    rows.sort(key=lambda r: (r["tier"], -r["score"]))
    return rows, log


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def to_draft(rows):
    items = []
    for tier in (1, 2):
        for r in [r for r in rows if r["tier"] == tier][:TOP_N]:
            vids = sorted(r["_videos"], key=lambda v: v["published_at"], reverse=True)
            items.append({
                "tier": tier, "channel_id": r["channel_id"], "channel_name": r["channel_name"],
                "subscribers": r["subscribers"], "partner_type": r["partner_type"],
                "score": r["score"], "score_parts": r["_parts"],
                "channel_description": r["_description"][:500],
                "best_video_title": r["best_video_title"], "best_video_url": r["best_video_url"],
                "relevant_videos": [{"title": v["title"], "published_at": v["published_at"][:10],
                                     "description": v["description"][:400]} for v in vids[:8]],
            })
    return items


def main():
    data = json.loads(DATA.read_text())
    today = dt.date.today()
    rows, log = build_rows(data["channels"], today)
    OUT.mkdir(exist_ok=True)
    write_csv(rows, OUT / "partners.csv")
    (OUT / "to_draft.json").write_text(json.dumps(to_draft(rows), indent=1, ensure_ascii=False))
    (OUT / "run_log.json").write_text(json.dumps({"date": today.isoformat(), **{f"tier{t}": log[t] for t in log}},
                                                 indent=1, ensure_ascii=False))
    hidden = [c["channel_name"] for c in data["channels"] if c.get("hidden_subscribers")]
    for t in (1, 2):
        print(f"Tier {t}: {log[t]['found']} found, {log[t]['passed']} passed, {len(log[t]['dropped'])} dropped")
        reasons = {}
        for d in log[t]["dropped"]:
            key = re.sub(r"\d+ days", "N days", re.sub(r"only \d+ topic", "only N topic", d["reason"]))
            reasons[key] = reasons.get(key, 0) + 1
        for k, n in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"   {n:4d}  {k}")
    if hidden:
        print(f"Hidden subscriber counts (scored as 0): {', '.join(hidden)}")
    print("Per-channel drop reasons: output/run_log.json")
    print(f"Wrote output/partners.csv ({len(rows)} rows) and output/to_draft.json")


if __name__ == "__main__":
    main()
