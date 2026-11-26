"""Render an episode: long video (EN), Arabic audio track, Shorts (EN + AR), thumbnail, subtitles.

python -m oaf.render --episode ep01-hyatt-regency                 # everything
python -m oaf.render --episode ep01-hyatt-regency --only long     # long|arabic|short|thumb
python -m oaf.render --episode ep01-hyatt-regency --test          # 120 words, quick check
"""
from __future__ import annotations

import argparse
import json
import random
import re
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
              overlay: Path | None = None, variant: int = 0) -> Path:
    """One still -> a moving shot. Alternates push-in / pull-back and drifts a little sideways.
    variant > 0 = a closer framing of a different part of the same still (a "new shot" for long holds)."""
    fps = cfg["video"]["fps"]
    n = max(2, int(round(dur * fps)))
    z = cfg["video"]["ken_burns_zoom"]
    bw, bh = int(w * 1.5), int(h * 1.5)
    rnd = random.Random(idx * 10 + variant)
    a, b = rnd.choice([(0.5, 0.5), (0.35, 0.65), (0.65, 0.35), (0.5, 0.4)])
    base = 1 + (0.3 + 0.1 * (variant % 2)) * (variant > 0)
    if variant:
        a, b = rnd.choice([(0.15, 0.3), (0.85, 0.7), (0.3, 0.15), (0.7, 0.85)])
    zexpr = f"{base}+{z}*on/{n}" if (idx + variant) % 2 == 0 else f"{base}+{z}-{z}*on/{n}"
    vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
          f"zoompan=z='{zexpr}':x='(iw-iw/zoom)*({a}+({b}-{a})*on/{n})':y='(ih-ih/zoom)*{0.5 if not variant else rnd.choice([0.3, 0.5, 0.7])}'"
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


def music_bed(cfg: dict, seed: str, total: float, dst: Path) -> Path | None:
    """Several tracks in a shuffled order, joined with 4 s crossfades, long enough for the whole video
    (one 3-minute track looped four times sounds like a loop)."""
    folder = Path(__file__).resolve().parent.parent / cfg["music"]["folder"]
    tracks = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))
    if not tracks:
        return None
    random.Random(seed).shuffle(tracks)
    chosen, length, i = [], 0.0, 0
    while length < total + 6:
        t = tracks[i % len(tracks)]
        chosen.append(t)
        length += duration(t) - (4 if chosen[1:] else 0)
        i += 1
    if len(chosen) == 1:
        run(["ffmpeg", "-y", "-i", str(chosen[0]), "-ar", "48000", "-ac", "2", str(dst)])
        return dst
    cmd = ["ffmpeg", "-y"]
    for t in chosen:
        cmd += ["-i", str(t)]
    fc, last = "", "[0:a]"
    for k in range(1, len(chosen)):
        out = f"[x{k}]"
        fc += f"{last}[{k}:a]acrossfade=d=4:c1=tri:c2=tri{out};"
        last = out
    run(cmd + ["-filter_complex", fc.rstrip(";"), "-map", last, "-ar", "48000", "-ac", "2", str(dst)])
    return dst


def mix_audio(voice: Path, total: float, cfg: dict, dst: Path, seed: str) -> Path:
    """Voice + looping music ducked under it, levelled to -14 LUFS, exactly `total` seconds."""
    music = music_bed(cfg, seed, total, dst.with_name(dst.stem + "_bed.wav"))
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
    run(["ffmpeg", "-y", "-i", str(voice), "-i", str(music), "-filter_complex", fc,
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

def plan_long(scenes: list[dict], total: float, hook_seconds: float,
              clip_len: dict[int, float] | None = None) -> list[float]:
    """Seconds per scene: a hook scene with a real Flow clip plays that clip's full length (never a frozen
    tail), other hook scenes share the planned hook time, body scenes are scaled to fill the voice."""
    clip_len = clip_len or {}
    starts = [secs(s["t"]) for s in scenes]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    tail = sorted(gaps)[len(gaps) // 2] if gaps else total
    planned = gaps + [tail]
    hook_idx = [i for i, s in enumerate(scenes) if s["tool"] == "flow"]
    hook = {i: clip_len.get(i, min(planned[i], hook_seconds / max(1, len(hook_idx)))) for i in hook_idx}
    scale = min(1.0, total * 0.5 / (sum(hook.values()) or 1))
    hook = {i: v * scale for i, v in hook.items()}
    hook_total = sum(hook.values())
    body_idx = [i for i in range(len(scenes)) if i not in hook_idx]
    body_planned = sum(planned[i] for i in body_idx) or 1
    return [hook[i] if i in hook else planned[i] * (total - hook_total) / body_planned
            for i in range(len(scenes))]


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def find_phrase(ws: list[dict], phrase: str) -> float | None:
    """Start time of the first place the narration says `phrase` (words compared without punctuation)."""
    want = [_norm(w) for w in phrase.split() if _norm(w)]
    heard = [_norm(w["w"]) for w in ws]
    for i in range(len(heard) - len(want) + 1):
        if heard[i:i + len(want)] == want:
            return ws[i]["s"]
    return None


def anchor_chapters(scenes: list[dict], lengths: list[float], ws: list[dict]):
    """Move scene boundaries so every chapter scene starts exactly when the narration reaches its `cue`
    phrase; the stills between two anchors are stretched or squeezed evenly. Returns new lengths and
    [(time, chapter title)] for the description's chapter list."""
    starts = [sum(lengths[:i]) for i in range(len(lengths))]
    anchors = {}
    for i, sc in enumerate(scenes):
        if sc.get("chapter") and sc.get("cue"):
            t = find_phrase(ws, sc["cue"])
            if t is None:
                log(f"chapter cue not heard: {sc['cue']!r} (scene {sc['n']}): left where it was")
            else:
                anchors[i] = max(t - 0.3, 0.0)
    if not anchors:
        return lengths, [(starts[i], sc["chapter"]) for i, sc in enumerate(scenes) if sc.get("chapter")]
    total = sum(lengths)
    keys = sorted(anchors)
    bounds = [(0, 0.0)] + [(i, anchors[i]) for i in keys] + [(len(scenes), total)]
    new = list(lengths)
    for (a, ta), (b, tb) in zip(bounds, bounds[1:]):
        fixed = sum(lengths[k] for k in range(a, b) if scenes[k]["tool"] == "flow")
        flex = [k for k in range(a, b) if scenes[k]["tool"] != "flow"]
        room = max(tb - ta - fixed, 0.5 * len(flex))
        # Even pace inside a chapter: the package's planned times are rough, and uneven ones left one still
        # on screen for 40 s and another for 4 s (EP02).
        for k in flex:
            new[k] = max(room / len(flex), 0.5)
    starts = [sum(new[:i]) for i in range(len(new))]
    return new, [(starts[i], sc["chapter"]) for i, sc in enumerate(scenes) if sc.get("chapter")]


# ---------- builders ----------

def add_callouts(picture: Path, callouts: list[dict], ws: list[dict], total: float, cfg: dict, work: Path,
                 w: int, h: int) -> Path:
    """Big numbers on screen at the moment the narration says them: [{"cue": "a hundred and fourteen",
    "text": "114"}]. Each shows for about 3 s, fading in and out."""
    shown = []
    for k, c in enumerate(callouts):
        t = find_phrase(ws, c["cue"])
        if t is None:
            log(f"callout cue not heard, skipped: {c['cue']}")
            continue
        shown.append((t, cards.callout(c["text"], work / f"callout_{k}.png", w, h)))
    if not shown:
        return picture
    cmd = ["ffmpeg", "-y", "-i", str(picture)]
    fc, last = [], "0:v"
    for k, (t, png) in enumerate(shown):
        cmd += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(png)]
        fc.append(f"[{k + 1}:v]format=rgba,fade=in:st={t:.2f}:d=0.3:alpha=1,"
                  f"fade=out:st={t + 2.7:.2f}:d=0.4:alpha=1[c{k}]")
        fc.append(f"[{last}][c{k}]overlay=shortest=1[v{k}]")
        last = f"v{k}"
    dst = work / "picture_long_callouts.mp4"
    run(cmd + ["-filter_complex", ";".join(fc), "-map", f"[{last}]"] + enc(cfg) + ["-an", str(dst)])
    log(f"{len(shown)} number callouts added")
    return dst


def build_long(ep: dict, folder: Path, cfg: dict, work: Path, out: Path, max_words: int | None) -> dict:
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    voice = tts.narrate(read_script(folder, ep["scripts"]["en"], max_words), "en", cfg, work / "voice_en.wav")
    total = duration(voice)
    log(f"English narration {total / 60:.1f} min")
    min_s = cfg.get("quality", {}).get("min_long_seconds", 480)
    if max_words is None and total < min_s:  # channel rule: every long video runs past 8 minutes
        raise SystemExit(f"narration is {total / 60:.1f} min, under the {min_s / 60:.0f}-minute minimum: lengthen the script")
    scenes = ep["scenes"]
    if max_words:
        scenes = scenes[:6]
    clip_len = {i: duration(folder / s["clip"]) for i, s in enumerate(scenes)
                if s["tool"] == "flow" and s.get("clip") and (folder / s["clip"]).exists()}
    lengths = plan_long(scenes, total, ep.get("hook_seconds", 20), clip_len)
    ws = subtitles.words(voice, "en", cfg["subtitles"]["model"])
    lengths, chapter_times = anchor_chapters(scenes, lengths, ws)
    if chapter_times:
        (out / "chapters.txt").write_text(
            f"0:00 {ep.get('intro_chapter', 'Intro')}\n" + "".join(f"{int(t // 60)}:{int(t % 60):02d} {title}\n" for t, title in chapter_times),
            encoding="utf-8")
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
            still = images.get_still(sc, folder, cfg)
            hold = cfg["video"].get("max_hold", 7.5)
            k = max(1, int(-(-d // hold)))  # owner/Gemini review: change the picture every 5-8 s
            if k == 1:
                ken_burns(still, d, seg, i, cfg, W, H, ov)
            else:
                subs = []
                for j in range(k):
                    sp = work / f"seg_{i:03d}_{j}.mp4"
                    ken_burns(still, d / k, sp, i, cfg, W, H, ov if j == 0 else None, variant=j)
                    subs.append(sp)
                concat(subs, seg)
        parts.append(seg)
        log(f"scene {i + 1}/{len(scenes)} done ({d:.1f}s)")
    picture = concat(parts, work / "picture_long.mp4")
    picture = add_callouts(picture, ep.get("callouts", []), ws, total, cfg, work, W, H)
    audio = mix_audio(voice, total, cfg, work / "mix_en.wav", ep["id"])
    ass = None
    subtitles.write_srt(ws, out / "long_en.srt")
    if cfg["subtitles"].get("burn_in_long"):
        ass = subtitles.write_word_ass(ws, work / "long.ass", W, H, cfg["subtitles"]["font"], per_group=6)
    finish(picture, audio, total, cfg, out / "long.mp4", ass)
    upload_copy(out / "long.mp4", total, cfg)
    return {"total": total}


def upload_copy(src: Path, total: float, cfg: dict) -> None:
    """Make.com moves files only up to its plan's size limit (Core: 100 MB). When the master is bigger,
    write long_upload.mp4 aimed at `upload.max_mb` (slow Ken Burns stills compress well)."""
    max_mb = cfg["upload"].get("max_mb")
    if not max_mb or src.stat().st_size <= max_mb * 1e6:
        return
    kbps = int(max_mb * 8000 / total) - 160 - 40  # minus audio and container overhead
    log(f"master is {src.stat().st_size / 1e6:.0f} MB: writing a {max_mb} MB upload copy at {kbps} kb/s")
    run(["ffmpeg", "-y", "-i", str(src), "-c:v", "libx264", "-preset", "medium", "-b:v", f"{kbps}k",
         "-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 3}k", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(src.with_name("long_upload.mp4"))])


def build_dub(ep: dict, folder: Path, cfg: dict, work: Path, out: Path, total: float,
              max_words: int | None, lang: str) -> None:
    """Narration in another language fitted to the English video's length, with the same music: for
    YouTube's multi-language audio (added in Studio). Arabic also gets its own subtitle file."""
    name = ep["scripts"].get(lang) or f"script_{lang}.txt"
    if not (folder / name).exists():
        log(f"no {name}: {lang} track skipped")
        return
    text = read_script(folder, name, max_words)
    voice = tts.narrate(text, lang, cfg, work / f"voice_{lang}.wav")
    ratio = duration(voice) / total
    if ratio > 1.15:  # too long: speak faster rather than squeeze it all with atempo
        base = int(str(cfg["voice"]["edge"]["rate"]).rstrip("%"))
        c2 = json.loads(json.dumps(cfg))
        c2["voice"]["edge"]["rate"] = f"{base + round((ratio - 1.05) * 100):+d}%"
        log(f"{lang} is {ratio:.2f}x the English length: re-reading at {c2['voice']['edge']['rate']}")
        voice = tts.narrate(text, lang, c2, work / f"voice_{lang}.wav")
        ratio = duration(voice) / total
    fitted = work / f"voice_{lang}_fit.wav"
    if 0.8 <= ratio <= 1.35:  # Spanish runs ~20-30% longer than English; up to 1.35x still sounds natural
        run(["ffmpeg", "-y", "-i", str(voice), "-af", f"atempo={ratio:.4f}", str(fitted)])
    else:
        log(f"{lang} is {ratio:.2f}x the English length: not stretched (shorten or lengthen the script)")
        shutil.copy(voice, fitted)
    mix = mix_audio(fitted, total, cfg, work / f"mix_{lang}.wav", ep["id"])
    run(["ffmpeg", "-y", "-i", str(mix), "-c:a", "aac", "-b:a", "192k", str(out / f"audio_track_{lang}.m4a")])
    if lang == "ar":
        subtitles.write_srt(subtitles.words(fitted, "ar", cfg["subtitles"]["model"]), out / "long_ar.srt")


def build_short(ep: dict, folder: Path, cfg: dict, work: Path, out: Path, lang: str,
                sh: dict | None = None, tag: str = "") -> None:
    """tag "" = the episode's main Short (short_<lang>.mp4); "b", "c"... = extra Shorts (short_b_<lang>.mp4)"""
    W, H = 1080, 1920
    sh = sh or ep["short"]
    lang_tag = f"{tag}_{lang}" if tag else lang
    voice = tts.narrate((folder / sh[lang]).read_text(encoding="utf-8"), lang, cfg, work / f"voice_short_{lang_tag}.wav")
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
        seg = work / f"short_{lang_tag}_{i:02d}.mp4"
        d = hook_len if sc["tool"] == "flow" else rest
        clip = folder / sc["clip"] if sc.get("clip") else None
        if sc["tool"] == "flow" and clip and clip.exists():
            fit_clip(clip, d, seg, cfg, W, H)
        else:
            src = by_n.get(int(sc["use"])) if sc.get("use") else sc
            ken_burns(images.get_still(src, folder, cfg), d, seg, i + 7, cfg, W, H)
        parts.append(seg)
    picture = concat(parts, work / f"picture_short_{lang_tag}.mp4")
    audio = mix_audio(voice, total, cfg, work / f"mix_short_{lang_tag}.wav", ep["id"] + lang_tag)
    ws = subtitles.words(voice, lang, cfg["subtitles"]["model"])
    font = "Noto Naskh Arabic" if lang == "ar" else cfg["subtitles"]["font"]
    ass = subtitles.write_word_ass(ws, work / f"short_{lang_tag}.ass", W, H, font)
    finish(picture, audio, total, cfg, out / f"short_{lang_tag}.mp4", ass)


def build_thumb(ep: dict, folder: Path, cfg: dict, out: Path) -> None:
    th = ep.get("thumbnail") or {}
    by_n = {int(s["n"]): s for s in ep["scenes"]}
    sc = by_n.get(int(th.get("scene", 7)), ep["scenes"][-1])
    cards.thumbnail(images.get_still(sc, folder, cfg), th.get("words", ep["title"][:20]), out / "thumbnail.jpg")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--only", default="long,arabic,dubs,short,extra,thumb")
    ap.add_argument("--test", action="store_true", help="first 120 words and 6 scenes only")
    a = ap.parse_args()
    need("ffmpeg")
    cfg = load_config()
    ep, folder = load_episode(a.episode)
    tts.PREREC = folder / "voice"
    out = OUT / a.episode
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    mw = 120 if a.test else None
    what = set(a.only.split(","))
    info = {}
    if "long" in what:
        info = build_long(ep, folder, cfg, work, out, mw)
    dubs = [l for l in cfg.get("dubs", []) if ("arabic" in what and l == "ar") or ("dubs" in what and l != "ar")]
    if dubs:
        total = info.get("total") or duration(out / "long.mp4")
        for lang in dubs:
            build_dub(ep, folder, cfg, work, out, total, mw, lang)
    if "short" in what and ep.get("short") and not a.test:
        for lang in ["en"]:  # Shorts stay English; the second language rides on the long video's audio track
            if ep["short"].get(lang):
                build_short(ep, folder, cfg, work, out, lang)
    if "extra" in what and not a.test:
        for x in ep.get("extra_shorts", []):
            for lang in ["en"]:
                if x.get(lang):
                    build_short(ep, folder, cfg, work, out, lang, x, x["id"])
    if "thumb" in what:
        build_thumb(ep, folder, cfg, out)
    (out / "meta.json").write_text(json.dumps({k: ep.get(k) for k in ("id", "title", "description", "tags", "short", "extra_shorts")},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"done: {out}")


if __name__ == "__main__":
    main()
