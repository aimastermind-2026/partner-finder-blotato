---
name: find-partners
description: Run the Blotato partner finder end to end - fetch YouTube data, tier and score creators, draft invites for the top 10 per tier, check them, and summarise. Use when asked to find partners, run the partner pipeline, or refresh partners.csv. Never sends anything.
---

# Find partners

Runs the whole pipeline in `/Users/crypto/partner-finder` and ends with a short summary.
**Never send, post, email or contact anyone.** Every invite is a draft for a person to review.
Don't collect or guess email addresses. Never print or commit the API key in `.env`.

## 1. Fetch and score

Work from `/Users/crypto/partner-finder`. Run each command **on its own**, exactly as written: use
the venv's Python directly, with no `source`/activate and no `&&` chains. That's what the weekly
headless run allows.

```bash
.venv/bin/python -m pytest -q     # stop and report if tests fail
.venv/bin/python fetch.py         # 9 searches max; same-day re-runs use the cache (0 units)
.venv/bin/python score.py         # writes output/partners.csv, output/to_draft.json, output/run_log.json
```

If `.venv` is missing, run `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`.
If `fetch.py` stops on quota, report it and stop. Don't retry.

## 2. Draft the invites (you write these, no API call)

Read `output/to_draft.json` (top 10 per tier). For more context on a channel, read its uploads in
`data/channels.json`. Write a **fresh** `output/drafts.json`, replacing last run's file:

```json
[{"channel_id": "UC...", "tier": 1, "attempt": 1, "invite": "..."}]
```

Each invite:
- is 80 words or fewer, with no emojis and no hype words (revolutionary, game-changer, game changing,
  unlock, skyrocket, ultimate, insane, crushing). Avoid quoting a title that contains one of these.
- names one video they really made, with its title **quoted exactly in straight double quotes**,
  and says something true about it, based on its title or description. Don't invent details.
  Tier 1: a Blotato video. Tier 2: their best topic video. `best_video_title` is a default, so pick another if it fits better.
- **Tier 1:** one line on the partner programme: 50% of each referred customer's first payment.
  Most Tier 1 creators already use a `blotato.com/?ref=` link. Acknowledge that rather than pitching cold.
- **Tier 2:** offers a free Blotato account and a ready-made workflow that fits what they already
  teach. The partner programme (50% of referred customers' first payment) is a second line.
- ends with a soft question, not a hard sell. Sign off `– [Your name], Blotato`.

## 3. Check, re-draft once, merge

```bash
.venv/bin/python checks.py
```

For each FAIL, rewrite that invite once to fix the listed notes, set `"attempt": 2`, and run
`.venv/bin/python checks.py` again. Don't rewrite a second time. Anything still failing stays as
`failed check – rewrite` with its `check_notes`.

## 4. Summarise

Report briefly:
- quota units used, and channels found / passed / dropped per tier with the top drop reasons
  (from the script output or `output/run_log.json`)
- the top 10 per tier as a short table: channel, subscribers, score, partner type, video named
- the check total (passed / failed after re-draft) and anything you noticed that a reviewer should
  know, such as duplicate people across channels or weak fits
- where the results are: `output/partners.csv` (status `draft – needs approval`)

Don't commit `output/` or `data/`. They're gitignored.
