# Job Scan Console

A personal job-search system you run with Claude. It has three parts:

- **`/scan-jobs`** — a Claude skill that searches Indeed against *your* criteria, scores every posting with a personalized rubric, and writes a curated markdown report.
- **`profile.md`** — your search profile (target titles, location, salary floor, dealbreakers, scoring rubric). Built for you during onboarding; never committed to git.
- **The console** — a local web dashboard showing your profile and every scan report in a sortable results table.

Scans run inside Claude sessions (or on a daily schedule you can ask Claude to set up). The console is the dashboard over the results — your resume, profile, and reports never leave your machine.

**New here? Start with the [User guide](USER-GUIDE.md)** — a step-by-step walkthrough with screenshots, from install to your first scored report.

## Prerequisites

- **Claude desktop app** with a connected folder (these instructions assume it's called `Claude-Workshop`)
- **Indeed connector** enabled on your Claude account — this is what `/scan-jobs` searches with
- Your **resume** as a PDF in your Claude-Workshop folder (Google Doc? Use File → Download → PDF — or connect the Google Drive connector and Claude can fetch it)
- macOS with `python3` (only used to serve the console locally; any static file server works)

## Quick start (recommended)

Paste this one prompt into Claude:

> Download https://github.com/ai-build-club-dc/job-scan-console into my Claude-Workshop folder, then follow the setup instructions in job-scan-console/CLAUDE.md and onboard me.

Claude will then, with you in the loop:

1. Find your resume and create `resume.md` — a machine-readable copy used for everything afterward
2. Interview you: target titles, location, salary floor, job type, dealbreakers
3. Write **your** `profile.md`, including a scoring rubric personalized to your background
4. Start the console at http://localhost:8642/console/
5. Offer your first `/scan-jobs` run — and an optional automatic daily scan

## Manual setup

1. **Code → Download ZIP** on this repo, unzip into your Claude-Workshop folder as `job-scan-console`
2. Open Claude in that folder and say: *"Follow the setup instructions in CLAUDE.md and onboard me."*

## Everyday use

| You want | Do |
|---|---|
| A fresh scan | Ask Claude: `/scan-jobs` |
| Change criteria | Ask Claude: *"raise my salary floor to $95K"* (edits `profile.md`; console updates on refresh) |
| Automatic daily scans | Ask Claude: *"schedule a daily morning job scan"* |
| See results | http://localhost:8642/console/ → Refresh after a scan lands |
| Console offline? | Ask Claude: *"start the job scan console server"* |

## What's in the repo

| Path | What it is |
|---|---|
| `console/index.html` | The dashboard — single file, no dependencies, reads `profile.md` + `reports/` |
| `profile.template.md` | Skeleton Claude fills in to create your `profile.md` |
| `.claude/skills/scan-jobs/` | The scan skill — available automatically in sessions opened here |
| `CLAUDE.md` | Instructions your Claude follows to onboard you and run the system |
| `spec.md` | Design spec — how scanning, scoring, and reports work |
| `reports/` | Your scan reports land here (gitignored) |

Your personal files — `profile.md`, `resume*`, `reports/*`, `applications/` — are **gitignored**: they can't be committed or pushed, by you or anyone.

## Updating

Ask Claude: *"pull the latest job-scan-console"*. Your profile and reports are untouched by updates.

---

Built at **AI Build Club DC** · MIT license
