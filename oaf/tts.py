"""Narration: edge-tts (free, no key) or Google Cloud TTS Chirp 3 HD. Then auto-editor tightens pauses."""
from __future__ import annotations

import asyncio
import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

import requests

from .common import env, log, run


def clean_for_speech(text: str) -> str:
    """Strip anything a voice should not read: markdown, brackets, stage notes."""
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"[*_#>`|]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def _edge(text: str, voice: str, rate: str, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def _chirp(text: str, voice: str, rate: float, out: Path) -> None:
    """Google Cloud TTS REST with a service-account key (GOOGLE_TTS_KEY_JSON). Chunks at ~4,500 bytes."""
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    info = json.loads(env("GOOGLE_TTS_KEY_JSON"))
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    lang = "-".join(voice.split("-")[:2])
    chunks, cur = [], ""
    for para in text.split("\n"):
        if len((cur + "\n" + para).encode()) > 4500 and cur:
            chunks.append(cur)
            cur = para
        else:
            cur = (cur + "\n" + para).strip()
    if cur:
        chunks.append(cur)
    parts = []
    for i, chunk in enumerate(chunks):
        r = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            headers={"Authorization": f"Bearer {creds.token}"},
            json={"input": {"text": chunk},
                  "voice": {"languageCode": lang, "name": voice},
                  "audioConfig": {"audioEncoding": "LINEAR16", "speakingRate": rate, "sampleRateHertz": 24000}},
            timeout=300)
        r.raise_for_status()
        part = out.with_name(f"{out.stem}_part{i}.wav")
        part.write_bytes(base64.b64decode(r.json()["audioContent"]))
        parts.append(part)
    lst = out.with_name(out.stem + "_parts.txt")
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), str(out)])


def trim_silence(src: Path, dst: Path, tool: str = "ffmpeg") -> Path:
    """Shorten every pause longer than 0.6 s to 0.35 s. Default is ffmpeg silenceremove: auto-editor 2x
    (tested 2026-11-25) squeezed the opening words and inserted 4 s gaps, so it is opt-in only."""
    if tool == "auto-editor" and shutil.which("auto-editor"):
        p = subprocess.run(["auto-editor", str(src), "--edit", "audio:threshold=0.03", "--margin", "0.25s",
                            "--no-open", "-o", str(dst)], capture_output=True, text=True)
        if p.returncode == 0 and dst.exists():
            return dst
        log("auto-editor failed, using ffmpeg silenceremove")
    run(["ffmpeg", "-y", "-i", str(src), "-af",
         "silenceremove=stop_periods=-1:stop_duration=0.6:stop_silence=0.35:stop_threshold=-45dB", str(dst)])
    return dst


def narrate(text: str, lang: str, cfg: dict, out_wav: Path) -> Path:
    """Speak `text` in `lang` ("en"/"ar"); returns a 48 kHz mono WAV, loudness-levelled."""
    text = clean_for_speech(text)
    vc = cfg["voice"]
    raw = out_wav.with_name(out_wav.stem + "_raw")
    engine = vc["engine"]
    if engine == "chirp" and not env("GOOGLE_TTS_KEY_JSON"):
        log("chirp chosen but GOOGLE_TTS_KEY_JSON is not set: using edge-tts")
        engine = "edge"
    if engine == "chirp":
        raw = raw.with_suffix(".wav")
        _chirp(text, vc["chirp"][lang], vc["chirp"]["speaking_rate"], raw)
    else:
        raw = raw.with_suffix(".mp3")
        asyncio.run(_edge(text, vc["edge"][lang], vc["edge"]["rate"], raw))
    wav = out_wav.with_name(out_wav.stem + "_full.wav")
    run(["ffmpeg", "-y", "-i", str(raw), "-ac", "1", "-ar", "48000", str(wav)])
    if vc.get("trim_silence"):
        wav = trim_silence(wav, out_wav.with_name(out_wav.stem + "_tight.wav"), vc.get("trim_tool", "ffmpeg"))
    run(["ffmpeg", "-y", "-i", str(wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1",
         str(out_wav)])
    return out_wav
