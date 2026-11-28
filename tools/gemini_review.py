"""Gemini draft review (owner's rule, 28 Nov): before a video is queued, Gemini watches the rendered draft with the
script beside it and lists every problem with its timestamp: picture not matching the words, a still held too long,
dead gaps, wrong spellings in captions, mispronounced names, facts that contradict each other.

    python tools/gemini_review.py <episode-id> [video]      (default video: out/<ep>/long.mp4)

Writes out/<ep>/gemini_review.json and prints the issues. Uses the Google AI Studio key the owner saved
(GEMINI_API_KEY or ~/.flow-mcp/gemini-key); the key is never printed. Free tier; bounded retries and timeouts."""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from oaf.tts import _gemini_key  # noqa: E402

API = "https://generativelanguage.googleapis.com"
MODEL = "gemini-flash-latest"  # 2.5-flash answered 404 on 28 Nov


def log(msg: str) -> None:
    print(f"[review] {msg}", flush=True)


def upload(path: Path, key: str) -> dict:
    size = path.stat().st_size
    r = requests.post(f"{API}/upload/v1beta/files", timeout=60, headers={
        "x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(size), "X-Goog-Upload-Header-Content-Type": "video/mp4",
        "Content-Type": "application/json"}, json={"file": {"display_name": path.name}})
    r.raise_for_status()
    url = r.headers["X-Goog-Upload-URL"]
    with open(path, "rb") as f:
        r = requests.post(url, data=f, timeout=900, headers={
            "Content-Length": str(size), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"})
    r.raise_for_status()
    info = r.json()["file"]
    for _ in range(90):  # wait until Google has processed the video (up to ~15 min)
        if info.get("state") == "ACTIVE":
            return info
        if info.get("state") == "FAILED":
            raise SystemExit("Gemini could not process the video")
        time.sleep(10)
        info = requests.get(f"{API}/v1beta/{info['name']}", headers={"x-goog-api-key": key}, timeout=30).json()
    raise SystemExit("video still processing after 15 minutes")


PROMPT = """You are the final reviewer for a faceless English documentary YouTube channel. Watch the whole draft video
and compare it with the narration script below. Report ONLY real problems, each with the time (m:ss) it happens:
- picture does not match what the narrator says at that moment (say what is shown and what is said)
- a still or clip held so long it feels frozen (over ~8 s), black or broken frames, abrupt jumps
- dead gaps or awkward pauses in the voice, music too loud over speech
- a name or word the narrator mispronounces (compare with the script spelling)
- on-screen text or numbers that are wrong, misspelled or contradict the script
- facts, dates, ages or numbers that contradict each other inside the script
Answer as JSON only: {"verdict": "PASS" or "FAIL", "issues": [{"time": "m:ss", "type": "...", "problem": "...",
"fix": "..."}], "strengths": ["..."]}. FAIL if any issue would make a viewer leave or doubt the channel.

SCRIPT:
"""


def main() -> None:
    ep = sys.argv[1]
    video = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "out" / ep / "long.mp4"
    meta = json.loads((ROOT / "episodes" / ep / "episode.json").read_text(encoding="utf-8"))
    script = (ROOT / "episodes" / ep / meta["scripts"]["en"]).read_text(encoding="utf-8")
    key = _gemini_key()
    if not key:
        raise SystemExit("no Gemini key (GEMINI_API_KEY or ~/.flow-mcp/gemini-key)")
    log(f"uploading {video.name} ({video.stat().st_size // 1048576} MB)")
    f = upload(video, key)
    body = {"contents": [{"parts": [{"file_data": {"mime_type": "video/mp4", "file_uri": f["uri"]}},
                                    {"text": PROMPT + script}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}}
    result = None
    for attempt in range(3):
        r = requests.post(f"{API}/v1beta/models/{MODEL}:generateContent", headers={"x-goog-api-key": key},
                          json=body, timeout=600)
        if r.status_code in (429, 500, 503):
            log(f"Gemini busy ({r.status_code}), retry {attempt + 1}/3")
            time.sleep(30 * (attempt + 1))
            continue
        r.raise_for_status()
        result = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        break
    requests.delete(f"{API}/v1beta/{f['name']}", headers={"x-goog-api-key": key}, timeout=30)
    if result is None:
        raise SystemExit("Gemini did not answer after 3 tries")
    dst = ROOT / "out" / ep / "gemini_review.json"
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"verdict {result.get('verdict')}, {len(result.get('issues', []))} issue(s) -> {dst}")
    for i in result.get("issues", []):
        print(f"  {i.get('time')}  [{i.get('type')}] {i.get('problem')}  ->  {i.get('fix')}", flush=True)


if __name__ == "__main__":
    main()
