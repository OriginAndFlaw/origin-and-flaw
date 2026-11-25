"""Render an episode: long video (EN), Arabic audio track, Shorts (EN + AR), thumbnail, subtitles.

python -m oaf.render --episode ep01-hyatt-regency                 # everything
python -m oaf.render --episode ep01-hyatt-regency --only long     # long|arabic|short|thumb
python -m oaf.render --episode ep01-hyatt-regency --test          # 120 words, quick check
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from . import cards, images, subtitles, tts
from .common import OUT, duration, ff_path, load_config, load_episode, log, need, run


# ---------- helpers ----------

def secs(t: str) -> float:
    parts = [float(x) for x in str(t).split(":")]
    return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0]


def enc(cfg: dict) -> list[str]:
    v = cfg["video"]
    return ["-c:v", "libx264", "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", "yuv420p",
            "-r", str(v["fps"])]


def ken_burns(img: Path, dur: float, dst: Path, idx: int, cfg: dict, w: int, h: int,
              overlay: Path | None = None) -> Path:
    """One still -> a moving shot. Alternates push-in / pull-back and drifts a little sideways."""
    fps = cfg["video"]["fps"]
    n = max(2, int(round(dur * fps)))
    z = cfg["video"]["ken_burns_zoom"]
    bw, bh = int(w * 1.5), int(h * 1.5)
    rnd = random.Random(idx)
    a, b = rnd.choice([(0.5, 0.5), (0.35, 0.65), (0.65, 0.35), (0.5, 0.4)])
    zexpr = f"1+{z}*on/{n}" if idx % 2 == 0 else f"1+{z}-{z}*on/{n}"
    vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
          f"zoompan=z='{zexpr}':x='(iw-iw/zoom)*({a}+({b}-{a})*on/{n})':y='(ih-ih/zoom)*0.5'"
          f":d={n}:s={w}x{h}:fps={fps},setsar=1")
    cmd = ["ffmpeg", "-y", "-i", str(img)]
    if overlay:
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(overlay)]
        fc = (f"[0:v]{vf}[bg];[1:v]format=rgba,fade=in:st=0.4:d=0.6:alpha=1,"
              f"fade=out:st={min(3.6, dur - 0.7):.2f}:d=0.6:alpha=1[ov];[bg][ov]overlay=shortest=1,format=yuv420p")
        cmd += ["-filter_complex", fc]
    else:
        cmd += ["-vf", vf + ",format=yuv420p"]
    run(cmd + ["-frames:v", str(n)] + enc(cfg) + ["-an", str(dst)])
    return dst


def fit_clip(src: Path, dur: float, dst: Path, cfg: dict, w: int, h: int) -> Path:
    """A Flow clip cut/padded to exactly `dur`, cropped to the frame, silent."""
    fps = cfg["video"]["fps"]
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,"
          f"tpad=stop_mode=clone:stop_duration={dur:.3f},format=yuv420p")
    run(["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-t", f"{dur:.3f}"] + enc(cfg) + ["-an", str(dst)])
    return dst


def concat(parts: list[Path], dst: Path) -> Path:
    lst = dst.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dst)])
    return dst


def pick_music(cfg: dict, seed: str) -> Path | None:
    folder = Path(__file__).resolve().parent.parent / cfg["music"]["folder"]
    tracks = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))
    return random.Random(seed).choice(tracks) if tracks else None


def mix_audio(voice: Path, total: float, cfg: dict, dst: Path, seed: str) -> Path:
    """Voice + looping music ducked under it, levelled to -14 LUFS, exactly `total` seconds."""
    music = pick_music(cfg, seed)
    if not music:
        run(["ffmpeg", "-y", "-i", str(voice), "-af",
             f"apad,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5", "-ar", "48000", str(dst)])
        return dst
    mc = cfg["music"]
    fc = (f"[0:a]apad,atrim=0:{total:.3f},asplit=2[v][sc];"
          f"[1:a]aresample=48000,volume={mc['volume']},atrim=0:{total:.3f},"
          f"afade=t=out:st={max(0, total - 4):.2f}:d=4[m];")
    if mc.get("duck", True):
        fc += "[m][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[md];[v][md]"
    else:
        fc += "[sc]anullsink;[v][m]"
    fc += "amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[out]"
    run(["ffmpeg", "-y", "-i", str(voice), "-stream_loop", "-1", "-i", str(music), "-filter_complex", fc,
         "-map", "[out]", "-ar", "48000", str(dst)])
    return dst


def finish(picture: Path, audio: Path, total: float, cfg: dict, dst: Path, ass: Path | None = None) -> Path:
    vf = []
    if cfg["video"].get("vignette"):
        vf.append("vignette=PI/5")
    if ass:
        vf.append(f"subtitles='{ff_path(ass)}'")
    cmd = ["ffmpeg", "-y", "-i", str(picture), "-i", str(audio)]
    if vf:
        cmd += ["-vf", ",".join(vf)] + enc(cfg)
    else:
        cmd += ["-c:v", "copy"]
    run(cmd + ["-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)])
    return dst


def read_script(folder: Path, name: str, max_words: int | None) -> str:
    text = (folder / name).read_text(encoding="utf-8")
    if max_words:
        text = " ".join(text.split()[:max_words])
    return text


# ---------- timing ----------

def plan_long(scenes: list[dict], total: float, hook_seconds: float) -> list[float]:
    """Seconds per scene: hook scenes keep their planned length, body scenes are scaled to fill the voice."""
    starts = [secs(s["t"]) for s in scenes]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    tail = sorted(gaps)[len(gaps) // 2] if gaps else total
    planned = gaps + [tail]
    hook_idx = [i for i, s in enumerate(scenes) if s["tool"] == "flow"]
    hook_total = min(sum(planned[i] for i in hook_idx), hook_seconds, total * 0.5)
    body_idx = [i for i in range(len(scenes)) if i not in hook_idx]
    body_planned = sum(planned[i] for i in body_idx) or 1
    out = []
    for i in range(len(scenes)):
        if i in hook_idx:
            out.append(hook_total / max(1, len(hook_idx)))
        else:
            out.append(planned[i] * (total - hook_total) / body_planned)
    return out


# ---------- builders ----------

def build_long(ep: dict, folder: Path, cfg: dict, work: Path, out: Path, max_words: int | None) -> dict:
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    voice = tts.narrate(read_script(folder, ep["scripts"]["en"], max_words), "en", cfg, work / "voice_en.wav")
    total = duration(voice)
    log(f"English narration {total / 60:.1f} min")
    scenes = ep["scenes"]
    if max_words:
        scenes = scenes[:6]
    lengths = plan_long(scenes, total, ep.get("hook_seconds", 20))
    parts, chapter_no = [], 0
    for i, (sc, d) in enumerate(zip(scenes, lengths)):
        seg = work / f"seg_{i:03d}.mp4"
        clip = folder / sc["clip"] if sc.get("clip") else None
        if sc["tool"] == "flow" and clip and clip.exists():
            fit_clip(clip, d, seg, cfg, W, H)
        else:
            ov = None
            if sc.get("chapter"):
                chapter_no += 1
                ov = cards.chapter_overlay(chapter_no, sc["chapter"], work / f"chapter_{chapter_no}.png", W, H)
            ken_burns(images.get_still(sc, folder, cfg), d, seg, i, cfg, W, H, ov)
        parts.append(seg)
        log(f"scene {i + 1}/{len(scenes)} done ({d:.1f}s)")
    picture = concat(parts, work / "picture_long.mp4")
    audio = mix_audio(voice, total, cfg, work / "mix_en.wav", ep["id"])
    ass = None
    ws = subtitles.words(voice, "en", cfg["subtitles"]["model"])
    subtitles.write_srt(ws, out / "long_en.srt")
    if cfg["subtitles"].get("burn_in_long"):
        ass = subtitles.write_word_ass(ws, work / "long.ass", W, H, cfg["subtitles"]["font"], per_group=6)
    finish(picture, audio, total, cfg, out / "long.mp4", ass)
    return {"total": total}


def build_arabic_track(ep: dict, folder: Path, cfg: dict, work: Path, out: Path, total: float,
                       max_words: int | None) -> None:
    """Arabic narration fitted to the English video's length, with the same music: for YouTube's
    multi-language audio feature (added in Studio), plus Arabic subtitles."""
    voice = tts.narrate(read_script(folder, ep["scripts"]["ar"], max_words), "ar", cfg, work / "voice_ar.wav")
    d = duration(voice)
    ratio = d / total
    fitted = work / "voice_ar_fit.wav"
    if 0.8 <= ratio <= 1.25:
        run(["ffmpeg", "-y", "-i", str(voice), "-af", f"atempo={ratio:.4f}", str(fitted)])
    else:
        log(f"Arabic is {ratio:.2f}x the English length: not stretched (shorten or lengthen the Arabic script)")
        shutil.copy(voice, fitted)
    mix = mix_audio(fitted, total, cfg, work / "mix_ar.wav", ep["id"])
    run(["ffmpeg", "-y", "-i", str(mix), "-c:a", "aac", "-b:a", "192k", str(out / "audio_track_ar.m4a")])
    subtitles.write_srt(subtitles.words(fitted, "ar", cfg["subtitles"]["model"]), out / "long_ar.srt")


def build_short(ep: dict, folder: Path, cfg: dict, work: Path, out: Path, lang: str) -> None:
    W, H = 1080, 1920
    sh = ep["short"]
    voice = tts.narrate((folder / sh[lang]).read_text(encoding="utf-8"), lang, cfg, work / f"voice_short_{lang}.wav")
    total = duration(voice)
    if total > 59:
        log(f"WARNING: {lang} Short narration is {total:.0f}s (over 59 s)")
    scenes = sh["scenes"]
    hook = [s for s in scenes if s["tool"] == "flow"]
    hook_len = min(5.0, total * 0.25) if hook else 0
    rest = (total - hook_len) / max(1, len(scenes) - len(hook))
    by_n = {int(s["n"]): s for s in ep["scenes"]}
    parts = []
    for i, sc in enumerate(scenes):
        seg = work / f"short_{lang}_{i:02d}.mp4"
        d = hook_len if sc["tool"] == "flow" else rest
        clip = folder / sc["clip"] if sc.get("clip") else None
        if sc["tool"] == "flow" and clip and clip.exists():
            fit_clip(clip, d, seg, cfg, W, H)
        else:
            src = by_n.get(int(sc["use"])) if sc.get("use") else sc
            ken_burns(images.get_still(src, folder, cfg), d, seg, i + 7, cfg, W, H)
        parts.append(seg)
    picture = concat(parts, work / f"picture_short_{lang}.mp4")
    audio = mix_audio(voice, total, cfg, work / f"mix_short_{lang}.wav", ep["id"] + lang)
    ws = subtitles.words(voice, lang, cfg["subtitles"]["model"])
    font = "Noto Naskh Arabic" if lang == "ar" else cfg["subtitles"]["font"]
    ass = subtitles.write_word_ass(ws, work / f"short_{lang}.ass", W, H, font)
    finish(picture, audio, total, cfg, out / f"short_{lang}.mp4", ass)


def build_thumb(ep: dict, folder: Path, cfg: dict, out: Path) -> None:
    th = ep.get("thumbnail") or {}
    by_n = {int(s["n"]): s for s in ep["scenes"]}
    sc = by_n.get(int(th.get("scene", 7)), ep["scenes"][-1])
    cards.thumbnail(images.get_still(sc, folder, cfg), th.get("words", ep["title"][:20]), out / "thumbnail.jpg")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--only", default="long,arabic,short,thumb")
    ap.add_argument("--test", action="store_true", help="first 120 words and 6 scenes only")
    a = ap.parse_args()
    need("ffmpeg")
    cfg = load_config()
    ep, folder = load_episode(a.episode)
    out = OUT / a.episode
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    mw = 120 if a.test else None
    what = set(a.only.split(","))
    info = {}
    if "long" in what:
        info = build_long(ep, folder, cfg, work, out, mw)
    if "arabic" in what and ep["scripts"].get("ar"):
        total = info.get("total") or duration(out / "long.mp4")
        build_arabic_track(ep, folder, cfg, work, out, total, mw)
    if "short" in what and ep.get("short") and not a.test:
        for lang in ("en", "ar"):
            if ep["short"].get(lang):
                build_short(ep, folder, cfg, work, out, lang)
    if "thumb" in what:
        build_thumb(ep, folder, cfg, out)
    (out / "meta.json").write_text(json.dumps({k: ep.get(k) for k in ("id", "title", "description", "tags", "short")},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"done: {out}")


if __name__ == "__main__":
    main()
