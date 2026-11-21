"""Tests for the invite eval in checks.py. No API calls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import checks  # noqa: E402

TITLES = ["Blotato + n8n: Auto Post Everywhere (Step by Step)", "My Studio Tour"]
GOOD_T1 = ('Hi Sam, "blotato n8n auto post everywhere step by step" was clear. '
           "Our partner programme pays 50% of each referred customer's first payment. Open to a chat?")
GOOD_T2 = ('Hi Sam, "My Studio Tour" was fun. We would like to offer you a free Blotato account '
           "and a workflow. Would that help?")


def test_good_invites_pass():
    assert checks.check_invite(GOOD_T1, 1, TITLES) == []
    assert checks.check_invite(GOOD_T2, 2, TITLES) == []


def test_made_up_video_title_fails():
    notes = checks.check_invite(GOOD_T1.replace("blotato n8n auto post everywhere step by step",
                                                "A Video I Never Made"), 1, TITLES)
    assert any("not found" in n for n in notes)


def test_too_long_emoji_and_hype_fail():
    long = GOOD_T2 + " word" * 80
    assert any("words" in n for n in checks.check_invite(long, 2, TITLES))
    assert any("emoji" in n for n in checks.check_invite(GOOD_T2 + " 🚀", 2, TITLES))
    assert any("hype" in n for n in checks.check_invite(GOOD_T2 + " A game-changer.", 2, TITLES))


def test_tier_specific_offer_required():
    assert any("50%" in n for n in checks.check_invite(GOOD_T2, 1, TITLES))
    assert any("free account" in n for n in checks.check_invite(GOOD_T1, 2, TITLES))
