"""Fetch YouTube data for the partner finder, caching every raw response.

Run:  python fetch.py
Writes data/channels.json (one record per channel) and data/raw/*.json (cache).
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "channels.json"
API = "https://www.googleapis.com/youtube/v3/"

TIER1_QUERIES = ["Blotato", "Blotato n8n", "Blotato make.com", "Blotato tutorial"]
TIER2_QUERIES = [
    "n8n social media automation",
    "make.com social media automation",
    "auto post to all social media",
    "AI content repurposing",
    "AI social media content workflow",
]
MAX_SEARCHES = 10
TIER1_PAGES = 4  # latest 200 uploads
TIER2_PAGES = 1  # latest 50 uploads
BLOTATO = re.compile(r"blotato", re.I)

COST = {"search": 100, "channels": 1, "playlistItems": 1}


class QuotaError(RuntimeError):
    pass


def load_key():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("YOUTUBE_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("YOUTUBE_API_KEY is not set in .env")
    return key


class Client:
    """YouTube API client with a same-day file cache. Never logs the key."""

    def __init__(self, key, today=None):
        self.key = key
        self.today = today or dt.date.today().isoformat()
        self.units = 0
        self.cache_hits = 0
        self.searches = 0

    def get(self, endpoint, params):
        # The cache key includes today's date so a weekly run gets fresh data
        # while same-day re-runs cost nothing.
        ident = json.dumps({"e": endpoint, "p": params, "d": self.today}, sort_keys=True)
        path = RAW / f"{endpoint}_{hashlib.sha1(ident.encode()).hexdigest()[:16]}.json"
        if path.exists():
            self.cache_hits += 1
            return json.loads(path.read_text())
        if endpoint == "search":
            if self.searches >= MAX_SEARCHES:
                raise QuotaError(f"search cap of {MAX_SEARCHES} per run reached")
            self.searches += 1
        resp = requests.get(API + endpoint, params={**params, "key": self.key}, timeout=30)
        if resp.status_code != 200:
            try:
                err = resp.json()["error"]
                reason = err.get("errors", [{}])[0].get("reason", "")
                msg = f"{resp.status_code} {reason}: {err.get('message', '')}"
            except Exception:
                msg = str(resp.status_code)
            if "quota" in msg.lower():
                raise QuotaError(msg)
            raise RuntimeError(f"{endpoint} failed: {msg}")  # URL (with key) is never shown
        self.units += COST[endpoint]
        data = resp.json()
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"request": {"endpoint": endpoint, "params": params}, "response": data}))
        return {"request": {"endpoint": endpoint, "params": params}, "response": data}


def months_ago(n, today=None):
    today = today or dt.date.today()
    return (today - dt.timedelta(days=round(n * 30.44))).isoformat() + "T00:00:00Z"


def channels_from_searches(search_results):
    """Merge search hits into one entry per channel ID.

    search_results: list of (tier, query, response_json).
    Returns {channel_id: {"found_by": [tiers], "queries": [queries]}}.
    """
    found = {}
    for tier, query, resp in search_results:
        for item in resp.get("items", []):
            cid = item.get("snippet", {}).get("channelId")
            if not cid:
                continue
            entry = found.setdefault(cid, {"found_by": [], "queries": []})
            if tier not in entry["found_by"]:
                entry["found_by"].append(tier)
            if query not in entry["queries"]:
                entry["queries"].append(query)
    return found


def read_uploads(client, playlist_id, pages):
    videos, token = [], None
    for _ in range(pages):
        params = {"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if token:
            params["pageToken"] = token
        try:
            resp = client.get("playlistItems", params)["response"]
        except RuntimeError as e:  # private/missing playlist: skip channel uploads
            print(f"  ! uploads unavailable for {playlist_id}: {e}")
            break
        for it in resp.get("items", []):
            sn, cd = it.get("snippet", {}), it.get("contentDetails", {})
            videos.append({
                "video_id": cd.get("videoId") or sn.get("resourceId", {}).get("videoId"),
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "published_at": cd.get("videoPublishedAt") or sn.get("publishedAt"),
            })
        token = resp.get("nextPageToken")
        if not token:
            break
    return videos


def main():
    client = Client(load_key())
    today = dt.date.today()
    results = []
    try:
        for tier, queries, months in (("tier1", TIER1_QUERIES, 24), ("tier2", TIER2_QUERIES, 12)):
            for q in queries:
                params = {"part": "snippet", "q": q, "type": "video", "maxResults": 50,
                          "publishedAfter": months_ago(months, today)}
                results.append((tier, q, client.get("search", params)["response"]))
    except QuotaError as e:
        sys.exit(f"Stopped: {e}")

    found = channels_from_searches(results)
    print(f"Searches: {len(results)}; unique channels: {len(found)}")

    # channels.list, 50 IDs per call
    ids = list(found)
    hidden = []
    channels = []
    for i in range(0, len(ids), 50):
        resp = client.get("channels", {"part": "snippet,statistics,contentDetails",
                                       "id": ",".join(ids[i:i + 50]), "maxResults": 50})["response"]
        for it in resp.get("items", []):
            st = it.get("statistics", {})
            if st.get("hiddenSubscriberCount"):
                subs = 0
                hidden.append(it["snippet"]["title"])
            else:
                subs = int(st.get("subscriberCount", 0))
            sn = it["snippet"]
            channels.append({
                "channel_id": it["id"],
                "channel_name": sn.get("title", ""),
                "description": sn.get("description", ""),
                "custom_url": sn.get("customUrl", ""),
                "subscribers": subs,
                "hidden_subscribers": bool(st.get("hiddenSubscriberCount")),
                "uploads_playlist": it.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
                **found[it["id"]],
            })
    for name in hidden:
        print(f"  hidden subscriber count, treated as 0: {name}")

    # Uploads: up to 200 for Tier 1 search hits, 50 for others (extended to 200
    # if the first page shows a Blotato video, since that makes them Tier 1).
    try:
        for n, ch in enumerate(channels, 1):
            if not ch["uploads_playlist"]:
                ch["uploads"] = []
                continue
            pages = TIER1_PAGES if "tier1" in ch["found_by"] else TIER2_PAGES
            vids = read_uploads(client, ch["uploads_playlist"], pages)
            if pages == TIER2_PAGES and len(vids) == 50 and any(
                    BLOTATO.search(v["title"] + " " + v["description"]) for v in vids):
                vids = read_uploads(client, ch["uploads_playlist"], TIER1_PAGES)
            ch["uploads"] = vids
            if n % 50 == 0:
                print(f"  uploads read for {n}/{len(channels)} channels")
    except QuotaError as e:
        sys.exit(f"Stopped: {e}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"fetched_on": client.today, "searches": len(results),
                               "channels": channels}, indent=1))
    print(f"Saved {len(channels)} channels to {OUT.relative_to(ROOT)}")
    print(f"Quota used this run: {client.units} units ({client.searches} searches); "
          f"cache hits: {client.cache_hits}")


if __name__ == "__main__":
    main()
