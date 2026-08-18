# Job Scan Console — user guide

Job Scan Console is a personal job-search system you run through Claude — it searches Indeed against criteria you set, scores every listing against your own background, and saves the results as reports you can browse anytime. Claude does the actual searching and scoring inside your chat sessions; the console is just the dashboard you read the results in; and your resume, profile, and reports stay on your machine the whole time.

## What you'll end up with

Once setup is done, you'll have:

- **`/scan-jobs`** — a Claude skill you invoke any time you want a fresh scan
- **`profile.md`** — your search profile: target titles, location, salary floor, dealbreakers, and a scoring rubric written around your background
- **`resume.md`** — a markdown copy of your resume that Claude reads instead of re-parsing the original file every time
- **The console** — a local dashboard that shows your profile and every report you've run

![Search profile and Job boards panels populated with sample data](docs/images/dashboard.png)
*Sample data — "Jordan Lee" is a fictional example profile, not a real person or account.*

## Before you start

- The Claude desktop app, with your `Claude-Workshop` folder connected
- The **Indeed connector** added to your Claude account — go to **Settings → Connectors** and add **Indeed**. Without it, scans can't run.
- Your resume as a PDF (or `.docx`) somewhere inside your `Claude-Workshop` folder
- If your resume is a Google Doc: use **File → Download → PDF** to save a copy into the folder, or connect the **Google Drive connector** so Claude can fetch it directly
- A Mac with `python3` installed — this is only used to serve the dashboard locally; nothing else depends on it

## Install and onboard (one prompt)

Open Claude with your `Claude-Workshop` folder connected, and paste this exact prompt:

```
Download https://github.com/ai-build-club-dc/job-scan-console into my Claude-Workshop folder, then follow the setup instructions in job-scan-console/CLAUDE.md and onboard me.
```

Claude takes it from there. Here's what happens next:

1. **Finds your resume.** Claude looks for a PDF or `.docx` in the new `job-scan-console` folder and in `Claude-Workshop` itself. If it can't find one, it'll ask you where it is.
2. **Writes `resume.md`.** A faithful markdown transcription of your resume, saved next to the original file — outside the `job-scan-console` folder, so it's never part of the repo. From this point on, `resume.md` is what Claude actually reads.
3. **Interviews you.** A short back-and-forth: your target titles (2–3, plus anything you explicitly don't want to see), location, salary floor, job type, dealbreakers, and how fresh a posting has to be (defaults to 48 hours).
4. **Writes your `profile.md`.** Your interview answers, plus a scoring rubric written specifically around your background — more on how that scoring works below.
5. **Starts the console.** Claude runs a small local server and gives you a link to open.
6. **Offers your first scan.** Claude asks if you'd like to run `/scan-jobs` right away, and whether you want a daily scan scheduled automatically.

> You'll see: a handful of permission prompts along the way, as Claude asks to run shell commands to download the repo and start the server. Clicking **Allow** is normal and expected — that's just Claude checking in before it touches your machine.

The whole process takes about ten minutes, and most of that is the interview in step 3.

### Manual alternative

If you'd rather not have Claude download anything itself:

1. On the repo page, click **Code → Download ZIP**, then unzip it into your `Claude-Workshop` folder so it's named `job-scan-console`.
2. Open Claude in that folder and say: *"Follow the setup instructions in CLAUDE.md and onboard me."*

From here, onboarding proceeds exactly as described above.

## The console

Once onboarding finishes, your dashboard lives at `http://localhost:8642/console/`. It has three panels, listed in the left sidebar:

- **Profile** — a read-only view of `profile.md`: target titles, location, salary floor, job type, dealbreakers, and freshness rule. Near the bottom, a collapsible **Scoring rubric** section shows exactly how your fit scores get calculated.
- **Job boards** — shows Indeed as **Connected**. Other boards are listed too, marked **Coming soon** — they're not wired up yet.
- **Reports** — a dropdown picker over every scan you've run, each one shown as a table of matches.

Everything here is read-only. There's no in-app editing — to change anything, you ask Claude in a session, and the console picks up the updated file the next time you click **Refresh** (top right). A **Run scan** button is there too, but clicking it just explains this same thing: the console can't execute a scan itself, because scanning only happens inside a Claude session.

![Welcome panel with three numbered setup steps and a copy-paste prompt](docs/images/welcome.png)
*Sample screen — if you ever open the console before onboarding is finished, this Welcome panel appears with its own copy-paste prompt and a Copy button. Use that one instead of the prompt above — by this point the repo is already on your machine, so it skips the download step.*

## Running scans and reading fit scores

Ask Claude, in a session opened in `job-scan-console`: `/scan-jobs`

You can also paste specific job postings or links in the same message — Claude scores those alongside the automatic Indeed search, using the same rubric.

> You'll see: after the scan finishes, a short chat summary — how many results it found, the top few by score, and the file path of the new report. Claude won't dump the whole report into the chat; the file itself is the artifact.

Claude writes one new report per run into `reports/`, named for the date and time. Each entry lists the job title and company, location, salary (or "not listed" if the posting doesn't show one), a fit score, a one-line "Why," and a real apply link.

Every job is scored out of 10, built from three parts:

- **Title match (0–4)** — how closely the role matches one of your target titles
- **Substance (0–4)** — how well the actual work matches your background; this dimension is personalized to you during onboarding, built from your resume
- **Logistics (0–2)** — how cleanly location and salary line up with no friction, versus things like a hybrid requirement or a salary band that straddles your floor

Only jobs scoring 6/10 or higher make it into the report, and each report is capped at 10 results. The "Why" line always carries the breakdown, so you can see exactly how a score adds up — something like *(title 4 · substance 3 · logistics 2)*.

After your first scan, Claude will offer to record a few real results as **Calibration anchors** in your rubric — short examples like "Shoply Product Designer: 4+3+2 = 9" — so future scans stay consistent with how you actually judged the results.

![Reports panel with a fit-score table and an expanded rationale row](docs/images/reports.png)
*Sample report — "Shoply" and "Meridian Health" are fictional test-fixture companies, not real employers.*

## Changing your profile

Your profile isn't a settings page you edit directly — you just tell Claude what to change, in a session opened in `job-scan-console`. For example:

- *"Raise my salary floor to $95K"*
- *"Add Product Owner to my target titles"*
- *"Switch me to remote only"*

Claude edits `profile.md` directly, and the next scan (or console refresh) reflects the change right away. Resume edits work the same way — ask Claude to update `resume.md` and it will.

## Automatic daily scans (optional)

If you'd rather not remember to run `/scan-jobs` yourself, ask Claude: *"Schedule a daily morning job scan."* From then on, a fresh report lands in `reports/` each morning the Claude app is open at scan time. (Laptop was closed? Just ask for a scan manually.)

Scheduled runs follow the same rule as manual ones: they never invent results. If the Indeed connector isn't available when a scheduled scan tries to run, the report says so plainly instead of pretending to have found something.

## Troubleshooting

| Problem | What to do |
|---|---|
| Scan says the Indeed connector is unavailable | Add the Indeed connector in Claude's settings, then re-run the scan |
| Console shows the Welcome panel, but you already onboarded | `profile.md` is missing or got moved — ask Claude to check |
| Console won't load / connection refused | Ask Claude to "start the job scan console server" |
| You opened `index.html` directly and the page looks broken | It needs to be served over HTTP, not opened as a file — ask Claude to start the server |
| Claude asks permission to run a command | Normal — click **Allow** |
| A report exists but the console doesn't show it | Click **Refresh** (top right) |

## Updating

Ask Claude: *"Pull the latest job-scan-console."* Your `profile.md`, `resume.md`, and everything in `reports/` are gitignored, so updates never touch them — you get the newest skill and console code with all your personal data left exactly as it was.

## Privacy

Your resume, profile, and reports live only on your machine. They're gitignored, so there's no way for them to be committed or pushed anywhere — by you or anyone else. The only thing that ever leaves your machine is the job search itself, and that goes through your own Claude account's Indeed connector, not through this repo.
