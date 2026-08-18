# Job Scan Console — project instructions

A self-serve job-search system: the `/scan-jobs` skill (in `.claude/skills/`) scans Indeed against `profile.md` and writes timestamped reports to `reports/`; the static console in `console/` displays both. Nothing in this repo executes scans — Claude runs them, in sessions like this one.

## If `profile.md` does not exist yet → onboard the user

Run setup conversationally, one step at a time. Never invent answers, and never keep template/example values the user didn't choose.

1. **Find the resume.** Look for a resume PDF or .docx in this folder and in its parent (the user's Claude-Workshop folder). If none is found, ask where it is. If it's a Google Doc: the easiest route is **File → Download → PDF** into the Claude-Workshop folder; if the user has the Google Drive connector connected, offer to fetch the Doc directly instead.
2. **Create `resume.md`.** Write a faithful markdown transcription of the resume **next to the original in the parent Claude-Workshop folder — NOT inside this repo** (it must never be committed or served). From now on `resume.md` is the canonical machine-readable resume: read it instead of re-parsing the PDF, and make future resume edits there at the user's request. The original PDF/Doc remains the formatting source of truth.
3. **Interview for preferences.** A resume says what they've done, not what they want — ask, with brief examples: target titles (2–3, plus any explicit exclusions), location (remote / a city / both), salary floor, job type (full-time / contract / both), dealbreakers (e.g. unpaid roles, mandatory relocation), freshness window (default 48 hours).
4. **Write `profile.md`** at this repo's root, from `profile.template.md`: Background drafted from resume.md; criteria from the interview; the Scoring rubric **personalized** — name the substance dimension after their focus and write its 0–4 anchors against their actual skills/domains from resume.md. Keep every `##` heading name exactly as the template has it (the console parses them). Leave Calibration anchors empty until after their first scan. Delete the template's HTML comment block.
5. **Start the console.** From this folder, run `python3 -m http.server 8642` as a background task, then have the user open http://localhost:8642/console/ and confirm their profile fields appear.
6. **Offer next steps:** run `/scan-jobs` now for a first report, and optionally create a scheduled task for automatic daily morning scans.

## Ongoing rules (once `profile.md` exists)

- **Profile edits happen here in sessions** ("raise my salary floor to $110K") by editing `profile.md` — the console is read-only and reflects the file on next refresh.
- **Reports:** `/scan-jobs` writes `reports/{YYYY-MM-DD-HHmm}.md`. Keep the `**Fit:** N/10` line format — the console parses it.
- **Never fabricate scan results.** If the Indeed connector's tools (`search_jobs` / `get_job_details`) are unavailable, say so and point the user to add the Indeed connector to their Claude account.
- **After the first scan**, offer to record Calibration anchors in profile.md's rubric from the real scored results.
- `profile.md`, `reports/*`, `applications/`, and `resume*` are gitignored — personal data never gets committed. Keep it that way.
