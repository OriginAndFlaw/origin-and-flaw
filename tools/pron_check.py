"""Pronunciation check: listen to a narration and list script words the voice did not say clearly.
python tools/pron_check.py <audio> <script.txt>   (faster-whisper, CPU, free)
Prints each long or capitalised script word that the listener heard as something else, with its time, so it can be
respelled in config.yml voice.pronounce and the take recorded again."""
import re, sys, difflib
from faster_whisper import WhisperModel

audio, script = sys.argv[1], sys.argv[2]
NUMS = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion point percent and".split())
norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())
want = [w for w in (norm(x) for x in open(script, encoding="utf-8").read().split()) if w]
model = WhisperModel("small.en", device="cpu", compute_type="int8")
# Decode with ffmpeg (the installed PyAV rejects faster-whisper's own decoder call on this PC).
import subprocess, numpy as np
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
segs, _ = model.transcribe(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768, word_timestamps=True, beam_size=5)
heard, times = [], []
for s in segs:
    for w in s.words:
        if norm(w.word):
            heard.append(norm(w.word)); times.append(w.start)
sm = difflib.SequenceMatcher(a=want, b=heard, autojunk=False)
bad = []
for op, a1, a2, b1, b2 in sm.get_opcodes():
    if op == "replace":
        for k, w in enumerate(want[a1:a2]):
            got = " ".join(heard[b1:b2])
            # Numbers (heard as digits) and UK/US spellings (litre/liter, favour/favor) are not mispronunciations.
            if any(c.isdigit() for c in got) or w in NUMS or difflib.SequenceMatcher(a=w, b=got).ratio() >= 0.75:
                continue
            if len(w) >= 5:
                t = times[b1] if b1 < len(times) else 0
                bad.append(f"{int(t // 60)}:{int(t % 60):02d}  script '{w}'  heard '{got}'")
print("\n".join(bad) or "No mispronounced long words found.")
