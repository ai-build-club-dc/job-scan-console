# Job Search Profile — ⟨Your Name⟩

Used by `/scan-jobs` and displayed by the console. Edit by asking Claude in a session — the skill re-reads this file fresh on every run.

<!-- ONBOARDING NOTES (Claude: read these, then delete this comment block from the finished profile.md):
     - Fill every ⟨placeholder⟩ from the user's resume.md + their interview answers. Never keep example values the user didn't choose.
     - DO NOT rename the "## " section headings — the console UI parses them by exact name.
     - "### " subsection names inside the Scoring rubric MAY be renamed to fit the user (the console renders any). -->

## Background (from resume)

⟨2–4 sentences drafted from resume.md: current role and career arc, industries, standout skills and tools, certifications.⟩

## Target titles

- ⟨Title 1⟩
- ⟨Title 2⟩
- ⟨Title 3 — optional⟩

(Explicitly excludes: ⟨any titles the user does NOT want surfaced — optional; delete this line if none⟩)

## Location

⟨e.g. "Open to remote OR ⟨City⟩ metro." · "Remote only." · "⟨City⟩ only."⟩

## Salary floor

⟨e.g. $85,000 — the minimum the user would accept⟩

## Job type

⟨Full-time / part-time / contract / internship — whichever combination applies⟩

## Dealbreakers

- ⟨e.g. No unpaid / equity-only roles⟩
- ⟨more from the interview — optional⟩

## Freshness rule

Reject postings older than ⟨48⟩ hours at scan time.

## Scoring rubric

Fit score = title match (0–4) + substance (0–4) + logistics (0–2), integer sum out of 10. Survival threshold: ≥6/10. In each report entry, keep the `**Fit:** N/10` line format unchanged and append the component breakdown to the "Why" line, e.g. "(title 4 · substance 3 · logistics 2)".

### Title match (0–4)

- 4 — Exact or near-exact match to a target title, including close blends
- 3 — Same-family title with an off-list qualifier
- 2 — Adjacent role in the same family
- 1 — Related but distant
- 0 — Not the target role family

⟨If the user excludes titles, add: "(Excluded titles are rejected before scoring — they never get scored.)"⟩

### ⟨Domain & skills⟩ substance (0–4)

Measured against ⟨the user⟩'s background: ⟨their standout skills, domains, and tools, from resume.md⟩.

- 4 — Role centers on ⟨their strongest, most differentiated skill area⟩
- 3 — ⟨core mandate points the same direction, but less hands-on / less central⟩
- 2 — ⟨partial overlap: one meaningful component matches, or strong industry-background overlap⟩
- 1 — Generic role in the family with minor overlap
- 0 — No relevance to their background

### Logistics & practical fit (0–2)

- 2 — Clean: location and salary comfortably fit, no frictions
- 1 — Workable frictions: hybrid requirement, salary band straddling the floor, extra gates to confirm
- 0 — Serious frictions short of a hard dealbreaker

### Calibration anchors

⟨Leave empty at onboarding. After the first scan, record 2–4 real scored examples — "Company Role: 4+3+2 = 9" — so future scans stay consistent.⟩
