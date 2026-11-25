"""Deliver a rendered episode.

mode none : nothing (the GitHub Actions run keeps the files as a downloadable artifact)
mode api  : YouTube Data API v3 with the channel owner's OAuth refresh token
            (secrets YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN). An unaudited Google Cloud project
            can only upload PRIVATE videos; request the free audit to post public automatically.
mode make : POST the file URLs to a Make.com webhook (MAKE_WEBHOOK_URL) whose YouTube module uploads them.

python -m oaf.upload --episode ep01-hyatt-regency [--base-url https://.../releases/download/ep01/]
"""
from __future__ import annotations

import argparse
import json

import requests

from .common import OUT, env, load_config, load_episode, log


def yt_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(None, refresh_token=env("YT_REFRESH_TOKEN"), client_id=env("YT_CLIENT_ID"),
                        client_secret=env("YT_CLIENT_SECRET"), token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload",
                                "https://www.googleapis.com/auth/youtube.force-ssl"])
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def api_upload(yt, path, title, description, tags, cfg) -> str:
    from googleapiclient.http import MediaFileUpload
    up = cfg["upload"]
    body = {"snippet": {"title": title[:100], "description": description[:4900], "tags": tags[:30],
                        "categoryId": up["category_id"], "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": up["privacy"], "selfDeclaredMadeForKids": up["made_for_kids"],
                       "containsSyntheticMedia": bool(up.get("ai_disclosure", True))}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            log(f"upload {int(status.progress() * 100)}%")
    return resp["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--base-url", default="", help="public folder URL of the files (mode make)")
    a = ap.parse_args()
    cfg = load_config()
    ep, _ = load_episode(a.episode)
    out = OUT / a.episode
    mode = cfg["upload"]["mode"]
    if mode == "none":
        log("upload mode is none: files stay in the run's artifact")
        return
    if mode == "make":
        # one webhook call per video; the scenario uploads it and sets the thumbnail when one is given
        url = env("MAKE_WEBHOOK_URL")
        up = cfg["upload"]
        calls = [{"kind": "long", "file": "long_upload.mp4" if (out / "long_upload.mp4").exists() else "long.mp4",
                  "title": ep["title"], "description": ep["description"], "thumb": "thumbnail.jpg"}]
        if (out / "short_en.mp4").exists():
            calls.append({"kind": "short", "file": "short_en.mp4", "title": ep["short"]["title"], "thumb": "",
                          "description": f"{ep['short']['title']}\n\nFull documentary on the channel.\n\n"
                                         "#shorts #history #engineering"})
        for c in calls:
            payload = {"episode": a.episode, "kind": c["kind"], "title": c["title"][:100],
                       "description": c["description"][:4900], "tags": ",".join(ep["tags"])[:480],
                       "video_url": a.base_url + c["file"],
                       "thumbnail_url": a.base_url + c["thumb"] if c["thumb"] else "",
                       "privacy": up["privacy"], "category_id": up["category_id"]}
            r = requests.post(url, json=payload, timeout=60)
            log(f"Make webhook ({c['kind']}) answered {r.status_code}")
            r.raise_for_status()
        return
    yt = yt_client()
    vid = api_upload(yt, out / "long.mp4", ep["title"], ep["description"], ep["tags"], cfg)
    log(f"long video uploaded: https://youtu.be/{vid}")
    from googleapiclient.http import MediaFileUpload
    if (out / "thumbnail.jpg").exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(out / "thumbnail.jpg"))).execute()
        except Exception as e:
            log(f"thumbnail not set (channel may need phone verification): {e}")
    for lang, name in (("en", "English"), ("ar", "العربية")):
        srt = out / f"long_{lang}.srt"
        if srt.exists():
            yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": lang, "name": name}},
                                 media_body=MediaFileUpload(str(srt))).execute()
    short_desc = f"{ep['short']['title']}\n\nFull story: https://youtu.be/{vid}\n\n#shorts #history #engineering"
    sid = api_upload(yt, out / "short_en.mp4", ep["short"]["title"], short_desc, ep["tags"][:10], cfg)
    log(f"short uploaded: https://youtu.be/{sid}  (set its Related Video to the long one in Studio)")
    (out / "uploaded.json").write_text(json.dumps({"long": vid, "short": sid}), encoding="utf-8")


if __name__ == "__main__":
    main()
