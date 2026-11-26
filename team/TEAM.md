# Origin & Flaw production team

Supreme commander: Claude (main session). Every episode passes through every seat below, in this order.
Agent seats are run as sub-agents with the brief in team/<seat>.md; code seats are the pipeline (oaf/*).
The commander reads every report, resolves conflicts, and nothing ships until the evaluator passes it.

| # | Seat | Who | Output |
|---|---|---|---|
| 1 | Topic scout (uniqueness + virality) | agent: team/scout.md | 3 candidate topics: proof few/no channels covered them, curiosity score, search demand |
| 2 | Researcher | agent: team/researcher.md | research dossier with 2+ sources per fact |
| 3 | Fact-checker | agent: team/factchecker.md | every claim marked VERIFIED / DISPUTED / CUT, independent of the researcher |
| 4 | Audience psychologist | agent: team/psychologist.md | hook options, open loops, the natural like/comment/subscribe moments |
| 5 | Scriptwriter | commander | package: titles, thumbnail, script (1,500-1,700 words), Short, scenes |
| 6 | Plain-language editor | agent: team/plainlanguage.md | script rewritten so a 14-year-old non-native speaker follows every line |
| 7 | Spanish dubbing writer | agent: team/spanish.md | natural Latin-American Spanish script for the second audio track |
| 8 | Visual director (stills) | commander + Flow Nano Banana | 50-60 stills, every one checked on a contact sheet |
| 9 | Clip director | commander + Flow Omni | 4-6 clips, every 1/2 s checked for morphs/text |
| 10 | Narrator | code: oaf/tts.py (Gemini Charon) | English + Spanish narration, recorded on the PC |
| 11 | Music | code: oaf/render.py music_bed | owner's Suno tracks, ducked under the voice |
| 12 | Editor | code: oaf/render.py | picture, pacing (max 7 s hold), chapters, number callouts |
| 13 | Subtitles | code: oaf/subtitles.py | English captions (YouTube auto-translates the rest) |
| 14 | Timing checker | code: oaf/qa.py + commander | chapters, callouts and cuts land on the right words |
| 15 | Final evaluator | code: oaf/qa.py + agent: team/evaluator.md | PASS/FAIL against the playbook; FAIL blocks the release |
| 16 | Make/publish monitor | code: publish.yml guard + commander daily check | every scheduled post went out; failures fixed the same day |

Rules for every seat: PLAYBOOK.md. Honesty over hype: a fact that cannot be verified is cut, never softened.
