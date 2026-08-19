---
name: apply
description: Build the full apply package (job post, company research, tailored résumé, honesty-checked claims ledger, gap analysis, tracker notes) for one or more jobs the user picked from a scan report. Gated by a manifest the user must approve before anything is written. Use when the user says "/apply", names a company or job to apply to, asks to build an application package, or wants to re-lint an existing package's claims.
---

# /apply

Build `applications/<Company>-<Full-Role-Title>/` for a job the user has already chosen from a
`reports/*.md` scan. Full design rationale: `docs/apply-package-spec.md`. All paths below are relative to
the `job-scan-console` folder (the folder containing this skill's `.claude/`), except where noted.

**Nothing is created until the user approves the manifest in step 3.** Not a folder, not one file.

## 1. Resolve the job(s)

Read every file in `reports/`, not just the newest — the console lets the user browse older reports,
and they may be acting on something from last week.

- **`/apply <text>`** — match `<text>` against company names (and role title, if given) across all
  report entries, case-insensitive substring match. A bare string that isn't cleanly one or the other
  (`/apply Capital One Shopping` could be a company or a product-line role name) is matched jointly
  against **both** the company name and the role title for every entry — a hit on either field counts
  as a match, so a string that only names the product line still resolves against the listing whose
  title carries it.
  - **Exactly one match:** proceed with it.
  - **Zero matches:** say so, ask for the exact company/role, or offer the numbered list below.
  - **More than one match** — same company in two different reports, or twice in one report (a
    reposting, or two roles at the same company) — **ask**. Show each candidate with its report
    filename, role title, and fit score, and wait for the user to pick. Accept a number, a name, or
    "both"/"all" if they want every candidate built. Never guess between them.
- **`/apply` with no argument** — print a numbered list of every entry in the *newest* report only
  (company, role, fit score) and ask which one(s). Do not search older reports for this case; that's
  what naming a company is for.
- **Batching is explicit enumeration only** — `/apply Acme, Globex, Initech`. Resolve each name
  independently through the same rules above (each may hit its own ambiguity and need its own ask).
  There is no other batch mechanism: the console's Queue panel is `localStorage`, entirely
  browser-local, and this session cannot read it.
- **If the user says something like "process my queue" or "do the ones I queued"** — this is the
  trap case. Say plainly, in these words or close to them: *"I can't see the console's Queue panel —
  it's stored in your browser, not in a file I can read."* Then immediately show the numbered list
  from the newest report (per the no-argument case above) so they can name the jobs explicitly.
  **Never silently substitute a different set of jobs** — not "the top N by fit," not "everything in
  the newest report," nothing the user didn't actually name.

Once resolved, each job carries: company, role title (as printed in its report entry — this is the
title `/scan-jobs` pulled from the real listing, treat it as "posted"), fit score, and source report
filename. Keep these; they populate the manifest in step 3.

## 2. Migration check — `facts.md`

`facts.md` is the fact registry the honesty checks run against. It lives **at the repo root**,
beside `profile.md` — not in `applications/`, not beside `resume.md`. `resume.md` itself lives in the
**parent folder** (the Claude-Workshop folder, one level above this repo), per this repo's `CLAUDE.md`
onboarding — read it from there, not from the repo root.

Do this **once per `/apply` invocation**, before the manifest, regardless of how many jobs were
resolved in step 1 — the registry isn't job-specific.

**If `facts.md` already exists**, skip to step 3.

**If it's missing** (pre-v0.8 user who onboarded before this feature existed):

1. Tell the user you don't see a fact registry yet and you'll build one now, before building anything
   else — this has to happen first because part of it is an interview, and starting an interview
   after they've already approved a manifest breaks the "approve, then build" contract.
2. If `facts.md` is not already listed in `.gitignore`, add the line before writing anything to it —
   this file will hold personal career data.
3. Read `resume.md`. Extract every number, title, date range, and credential into candidate rows:
   `id` (`F1`, `F2`, …), `kind` (`metric` / `title` / `date` / `credential` / `deliverable`), `value`
   (the extracted fact), `source_text` (the **verbatim** line or sentence from `resume.md` it came
   from — copy it exactly, don't paraphrase), `provenance` (`résumé`).
4. Show the user the full extracted table and ask them to confirm it. Because `source_text` is a
   verbatim quote, this is a diff against their own document, not a comprehension test — they're
   checking "did you copy this right," not "is this true." Fix anything they flag before writing.
5. Write the confirmed rows to `facts.md` at the repo root as a markdown table:
   `| id | kind | value | source_text | provenance |`.
6. **Reservoir questions — skippable.** Ask 3–4 questions aimed at accomplishments that aren't on the
   résumé: *"What have you shipped, fixed, or led that isn't written down here? Anything from before
   this résumé, or too small to have made the cut?"* This matters most for career-changers, whose
   résumés are written for the field they're leaving and systematically omit transferable evidence.
   If the user wants to skip this, that's fine — say plainly that `facts.md` will be résumé-only for
   now (every row `provenance: résumé`), and that they can add reservoir facts later by asking to
   re-run this step.
   - For each reservoir answer, append a row: `kind` from context, `value` the fact, `source_text`
     empty (nothing to quote — it was typed into chat, not extracted from a document), `provenance:
     self-reported`.
   - **One-time attestation offer.** For each self-reported row just captured, ask: *"Do you stand
     behind that and could defend it in an interview? If so I'll mark it attested — otherwise it'll
     show up as a WARN (not an error) wherever it's used, just as a reminder."* If yes, set
     `provenance: attested` instead of `self-reported`. This is per-fact and happens once; it exists
     so a thin registry doesn't turn every future lint into a wall of ignorable WARNs.
7. **Thin registry.** If extraction produced very few quantified facts (metrics, dated ranges,
   credentials) and the reservoir was skipped or came back sparse, say so now, before the manifest:
   tailoring will have little to draw on, and the résumé will mostly restate what's already there.
   Better to set that expectation than let the writer invent its way to a fuller page.

## 3. The manifest gate

Print, for every resolved job, in one message:

```
1. Acme Corp — Senior Product Manager        Fit 8/10   (reports/2026-08-10-1400.md)
   → applications/Acme-Corp-Senior-Product-Manager/
   Files: job-post.md, company-context.md, tailored-resume.md, lint-report.md,
          gap-analysis.md, notes.md
   Research budget: ~5 fetches (company-context.md) + 1 job-post fetch (not counted) + 3 tracer subagents

2. Globex — Staff Product Manager            Fit 7/10   (reports/2026-08-01-0900.md)
   → applications/Globex-Staff-Product-Manager/
   Files: job-post.md, company-context.md, tailored-resume.md, lint-report.md,
          gap-analysis.md, notes.md
   Research budget: ~5 fetches (company-context.md) + 1 job-post fetch (not counted) + 3 tracer subagents

Total: 2 jobs, ~10 research fetches, 6 tracer subagents.

Reply "go" to build all of these, or "go, skip globex" to build a subset.
```

For a single resolved job, print just that one numbered entry — same header, folder path, Files
line, and Research budget line as above — and still close with the `Total:` line and a reply prompt
scoped to one job, e.g.:

```
Total: 1 job, ~5 research fetches, 3 tracer subagents.

Reply "go" to build it.
```

The `Total:` line is never optional, batch or not — see below.

Always include that total line — for a real batch it's the whole point of the gate: a ten-job batch
is ~50 research fetches and thirty tracer subagents under one approval, and the per-job lines
shouldn't make the user do that arithmetic themselves.

**Wait for one reply.** Nothing downstream — no folder, no file, no fetch — runs before it arrives.
The reply grammar is `go`, optionally with per-job `skip <name>` clauses in the same message. There
are no depth tiers to override (every job gets the full package — see `docs/apply-package-spec.md`
§4); this gate is the only cost control there is. **A reply already given counts.** If the message
that invoked `/apply` already carried an explicit `go` alongside the job names (e.g. `/apply Acme,
go`), that reply already exists — print the manifest anyway, for the record, then proceed without
asking a second time. Short of an approval actually present in that invoking message, nothing here
changes: an agent must never read approval into an ambiguous message, prior context, or its own sense
that the user is probably fine with it — only a reply the user actually gave counts.

## 4. Build, per approved job

Do the following **in this exact order** for each job that wasn't skipped:
`job-post.md` → `company-context.md` → `tailored-resume.md` → **tracer + lint** → `gap-analysis.md` →
seed `notes.md`. The résumé is built before the gap analysis on purpose — the gap analysis reports on
a finished package instead of steering it, so it reads as advice to the user, not as generator
machinery talking to itself.

**Slug.** `<Company>-<Full-Role-Title>`: the company name and the job's title (from step 1), each
proper-cased, spaces and punctuation replaced with single hyphens (e.g. `Humana-Lead-AI-Technical-Product-Manager`).
No role-type abbreviation — this repo has no controlled vocabulary of role tags, and inventing one
wouldn't generalize past product-management careers.

**Punctuation.** Replace every run of whitespace or punctuation (commas, slashes, parentheses,
ampersands, existing hyphens included) with a single hyphen, then collapse any resulting run of
multiple hyphens into one and strip leading/trailing hyphens. Parenthesized qualifiers keep their
contents, just unwrapped: `(Remote-Eligible)` becomes part of the hyphen run, not a dropped chunk.

**De-dup.** Branded product lines (Capital One Shopping, Capital One Travel, Google AI, …) put the
company name a second time *inside the posted role title* — applied literally, the rule above
produces `Capital-One-Product-Manager-Capital-One-Shopping-Remote-Eligible`, the company name twice.
If the company name already appears in the role title, don't repeat it: slugify the title first,
remove the chunk matching the company's own slug from within it (case-insensitive), then prefix with
the company once. Worked example — company `Capital One`, title `Product Manager, Capital One
Shopping (Remote-Eligible)`: title alone slugifies to
`Product-Manager-Capital-One-Shopping-Remote-Eligible`; strip the embedded `Capital-One` chunk to get
`Product-Manager-Shopping-Remote-Eligible`; prefix with the company once for
`Capital-One-Product-Manager-Shopping-Remote-Eligible`.

**Collision rule.** If `applications/<slug>/` already exists:
- If it has an `INCOMPLETE` marker at the top of its `notes.md`, **resume into it** — see below —
  rather than making a sibling. This is a package that didn't finish, not a second pursuit of the
  same job.
- Otherwise, append the lowest free integer suffix: `-2`, then `-3`. Never write into an existing
  finished folder. Silently overwriting a package the user has since edited is the worst failure this
  feature can have.

**Atomicity and the `INCOMPLETE` marker.** If a batch is interrupted partway (an error, the user
stopping it, the session ending), completed folders stand as-is; a folder that didn't finish needs to
say so. Concretely: as the **first** action after the manifest is approved for a given job — before
`job-post.md` — create the folder and write a minimal `notes.md` whose first line is
`**INCOMPLETE** — build in progress`, followed by the header block (company/role/source_report/fit)
filled in with what's already known. Build normally from there. The **true last step** of a
successful build overwrites that same `notes.md` with the real seed content (see 4.6) and drops the
marker. If a later `/apply` run resolves to a job whose folder still carries the marker, resume by
checking which of the six files already exist and continuing from the first one that's missing,
rather than restarting from `job-post.md`.

### 4.1 `job-post.md`

Source, in this order, and stop at the first that works:
1. Resolve the job ID. The report entry doesn't carry an explicit job-ID field, and in practice the
   `**Apply:**` URL is a shortlink (`https://to.indeed.com/<token>`) with no ID visible in it at all
   — the ID only appears after the shortlink is resolved (follow the redirect), which typically lands
   on an `indeed.com/rc/clk` or `/uie/clk` tracking URL carrying the listing ID as a `jk=` parameter.
   Resolve first, then extract `jk=` from the *resolved* URL, not the shortlink.
2. Call `get_job_details` (load it via `ToolSearch`, query "Indeed job search", if not already loaded)
   on that ID. Treat an error here as inconclusive, not proof the ID was wrong — this call has been
   observed to error on IDs that are nonetheless valid, so an error means "move to the next source,"
   not "give up on this job." If it returns a JD, record the provenance line as `provenance: Indeed
   (get_job_details)`.
3. If that didn't produce a JD, `WebFetch` the resolved tracking URL directly (not the original
   shortlink). That URL can carry an encoded query string thousands of characters long — long enough
   that `WebFetch` sometimes refuses it outright with "Invalid URL." If that happens, trim the URL
   down to the bare `jk=` parameter (e.g. `https://www.indeed.com/viewjob?jk=<id>`) and retry once
   before treating this path as failed. If this produces a JD, record the provenance line as
   `provenance: Indeed (<url>)` — the resolved or trimmed tracking URL actually fetched, not the
   original shortlink.
4. If the JD still hasn't been found, search for the posting on the employer's own careers site —
   `WebSearch` company name + role title (e.g. `"Capital One" "Product Manager, Capital One Shopping"
   careers`). Employer career pages are commonly indexed and often carry the full JD, exact
   requirements, and exact salary bands where the Indeed listing had already thinned to a summary.
   If a matching posting turns up, `WebFetch` it and use its content in place of the Indeed JD —
   record the provenance line as `provenance: careers site (<url>)` rather than crediting the Apply
   link, since that's not actually where the content came from.
5. If that also fails (login wall, dead link, blocked fetch, nothing found on the careers site),
   fall back to the report entry alone — title, company, location, salary, the "Why" line — and mark
   the file `provenance: degraded (summary only)`. **Never** invent JD content to fill the gap, and
   never let a dead link stall the whole job — degrade visibly and move on.

Write the JD (or the degraded summary) into `job-post.md`, along with two things: a provenance line in
the format above for whichever source actually produced it, and a separate line citing the source
report and entry number this job was resolved from in step 1. Both lines live inside `job-post.md`
itself; nothing in this step edits `reports/*.md`, which stays exactly as `/scan-jobs` wrote it. This
fetch does not count against the company-research budget below.

### 4.2 `company-context.md`

~5 fetches (`WebSearch` to find pages, `WebFetch` to actually read them; `get_company_data` if the
Indeed connector exposes it and it's loaded) into this fixed template:

```markdown
## What they do
## Size & stage
## Recent news
## Product & tech
## Why this fits you
```

**A URL may only be cited if it was actually fetched during this run.** Never write a citation next
to a plausible-sounding claim you didn't verify this way — a fabricated citation is worse than none,
because it looks checked. If a section turns up nothing after a real attempt, write the section
header followed by the literal text `Not found.` — don't leave it blank (ambiguous) and don't pad it
with generic filler. "Why this fits you" may draw on facts already gathered in the other four
sections plus a comparison against `facts.md`/`profile.md`; it still needs a fetched-this-run URL
behind any *new* factual claim about the company that appears only in that section.

**This covers URLs that arrive inside a tool's response, not just ones found via `WebSearch`.**
`get_company_data` and similar connector calls return structured data that often includes a URL field
(e.g. a company's Indeed profile link) — that URL reads as verified because it came back from a real
tool call, but the tool call didn't *fetch* the page at that URL, it returned a record that happens to
contain a link. Citing it as a source would be the same fabrication this rule exists to prevent, just
laundered through a connector instead of invented outright. If a fact came from a connector response,
credit the tool (e.g. "per Indeed's company data") rather than manufacturing a citation for a URL
nothing in this run actually fetched.

### 4.3 `tailored-resume.md`

Free-text tailoring of `resume.md`'s content against `facts.md`, aimed at this specific JD (from
`job-post.md`). Draw only on facts that exist in the registry — this is a generator that writes new
prose about the user's career from real material, not one that reshuffles existing bullets untouched.

**Generation-time hard rule:** attribution may be **re-worded or generalized**, never **re-credited**.
You may restate "coordinated the launch" as "drove the launch" only if `facts.md` actually backs
"drove"; you may never give the user a role, a decision, or an outcome that no row backs, even when
the JD's language makes that framing obviously more persuasive. This is the one rule the tracer in
4.4 exists to catch violations of — treat it as load-bearing, not stylistic advice.

### 4.4 Tracer + lint → `lint-report.md`

This is the honesty check, and it has two independent parts that both have to land in the same file.

**The tracer (enumerates claims).** A script can reliably flag sentences with numbers, dates, and
credentials in them — it cannot reliably tell "drove product strategy for the platform org" apart
from an invented sentence that merely sounds like the rest of the résumé. So a model has to do the
enumeration, and it has to do it **without the JD in front of it** — otherwise it can rationalize an
invented claim as "well, the posting did ask for that."

**Spawn three independent subagents, not one.** The identical verbatim prompt below, run twice over
near-identical résumé text during this skill's own dry runs, disagreed — 29 claims/7 NO SOURCE versus
22 claims/5 NO SOURCE — and two verdicts flipped in *opposite* directions on claims neither run had
touched. One flip was severe: "end-to-end ownership of a tool build," a claim the registry backs only
as discrete task fragments — exactly the re-crediting the generation-time rule in 4.3 forbids — was
NO SOURCE on one pass and TRACED, i.e. certified, on the other. A single tracer pass is a sample of a
model's judgment, not a verdict, and that specific escalation was observed slipping through a lone
pass. So: spawn three subagents (via the Agent tool), each receiving **only** the contents of
`tailored-resume.md` and `facts.md` — not the job post, not `company-context.md`, not this
conversation, and not each other's output. Paste both files' full contents directly into each
prompt (don't just hand them file paths — a subagent with tool access could go read the JD anyway,
and withholding it is the entire mechanism). All three get the same prompt verbatim, with the two
marked insertions filled in:

```
You are a claims tracer. You will be given two documents: a tailored résumé and a facts registry.
Your only job is to enumerate every career claim in the résumé and mark whether it is backed by a
specific row in the registry.

Do not read, fetch, or ask for any other file, URL, or context. You have not been given the job
posting this résumé was written for, and you must not guess at or reconstruct it. Do not use any tool
to look at other files in this repository or on the web. Judge the résumé only against the registry
text below.

A "claim" is any sentence or bullet-point fragment that asserts something the candidate did,
achieved, held, owned, or is credentialed for — responsibilities, actions, outcomes, metrics, titles,
dates, credentials, and deliverables. Split compound bullets into separate claims where they assert
more than one thing.

For each claim:
- Quote the claim text.
- If a registry row supports it, cite the row's `id` and quote its `value`.
- If no registry row supports it — including if the résumé states or implies a stronger causal role,
  larger scope, or more direct ownership than the row backs — mark it "NO SOURCE".
- A claim can be NO SOURCE even if it reuses words that appear in the registry, if the registry
  doesn't support the specific assertion being made. Example: the registry says "contributed to a
  redesign that shipped" and the résumé says "led the redesign" — that is NO SOURCE, because the
  registry doesn't back "led."

Output a markdown table with columns: Claim | Status (TRACED / NO SOURCE) | Registry row(s). Follow
it with one summary line: total claims, and how many are NO SOURCE.

--- TAILORED RÉSUMÉ ---
{{TAILORED_RESUME_CONTENTS}}

--- FACTS REGISTRY (facts.md) ---
{{FACTS_MD_CONTENTS}}
```

**Combine the three runs by union, not majority.** A claim marked NO SOURCE by *any* of the three
runs is NO SOURCE in the ledger — do not average, and do not require 2-of-3 agreement. The risk this
guards against is a false TRACED slipping through, not a false NO SOURCE; a claim that's actually
fine costs the user a few seconds of re-reading, but a re-credited claim that ships costs them in an
interview. In the ledger, note per claim which of the three runs flagged it (e.g. "NO SOURCE — flagged
by 2/3 runs") — a claim only one run caught is real signal, not noise, but it's visibly weaker
evidence than one all three runs agreed on, and the user should be able to see that difference rather
than have it collapsed into a single flat verdict.

**The script (verifies the numeric subset).** The tracer enumerates; `honesty_lint.py` then
deterministically checks the parts of that enumeration where a script beats judgment — the numbers,
dates, and credentials actually printed in the résumé, against the registry. It does not enumerate
prose claims itself and does not replace the tracer. Run it from the repo root:

```
python3 scripts/honesty_lint.py applications/<slug>/tailored-resume.md --registry facts.md
```

It's a pure passive reporter — never blocks, never edits its input, always exits 0 — and it prints
markdown findings to **stdout**. Capture that output; the script does not write its own report file.

**Write `lint-report.md` now** — this skill is the only writer of that file, at any point it's
touched. Structure:

```markdown
# Lint report — <Company> / <Role>

## Claims ledger (tracer)
<the merged ledger: one row per claim, union-combined across the three runs, each NO SOURCE row
annotated `flagged by N/3 runs` (per 4.4 above) and citing the registry row(s), plus a summary line>

### Per-run tracer tables
<all three subagents' tables + summary lines, verbatim, one after another>

## Lint findings — tailored-resume.md
<the script's captured stdout, verbatim>
```

Both halves land in the file; neither is a chat-only finding. A finding that only appears in chat
evaporates when the session ends, while `lint-report.md` persists as the record the user actually
comes back to and trusts — so anything either check produced has to be in the file, not just
summarized to them in the moment. That includes the disagreement between runs, not just the merged
verdict: a claim one run traced and another flagged NO SOURCE is the highest-value thing this
three-run design produces — the "end-to-end ownership" flip described above is exactly that shape —
and a merged ledger alone hides it behind a single flat annotation. The merged ledger is what a
reader wants first; the per-run tables underneath are what preserve the raw disagreement once the
session that ran the three subagents has ended. This isn't the file's final form: `gap-analysis.md`'s
student-claim section is also honesty-checked (see `docs/apply-package-spec.md` §2's file table), but
it doesn't exist yet at this point in the build order — 4.5 appends its findings to this same file
below.

### 4.5 `gap-analysis.md`

Three sections, in this order. **Each one must be rendered as a `##` ATX heading, with exactly this
text** — not a numbered list item, not bold prose standing alone, not a `###`:

```
## What this job asks for
## What your record evidences
## How to close the gaps, and can you defend them?
```

This isn't a style preference. `honesty_lint.py`'s `--section` flag — used two steps below, on this
same file — matches only ATX headings (`^#{1,6}\s`), and if the heading text it's told to find isn't
present as one, it does **not** fall back to scanning the whole file. It just prints a "not found"
notice and moves on. Write section 2 as a list item instead of a heading (`2. **What your record
evidences**`) and the flag matches nothing, the lint call still exits 0, and the gap-analysis half of
the honesty check has silently done nothing — no error loud enough to notice after the fact. Get the
heading level and text exactly right the first time.

1. **What this job asks for** — the JD's requirements, quoted from `job-post.md`. Not lint-checked —
   these are the JD's words, not the user's claims.
2. **What your record evidences** — each requirement measured **against `facts.md`**, never against
   `tailored-resume.md`'s prose: *meet* / *partially evidence* / *no evidence*, citing the row(s).
   **This is deliberate and load-bearing — do not "simplify" it into checking the résumé instead.**
   If this section audited the résumé's prose, a fabricated bridge in the résumé (say, "led the
   redesign" where the registry only backs "contributed to") would make the résumé *appear* to
   evidence the requirement, and the gap analysis would fall silent exactly where the user needs it
   most. Measuring against the registry instead means that same fabricated bridge shows up as a
   visible contradiction: the résumé claims it, the gap analysis says the registry doesn't back it.
   This section's claims are in lint scope — see the step below, right after this file is written.
   **Keep any summary tally out of this section.** A line like "Tally: 1 meets, 5 partially evidence,
   7 no evidence" is meta-commentary about the analysis, not a claim about the user — but it lives
   inside the lint-scoped section, the script reads "1", "5", and "7" as unbacked numeric claims, and
   throws a zero-source ERROR on each. A tally is genuinely useful to a reader; it just belongs
   **outside** the lint-scoped section — fold it into section 3 below, or place it above section 1's
   heading — because only the numbers inside section 2 get checked against the fact registry.
3. **How to close the gaps, and can you defend them?** — concrete, honest next actions for the real
   gaps, closing with: *"You will be asked to back these claims in an interview. Can you, out loud,
   right now?"* This is the point where an invisible risk becomes a rehearsal task — nothing in this
   package can verify that a technically-traceable claim isn't still overstated ("owned the roadmap,"
   backed by a row that says "coordinated sprint planning," passes every check here and can still
   fail an interview). The user's judgment is the last gate, and this line is where the skill has to
   say so plainly rather than let a clean lint read as "verified."

**Lint `gap-analysis.md` and fold it into `lint-report.md`.** The file table in
`docs/apply-package-spec.md` §2 marks `gap-analysis.md` honesty-checked (student-claim section only),
but the generation order puts "tracer + lint" before this file is written — so the check on *this*
file's claims has to happen here, immediately after it's written, not back in 4.4:

```
python3 scripts/honesty_lint.py applications/<slug>/gap-analysis.md --registry facts.md --section "What your record evidences"
```

Append the captured stdout to the `lint-report.md` written in 4.4 as a new section:

```markdown
## Lint findings — gap-analysis.md
<the script's captured stdout, verbatim>
```

Only "what your record evidences" is in scope here — the script itself is expected to skip the
JD-derived "what this job asks for" section per `docs/apply-package-spec.md` §5.5. After this,
`lint-report.md` covers both claim-bearing files in the package, matching the file table.

### 4.6 Seed `notes.md`

Overwrite the placeholder `notes.md` from earlier in this build (dropping the `INCOMPLETE` marker)
with the real header block and an empty dated log below it:

```markdown
company: <Company>
role: <Role>
source_report: reports/<file>.md
fit: <N>/10
folder_created: <YYYY-MM-DD>
status: built

---

## <YYYY-MM-DD>
Package built via /apply.
```

`status` moves through `built` / `applied` / `interviewing` / `rejected` / `offer` by hand — this
file is edited directly by the user going forward ("recruiter called Tuesday"), never regenerated
wholesale and never treated as structured data beyond that header block.

## 5. Re-lint (standalone)

A user who edits `tailored-resume.md` after reading the ledger needs to re-verify it without
rebuilding the package. Trigger this when the user asks to re-check, re-lint, or re-verify an
existing application folder (e.g. "relint Acme," "re-check the Globex package").

1. Resolve the folder against `applications/*` (by company/role match, same ask-on-ambiguity rule as
   step 1) — **not** against `reports/`, since this operates on a package that already exists.
2. Re-run the tracer (4.4) on the **current** `tailored-resume.md` + `facts.md` — same prompt, same
   isolation, three fresh subagents, same union-of-NO-SOURCE combination.
3. Re-run the script over whichever of the two claim-bearing materials actually exist in the folder —
   normally both, but an `INCOMPLETE` folder or one built before this skill folded gap-analysis
   findings into 4.5 may only have `tailored-resume.md`. Pass only what's present; the script exits
   non-zero on a missing material, so don't hand it a path that isn't there:
   ```
   python3 scripts/honesty_lint.py applications/<slug>/tailored-resume.md --registry facts.md
   python3 scripts/honesty_lint.py applications/<slug>/gap-analysis.md --registry facts.md --section "What your record evidences"

   Two separate calls, not one. `--section` applies to *every* material passed in a single
   invocation, so linting both files together would either scope the résumé (wrong — the whole
   résumé is in scope) or leave the gap analysis unscoped (wrong — its JD-requirements section
   would ERROR on every quoted figure). Run whichever materials exist; skip a file that's absent.
   ```
   (`gap-analysis.md`'s "what this job asks for" section is JD-derived and stays out of lint scope;
   only "what your record evidences" is in scope, matching `docs/apply-package-spec.md` §5.5.)
4. Overwrite `lint-report.md` with the fresh ledger + findings, same structure as 4.4. This is **not**
   a rebuild — it doesn't touch any other file in the folder, and it never triggers the `-2` collision
   suffix.
5. Report the new ERROR/WARN counts and the ledger's NO SOURCE count, and note anything that flipped
   since the last lint (newly traced, newly untraceable). **A flip doesn't necessarily mean the
   document changed** — the tracer is three model passes, not a deterministic check, so a claim can
   flip between two lint runs over *identical* `tailored-resume.md` content purely from run-to-run
   variance. Report a flip either way, but don't imply the file changed if it didn't, and treat a
   claim that flips between runs as deserving **more** scrutiny than one that traces the same way
   every time — instability in the verdict is itself signal, not noise to explain away.

## 6. Wrap-up

After a build (or a batch), report per job:

- Files written (or, for a resumed `INCOMPLETE` build, files completed this run).
- Claims ledger: total claims / NO SOURCE count.
- Lint: ERROR count / WARN count.
- The tracer's most notable finding, if any (e.g. a claim that reads as overstated even if traced).
- The biggest gap from `gap-analysis.md`'s section 2.

Then say, plainly, once per session rather than per job: **passing the lint and the tracer is not the
same as a claim being true** — both check traceability to `facts.md`, not whether the underlying
fact is accurately represented or whether the user can defend it. Add, in the same breath: **the
claims ledger is a sample of a model's judgment, not a verdict** — three independent tracer passes
were combined precisely because a single pass was observed to certify a re-credited claim
("end-to-end ownership" of work the registry backs only as fragments) that a second pass on the same
material caught. Agreement across all three runs is stronger evidence than a flag from just one, but
none of it is proof. Encourage them to read `lint-report.md` and `gap-analysis.md` and cut anything
they can't say out loud in an interview before they send the package.

## Out of scope

No depth tiers — every approved job gets the full package; the manifest gate is the only cost
control. No console changes (the console doesn't read `applications/` in this version). No cover
letters, outreach drafts, or a reviewer pass — none of that is part of this build. No wiring the
console's Queue panel into `/apply` — it's `localStorage` and this session cannot read it; naming
jobs explicitly is the only input path for now.
