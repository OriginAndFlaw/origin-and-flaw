"""Daily outlier research -> research/YYYY-MM-DD.md

- YouTube Data API v3 (YOUTUBE_API_KEY): recent uploads of competitor channels + a few searches;
  a video is an OUTLIER when views > subscribers x multiplier within the last N days.
- pytrends: rising queries for our keywords (worldwide and Arabic-speaking regions).
- youtube-transcript-api: the first 60 seconds (the hook) of each outlier.
Every source is optional: a failure is written into the report, never stops it.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import requests

from .common import ROOT, env, load_config, log

API = "https://www.googleapis.com/youtube/v3/"


def yt(endpoint: str, **params) -> dict:
    params["key"] = env("YOUTUBE_API_KEY")
    r = requests.get(API + endpoint, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def channel_stats(ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        for c in yt("channels", part="statistics,snippet,contentDetails", id=",".join(ids[i:i + 50]))["items"]:
            out[c["id"]] = {"title": c["snippet"]["title"],
                            "subs": int(c["statistics"].get("subscriberCount", 0) or 0),
                            "uploads": c["contentDetails"]["relatedPlaylists"]["uploads"]}
    return out


def video_stats(ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        for v in yt("videos", part="statistics,snippet,contentDetails", id=",".join(ids[i:i + 50]))["items"]:
            out.append({"id": v["id"], "title": v["snippet"]["title"], "channel": v["snippet"]["channelId"],
                        "published": v["snippet"]["publishedAt"][:10],
                        "views": int(v["statistics"].get("viewCount", 0) or 0),
                        "duration": v["contentDetails"]["duration"]})
    return out


def find_outliers(cfg: dict) -> tuple[list[dict], list[str]]:
    rc, notes = cfg["research"], []
    since = (dt.datetime.utcnow() - dt.timedelta(days=rc["days"])).isoformat("T") + "Z"
    vids: list[str] = []
    chans = list(rc.get("channels") or [])
    for q in rc["search_queries"]:
        try:
            res = yt("search", part="snippet", q=q, type="video", order="viewCount", publishedAfter=since,
                     maxResults=15, relevanceLanguage="en")
            for it in res["items"]:
                vids.append(it["id"]["videoId"])
                chans.append(it["snippet"]["channelId"])
        except Exception as e:
            notes.append(f"search '{q}' failed: {e}")
    stats = channel_stats(sorted(set(chans)))
    for cid in rc.get("channels") or []:
        if cid in stats:
            try:
                pl = yt("playlistItems", part="contentDetails", playlistId=stats[cid]["uploads"], maxResults=15)
                vids += [it["contentDetails"]["videoId"] for it in pl["items"]]
            except Exception as e:
                notes.append(f"uploads of {cid} failed: {e}")
    out = []
    cutoff = since[:10]
    for v in video_stats(sorted(set(vids))):
        ch = stats.get(v["channel"], {"subs": 0, "title": "?"})
        if v["published"] >= cutoff and ch["subs"] and v["views"] > ch["subs"] * rc["outlier_multiplier"]:
            v.update(channel_title=ch["title"], subs=ch["subs"], ratio=round(v["views"] / ch["subs"], 1))
            out.append(v)
    out.sort(key=lambda v: v["ratio"], reverse=True)
    return out[:15], notes


def hook_text(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        parts = api.fetch(video_id, languages=["en", "ar"])
        return " ".join(p.text for p in parts if p.start < 60)
    except Exception as e:
        return f"(no transcript: {type(e).__name__})"


def trends(cfg: dict) -> list[str]:
    lines = []
    try:
        from pytrends.request import TrendReq
        kws = cfg["research"]["trends_keywords"][:5]
        for geo, label in (("", "Worldwide"), ("SA", "Saudi Arabia"), ("EG", "Egypt"), ("US", "USA")):
            tr = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
            tr.build_payload(kws, timeframe="now 7-d", geo=geo)
            rel = tr.related_queries()
            rising = []
            for k in kws:
                df = (rel.get(k) or {}).get("rising")
                if df is not None and not df.empty:
                    rising += [f"{r['query']} (+{r['value']})" for _, r in df.head(3).iterrows()]
            lines.append(f"- **{label}**: " + (", ".join(rising) if rising else "nothing rising"))
    except Exception as e:
        lines.append(f"- pytrends unavailable today: {type(e).__name__} (Google often rate-limits cloud runners)")
    return lines


def main() -> None:
    cfg = load_config()
    today = dt.date.today().isoformat()
    rep = [f"# Research {today}", ""]
    if env("YOUTUBE_API_KEY"):
        outs, notes = find_outliers(cfg)
        rep += ["## Outlier videos (views > subscribers x %d, last %d days)" %
                (cfg["research"]["outlier_multiplier"], cfg["research"]["days"]), ""]
        if not outs:
            rep.append("None found today.")
        for v in outs:
            rep += [f"### {v['title']}",
                    f"{v['channel_title']} · {v['subs']:,} subs · {v['views']:,} views · **{v['ratio']}x** · "
                    f"{v['published']} · https://youtu.be/{v['id']}",
                    "", f"> Hook (first 60 s): {hook_text(v['id'])[:900]}", ""]
        rep += [f"- note: {n}" for n in notes]
    else:
        rep.append("YOUTUBE_API_KEY is not set: outlier scan skipped.")
    rep += ["", "## Search trends (7 days)", ""] + trends(cfg)
    dst = ROOT / "research" / f"{today}.md"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text("\n".join(rep) + "\n", encoding="utf-8")
    log(f"report written: {dst}")


if __name__ == "__main__":
    main()
