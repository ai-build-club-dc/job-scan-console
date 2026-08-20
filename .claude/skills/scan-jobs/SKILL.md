---
name: scan-jobs
description: Scan Indeed for jobs matching the user's job-search profile, score and filter them against their criteria, and save a curated report. Also evaluates any job postings/links pasted alongside the invocation. Use when the user asks to scan for jobs, run a job search, find openings, or says "/scan-jobs".
---

# /scan-jobs

Curate a fresh list of job matches from Indeed against the user's profile, plus any job postings or links pasted alongside the invocation. All paths below are relative to the `job-scan-console` folder (the folder containing this skill's `.claude/`). Full design rationale: `spec.md`.

## 1. Load the profile

Read `profile.md` at the repo root. If it's missing, stop and offer to onboard the user first (see `CLAUDE.md`) — don't invent criteria from scratch. Use its target titles, location preference, salary floor, job type, and dealbreakers for every step below.

## 2. Query Indeed

Load the Indeed connector's `search_jobs` / `get_job_details` tools via `ToolSearch` if they aren't already loaded (query: "Indeed job search"). If they aren't available, tell the user to add the Indeed connector to their Claude account and stop — never fabricate results.

Build the query set from the profile: one `search_jobs` query per (target title × location), `country_code: "US"`. Derive the location strings from the profile's Location section (e.g. "Open to remote OR Washington, DC metro" → `"remote"` and `"Washington, DC"`; "Remote only" → just `"remote"`). Leave `job_type` unset — eligibility is checked from result text in step 5, not filtered at the query level.

## 3. Merge and dedupe

Combine all result sets. Dedupe by job ID — a title/location pair can return overlapping postings.
Also treat two results as duplicates when their company, title, location, and compensation all
match, even if their job IDs differ — the connector has been observed minting a fresh job ID per
call for what is otherwise the identical posting, so an ID match alone is not a reliable signal and
ID-only dedupe can leave the same listing in the report twice.

## 4. Score against the profile

For every deduped result, using only the search-summary fields (title, company, location, salary if shown, snippet):

- Score fit 1–10 using the **Scoring rubric** in profile.md: title match (0–4) + substance (0–4) + logistics (0–2). Keep the `**Fit:** N/10` report-line format unchanged (the console UI parses it). The component scores get written to the entry's `**Score:**` block in step 8, not appended to the "Why" line. If the rubric section is missing from profile.md, fall back to holistic 1–10 judgment (the `**Score:**` block still gets written, just without `X/N` points — see step 8).
- Apply hard filters: reject if salary is shown and below the profile's salary floor; reject if older than the profile's freshness window at scan time; reject if it matches a dealbreaker or an excluded title.
- If salary isn't shown in the summary, don't reject on that basis alone — leave it to the detail-check in step 5.

## 5. Confirm survivors

For every result that passed the hard filters, call `get_job_details` to:

- Confirm salary meets the floor (reject now if it doesn't and salary appears here).
- Get the real apply link.
- Confirm job-type eligibility from the full description (reject if it matches none of the profile's job types).

## 6. Fold in pasted postings/links (if any)

If the user pasted job postings or links alongside the `/scan-jobs` invocation, evaluate each the same way as steps 4–5:

- If it's a link with no visible "posted X ago" text, use `WebFetch` to try to find a posted date on the page.
- If a posted date truly can't be determined, don't silently accept or reject on freshness — mark it "posted date unknown" in the report instead.
- Merge these into the same candidate pool as the Indeed results before final ranking.

## 7. Rank and cap

Sort remaining candidates by fit score, descending. Keep only those scoring ≥6/10. Cap the list at **10 results**. If the cap trims jobs that passed the ≥6/10 floor, say so in the report's intro line — e.g. "14 matched, showing the top 10" — so good matches never vanish silently.

## 8. Write the report

Save to `reports/{YYYY-MM-DD-HHmm}.md` (create the `reports/` folder if it doesn't exist). One entry per job, in this exact format — the console parses it:

```
## 1. Job Title — Company
**Location:** …
**Salary:** … (or "not listed")
**Fit:** 8/10
**Why:**
- 2–3 short bullets: why this job is recommended for this user
- …
**Score:**
- Title 3/4: one-line reason
- Substance 4/4: one-line reason
- Logistics 2/2: one-line reason
**Posting:**
- 3–5 bullets: the job post's main points
- …
**Apply:** https://…
```

`**Fit:** N/10` stays exactly this shape — never change it. For each block field (`**Why:**`, `**Score:**`, `**Posting:**`): the label sits alone on its line, followed by `- ` bullet lines; the block ends at the next `**Field:**` line, the next `##` header, or a `---` rule. `**Score:**` always has exactly three bullets, named Title/Substance/Logistics, each starting with that component's real points from step 4 (`Title X/4`, `Substance X/4`, `Logistics X/2`) followed by a colon and a one-line reason — except when profile.md has no rubric section (holistic-fallback case), where the three bullets keep their names but drop the `X/N` points (just `- Title: reason`, etc.). `**Posting:**` bullets are drawn only from material already in hand — the search-summary snippet plus the full description from step 5's `get_job_details` call (or the fetched page, for pasted postings) — never a new fetch; cover core responsibilities, hard requirements (years, skills, clearances), and logistics worth knowing (hybrid days, locations).

Note "posted date unknown" inline for any pasted job that couldn't be freshness-checked.

## 9. Summarize in chat

After writing the file, give a short chat summary: how many results, the top 2–3 by score, and the report's file path. Don't dump the full report into chat — the file is the artifact.

If `facts.md` doesn't exist at the repo root, append this one line to the summary: *"Your fact registry is still pending — finishing it unlocks a verified résumé, the honesty check, and the gap analysis. Say 'finish my registry' any time."* This scan itself isn't affected either way — `/scan-jobs` never reads `facts.md` — this is just a reminder riding along on a surface the user is already looking at.

## Out of scope

No LinkedIn scraping, no cross-run dedup tracking, no company culture/salary data lookups (`get_company_data`). These are documented extensions in `spec.md`, not missing functionality — don't build toward them unprompted. (Recurring scans ARE supported: offer a scheduled task if the user wants automatic daily scans.)
