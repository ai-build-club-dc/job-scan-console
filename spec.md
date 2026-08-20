# /scan-jobs — Design Spec

Original design 2026-08-13 · generalized for the shared repo 2026-08-18.
Goal: a process to scan job boards and surface a curated list of jobs matching the user's criteria, qualifications, and preferences.

## Sources & access

- **Primary:** Indeed connector (`search_jobs` tool) — live, automatic, run each time `/scan-jobs` is invoked.
- **Secondary:** manual paste of a specific posting or link (e.g. found on LinkedIn or a company site). Evaluated through the same profile/scoring logic. Freshness is checked from the pasted "posted X ago" text if present, or via `WebFetch` on a bare link; if neither yields a determinable date, the job is flagged "posted date unknown" rather than silently included or excluded.
- **Future extension (not built now):** additional job boards, to cover sources the Indeed connector doesn't reach.

## Profile (`profile.md`)

Per-user, created during onboarding (see `CLAUDE.md`) from the user's resume plus an interview. Sections — heading names are a parse contract with the console UI:

- **Background (from resume):** short summary of their arc, industries, standout skills — drafted from `resume.md`.
- **Target titles:** 2–3 titles, plus optional explicit exclusions (excluded titles are rejected before scoring).
- **Location / Salary floor / Job type / Dealbreakers / Freshness rule:** the user's own answers; freshness defaults to 48 hours.
- **Scoring rubric:** title match (0–4) + substance (0–4) + logistics (0–2); the substance dimension is personalized to the user's background. Calibration anchors get recorded from real scans over time.

## Search mechanics

- One `search_jobs` query per (target title × location) from the profile, `country_code: "US"`; location strings derived from the profile's Location section.
- Merge results across all queries and dedupe by job ID.
- Score every merged result against the profile using summary-level data first (1–10 fit, per the profile's Scoring rubric).
- Apply hard filters: salary floor, freshness window, dealbreakers, excluded titles.
- For filter survivors only, call `get_job_details` to confirm details and retrieve a real apply link (avoids spending calls on obvious rejects).
- `get_company_data` (culture/salary ratings) is **not** called in v1 — flagged as a future extension.
- Report shows results scoring ≥6/10, capped at **10 results max**, each with a Why block, a Score block (the rubric breakdown), and a Posting block — see Output below.

## Output

- One new timestamped file per run: `reports/{YYYY-MM-DD-HHmm}.md`.
- Fields per job: title, company, location, salary (or "not listed"), fit score, a Why block, a Score block, a Posting block, apply link.
- The `**Fit:** N/10` line format is a parse contract with the console — never change it.
- **v0.9 (report format extension):** the per-job entry expanded from a single-line "Why" rationale into three bullet blocks — `**Why:**`, `**Score:**`, `**Posting:**` — each a label line followed by `- ` bullets, per `.claude/skills/scan-jobs/SKILL.md` step 8. This exists because the console's row-detail panel needs structured content (why recommended, score breakdown, posting highlights) to render on click, and since the console is a static file it can only show what was written into the report at scan time — there's no server-side computation to derive it later. The old parenthetical component breakdown appended to the Why line is superseded by the `**Score:**` block and is no longer written.
- **Stateless for v1:** no cross-run dedup tracking. Repeats across scans are expected and acceptable for now.

## Trigger

- **On-demand:** the user runs `/scan-jobs` whenever they want a scan.
- **Optional recurring:** a per-user scheduled Claude task (e.g. daily each morning). A scheduled run must never fabricate results — if the Indeed connector is unavailable in that context, it writes a `reports/{timestamp}-FAILED.md` explaining why instead.

## Packaging

- A project skill at `.claude/skills/scan-jobs/SKILL.md` — available automatically in Claude sessions opened in this folder, invoked as `/scan-jobs`.
- Accepts an optional batch of pasted postings/links alongside the automatic Indeed scan.
- The console (`console/index.html`) is a single-file static dashboard over `profile.md` + `reports/` — serve the repo root (`python3 -m http.server 8642 --bind 127.0.0.1`) and open `/console/`.

## Implementation defaults (low-stakes, reversible)

- `search_jobs`'s `job_type` param only accepts one value at a time, not a set. Rather than multiplying the query count, `job_type` is left unfiltered in the query and eligibility is checked from the result text instead.
- If a listing has no salary shown in the summary, it is not auto-rejected for that alone — the `get_job_details` check resolves it before the hard-filter decision is finalized.

## Extensions (explicitly out of scope for v1)

- Additional job boards beyond Indeed.
- Artifact-based output (vs. Markdown report).
- Cross-run dedup tracking of previously surfaced jobs.
- Company culture/salary data (`get_company_data`) in the report.
- In-console profile editing and a real Run button (requires a local server executing scans — see the repo's issue tracker if/when this lands).
