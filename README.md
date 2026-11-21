# Partner finder

Finds YouTube creators who could partner with Blotato, scores them, and drafts a personal invite for
the top 10 in each tier. **Nothing is ever sent.** Every invite is a draft for a person to review.

- **Tier 1, Blotato users:** creators who have made Blotato content for 3+ months
  (2+ Blotato videos, first and latest at least 90 days apart).
- **Tier 2, adjacent creators:** creators with 1,000+ subscribers who regularly teach social media
  automation (3+ topic videos in their latest 50 uploads, spread over 90+ days) but haven't made a
  Blotato video. Any Blotato video makes a channel Tier 1.

Output: `output/partners.csv` with tier, channel, subscribers, video dates, best video, partner type
(Agency / Automation builder / Creator), score (0–100), invite draft, status and check notes.

## How it works

| Step | File | What it does |
|---|---|---|
| Fetch | `fetch.py` | 9 YouTube searches (50 results each), `channels.list` for subscribers, and each channel's uploads playlist (50 uploads for Tier 2, up to 200 for Tier 1). Raw responses are cached in `data/raw/` for the day, so re-runs cost no quota. About 1,300 of the 10,000 free daily units per run. |
| Score | `score.py` | Tiers, filters and scores channels with plain rules. Writes `output/partners.csv`, the top 10 per tier to `output/to_draft.json`, and per-channel drop reasons to `output/run_log.json`. |
| Draft | Claude Code | The `find-partners` skill has Claude write `output/drafts.json` itself. No Anthropic API key or API call. |
| Check | `checks.py` | Checks every invite (80 words max, no emojis or hype words, quotes a video title that really exists in the channel's cached uploads, Tier 1 mentions the 50% commission, Tier 2 the free account). Merges drafts into the CSV. Failed invites are re-drafted once, then left as `failed check – rewrite`. |

Scoring (each tier ranked separately): Audience 30 (log scale: 1k ≈ 10, 10k ≈ 20, 100k+ = 30),
Consistency 25 (2 relevant videos = 10, 5+ = 25), Recency 25 (≤30 days = 25, ≤90 = 15, ≤180 = 5),
Teaching 10 (tutorial / how to / step by step / guide in a title), Depth 10 (n8n, Make, Zapier, API
or automation).

Excluded on purpose (edit `EXCLUDE_EXACT` in `score.py` to change): channels with "Blotato" in the
name, Blotato's founder, and the official n8n, Make and VEED channels.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
echo 'YOUTUBE_API_KEY=your-key-here' > .env
```

Get a key in Google Cloud Console: APIs & Services → enable **YouTube Data API v3** → Credentials →
Create API key. `.env`, `data/` and `output/` are gitignored. Never commit the key.

## Run it

In Claude Code, from this folder:

```
/find-partners
```

That runs the tests, fetch, scoring, invite drafting, checks and a summary. To run only the
non-AI steps by hand:

```bash
. .venv/bin/activate
python -m pytest -q
python fetch.py
python score.py
# write output/drafts.json (Claude does this in the skill), then:
python checks.py
```

## Weekly schedule

A launchd agent runs the skill headless every Monday at 08:00 through `scheduling/run_weekly.sh`.
It runs on this Mac only: if the Mac is asleep it runs on wake, and if it's off it skips. The run
can use only local Python and files in `output/`, with claude.ai connectors switched off, so it
can't contact anyone. Logs go to `output/weekly.log`.

```bash
# install / reinstall
cp scheduling/com.blotato.partner-finder.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.blotato.partner-finder.plist
# run now
launchctl kickstart gui/$(id -u)/com.blotato.partner-finder
# remove
launchctl bootout gui/$(id -u)/com.blotato.partner-finder
```

## Rules

- Never send, post or contact anyone. A person approves every invite.
- Public channel data only. No email addresses are collected or guessed.
- Stay within the free quota. Searches are capped at 10 per run (100 units each); this uses 9.

## Next steps (not built)

- More sources: n8n and Make template libraries, Medium.
- Blotato's own customer usage data for Tier 1, instead of inferring use from YouTube.
- Write results to the partner database through MCP.
- Feed inbound partner enquiries into the same table.
- A pipeline dashboard.
