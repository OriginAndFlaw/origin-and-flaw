"""Word timings with faster-whisper -> .srt for upload and word-highlight .ass for Shorts."""
from __future__ import annotations

from pathlib import Path

from .common import log

_MODELS: dict = {}


def words(audio: Path, lang: str, model_size: str = "small") -> list[dict]:
    from faster_whisper import WhisperModel
    if model_size not in _MODELS:
        log(f"loading faster-whisper {model_size}")
        _MODELS[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    # decode with ffmpeg ourselves: faster-whisper's own PyAV decoder breaks across PyAV versions
    import subprocess
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, dtype=np.float32)
    # NO vad_filter: on a clean 10-minute voice track it shifted every word ~9 s EARLY (EP03, 27 Nov), so pictures,
    # chapters, callouts and captions all came in before the voice. Checked against the audio itself.
    segs, _ = _MODELS[model_size].transcribe(samples, language=lang, word_timestamps=True,
                                             vad_filter=False, beam_size=5)
    out = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if t:
                out.append({"w": t, "s": float(w.start), "e": float(w.end)})
    return out


def script_timed(ws: list[dict], script: str) -> list[dict]:
    """The SCRIPT's own words carrying the listener's times, so captions are spelled as written ("Pozzuoli",
    "Vitruvius", "Aspdin") instead of as misheard ("Po Swalli", "Vituvius", "Aston"; EP02 CC, 28 Nov).
    Matched words take the heard word's time; unmatched runs share the time span between their neighbours."""
    import difflib, re
    norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
    toks = [t for t in script.split() if norm(t)]
    a, b = [norm(t) for t in toks], [norm(w["w"]) for w in ws]
    out: list[dict | None] = [None] * len(toks)
    for blk in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            w = ws[blk.b + k]
            out[blk.a + k] = {"w": toks[blk.a + k], "s": w["s"], "e": w["e"]}
    i = 0
    while i < len(out):
        if out[i] is not None:
            i += 1
            continue
        j = i
        while j < len(out) and out[j] is None:
            j += 1
        t0 = out[i - 1]["e"] if i > 0 else (ws[0]["s"] if ws else 0.0)
        t1 = out[j]["s"] if j < len(out) else (ws[-1]["e"] if ws else t0 + 0.4 * (j - i))
        step = max(t1 - t0, 0.05 * (j - i)) / (j - i)
        for k in range(i, j):
            out[k] = {"w": toks[k], "s": t0 + step * (k - i), "e": t0 + step * (k - i + 1)}
        i = j
    return [o for o in out if o]


def _ts(t: float, sep: str = ",") -> str:
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)):03d}"


def write_srt(ws: list[dict], dst: Path, max_words: int = 9) -> Path:
    """Caption lines that break at sentence ends or after max_words."""
    lines, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= max_words or w["w"][-1:] in ".?!؟":
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    with open(dst, "w", encoding="utf-8") as f:
        for i, ln in enumerate(lines, 1):
            f.write(f"{i}\n{_ts(ln[0]['s'])} --> {_ts(ln[-1]['e'])}\n{' '.join(x['w'] for x in ln)}\n\n")
    return dst


def write_word_ass(ws: list[dict], dst: Path, w: int, h: int, font: str = "Arial", per_group: int = 3) -> Path:
    """Big centred captions, three words at a time, the spoken word in amber (Shorts style)."""
    size = int(min(h * 0.045, w * 0.08))
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 0\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: W,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,%d,2,2,90,90,%d,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    ) % (w, h, font, size, max(3, size // 12), int(h * 0.30))
    ev = []
    groups = [ws[i:i + per_group] for i in range(0, len(ws), per_group)]
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else None
        for k, cur in enumerate(g):
            end = g[k + 1]["s"] if k + 1 < len(g) else cur["e"] + 0.15
            if nxt is not None:  # never overlap the next group: libass would stack the two lines
                end = min(end, nxt)
            txt = " ".join(("{\\c&H48A8E8&}" + x["w"].upper() + "{\\c&HFFFFFF&}") if j == k else x["w"].upper()
                           for j, x in enumerate(g))
            ev.append(f"Dialogue: 0,{_ts(cur['s'], '.')[:-1]},{_ts(end, '.')[:-1]},W,,0,0,0,,{txt}")
    dst.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return dst
