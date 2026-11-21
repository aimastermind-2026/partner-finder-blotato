"""Unit tests on made-up channel data. No API calls."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetch  # noqa: E402
import score  # noqa: E402

TODAY = dt.date(2026, 11, 21)


def video(vid, title, days_ago, description=""):
    when = (TODAY - dt.timedelta(days=days_ago)).isoformat() + "T12:00:00Z"
    return {"video_id": vid, "title": title, "description": description, "published_at": when}


def channel(cid="UC1", name="Test Channel", subs=5000, uploads=(), found_by=("tier1",)):
    return {"channel_id": cid, "channel_name": name, "description": "", "custom_url": "",
            "subscribers": subs, "uploads": list(uploads), "found_by": list(found_by),
            "queries": []}


def test_tier1_blotato_videos_30_days_apart_dropped():
    ch = channel(uploads=[video("a", "Blotato tutorial", 10), video("b", "Blotato with n8n", 40)])
    tier, vids, reason = score.filter_channel(ch)
    assert tier == 1 and len(vids) == 2
    assert reason is not None and "days apart" in reason


def test_tier1_blotato_videos_120_days_apart_kept():
    ch = channel(uploads=[video("a", "Blotato tutorial", 10), video("b", "Blotato with n8n", 130)])
    assert score.filter_channel(ch)[2] is None


def test_any_blotato_video_makes_tier1_even_if_found_by_tier2_search():
    ch = channel(found_by=("tier2",), uploads=[
        video("a", "n8n social media automation", 5),
        video("b", "Make.com auto post", 50, description="I use Blotato for posting"),
    ])
    assert score.assign_tier(ch) == 1
    assert score.filter_channel(ch)[0] == 1


def test_tier2_under_1000_subscribers_dropped():
    ch = channel(subs=999, found_by=("tier2",), uploads=[
        video("a", "n8n automation", 5), video("b", "Zapier scheduling", 60),
        video("c", "Make.com tutorial", 150)])
    tier, _, reason = score.filter_channel(ch)
    assert tier == 2 and reason == "under 1,000 subscribers"


def test_tier2_with_enough_spread_topic_videos_kept():
    ch = channel(subs=1000, found_by=("tier2",), uploads=[
        video("a", "n8n automation", 5), video("b", "Zapier scheduling", 60),
        video("c", "Make.com tutorial", 150)])
    assert score.filter_channel(ch)[2] is None


def test_audience_full_marks_at_100k_and_recency_zero_at_400_days():
    assert score.audience_score(100_000) == 30
    assert score.audience_score(2_000_000) == 30
    assert score.recency_score(TODAY - dt.timedelta(days=400), TODAY) == 0


def test_audience_log_scale_anchors():
    assert score.audience_score(1_000) == 10
    assert score.audience_score(10_000) == 20


def test_same_channel_from_two_searches_appears_once():
    hit = {"items": [{"snippet": {"channelId": "UC1"}}]}
    found = fetch.channels_from_searches([("tier1", "Blotato", hit), ("tier2", "n8n social media automation", hit)])
    assert list(found) == ["UC1"]
    assert found["UC1"]["found_by"] == ["tier1", "tier2"]

    # And the scoring step dedupes rows by channel ID too.
    ch = channel(uploads=[video("a", "Blotato tutorial", 10), video("b", "Blotato with n8n", 130)])
    rows, _ = score.build_rows([ch, dict(ch, found_by=["tier2"])], TODAY)
    assert [r["channel_id"] for r in rows] == ["UC1"]
