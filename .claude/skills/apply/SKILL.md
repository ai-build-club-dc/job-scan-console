---
name: apply
description: Build the full apply package (job post, company research, tailored résumé, honesty-checked claims ledger, gap analysis, tracker notes) for one or more jobs the user picked from a scan report, or for a job-post URL they paste. Gated by a manifest the user must approve before anything is written. Use when the user says "/apply", names a company or job to apply to, pastes a link to a job posting they found online, asks to build an application package, or wants to re-lint an existing package's claims.
---

# /apply

Build `applications/<Company>-<Full-Role-Title>/` for a job the user has already chosen from a
`reports/*.md` scan. Full design rationale: `docs/apply-package-spec.md`. All paths below are relative to
the `job-scan-console` folder (the folder containing this skill's `.claude/`), except where noted.

**Nothing is created until the user approves the manifest in step 3.** Not a folder, not one file.

## 1. Resolve the job(s)

- **`/apply <url>`** — if the argument begins `http://` or `https://`, it is a URL, not a search
  string. **Skip straight to this bullet without reading `reports/` first** — none of the
  report-matching logic in this step applies to a job that never came from a report, including the
  "read every file in `reports/`" instruction that opens the next bullet, so reading the whole
  `reports/` folder for a URL invocation is pure wasted motion. Do not substring-match it against
  `reports/` entries, and don't fall through to the ambiguity rules below. Fetch it (this is
  the one pre-gate fetch the manifest gate in step 3 makes room for) and extract **company** and **role
  title** from the job description. If either can't be determined confidently, **ask** rather than
  guess — the same reasoning that sends two ambiguous text matches to the user instead of a coin flip
  applies here too, and a guessed company name silently produces a wrong folder slug with no report
  entry downstream to catch it.

  If the fetch itself fails, there's no report summary to degrade to the way a scan-sourced job can
  (step 4.1's chain), because there's no report entry at all to fall back on — but *how* it failed
  determines what to ask for next, since a page the student can't get past and a page that's gone
  aren't the same problem and don't call for the same ask:

  - **Blocked, behind a login wall, or timed out** — the student likely has access even though this
    session doesn't. Say the fetch failed and why, then ask the student to paste the posting text into
    chat. This isn't a rare edge case — LinkedIn and Workday, between them a large share of where
    students actually find jobs, sit behind login walls or render via JS, so this is the common case,
    not the exception.
  - **404, or otherwise clearly gone** — the listing itself may no longer exist, and asking the student
    to paste text they may not have is the wrong ask. Say plainly that the listing looks dead, and ask
    whether they have another link to the same posting or a saved copy (an email, a screenshot, a
    cached page) instead of asking them to paste text.

  Either way, if the student comes back with usable text, build normally from what they gave you and
  record `provenance: user-pasted (<url>)` in `job-post.md` — the JD is still real, only its delivery
  route changed. If they decline, or simply have nothing to give, **abort cleanly**: nothing written,
  no folder. Never build a package from a page that yielded nothing; a near-empty `job-post.md`
  produces a hollow gap analysis while inviting the tailoring step to fill the space with invention
  instead of fact.

  **Exactly one URL per invocation.** Don't mix a URL with company names, and don't accept more than
  one URL in the same call. This isn't arbitrary: the batching rule below splits `/apply Acme, Globex`
  on commas, and a URL can legally contain a comma inside its own query string — so comma-splitting a
  pasted URL is a silent-corruption bug, not a loud one, and the student ends up with a package built
  from a mangled link and no error telling them why. One URL at a time removes the ambiguity entirely.
  Revisit this only by adding a real tokenizer that recognizes URLs before it ever splits on commas —
  never by loosening the split itself.

  A resolved URL job carries **company**, **role title** (both extracted), `fit: unscored`, and
  `source: <url>` — in place of the fit score and source-report filename a scan-resolved job carries.
  Keep these; they populate the manifest in step 3 the same way.
- **`/apply <text>`** — first, read every file in `reports/`, not just the newest: the console lets
  the user browse older reports, and they may be acting on something from last week. Then match
  `<text>` against company names (and role title, if given) across all report entries,
  case-insensitive substring match. A bare string that isn't cleanly one or the other
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
filename. Keep these; they populate the manifest in step 3. (A URL-resolved job carries the four-field
contract given above instead — `fit: unscored` and `source: <url>` in place of the fit score and
report filename.)

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
   Research budget: ~5 fetches (company-context.md) + 1 job-post fetch (not counted) + 1 tracer subagent

2. Globex — Staff Product Manager            Fit 7/10   (reports/2026-08-01-0900.md)
   → applications/Globex-Staff-Product-Manager/
   Files: job-post.md, company-context.md, tailored-resume.md, lint-report.md,
          gap-analysis.md, notes.md
   Research budget: ~5 fetches (company-context.md) + 1 job-post fetch (not counted) + 1 tracer subagent

Total: 2 jobs, ~10 research fetches, 2 tracer subagents.

Reply "go" to build all of these, or "go, skip globex" to build a subset.
```

For a single resolved job, print just that one numbered entry — same header, folder path, Files
line, and Research budget line as above — and still close with the `Total:` line and a reply prompt
scoped to one job, e.g.:

```
Total: 1 job, ~5 research fetches, 1 tracer subagent.

Reply "go" to build it.
```

The `Total:` line is never optional, batch or not — see below.

Always include that total line — for a real batch it's the whole point of the gate: a ten-job batch
is ~50 research fetches and ten tracer subagents under one approval, and the per-job lines
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

**URL mode changes what may precede the gate, not the gate itself.** The rule above — nothing
downstream, no folder, no file, no fetch, runs before the reply arrives — has exactly one carve-out,
and it exists only because a manifest for a pasted URL cannot name the job without it:

> No folder and no file is created before approval. Ever. That part does not change.
> In URL mode only, ONE fetch — of the pasted URL itself — may precede the gate, because the
> manifest cannot name the job otherwise. No company research, no second fetch, nothing written.

This preserves the rule's purpose rather than eroding it. The gate exists to stop expensive work and
unwanted files from happening before the user has said yes, and this one fetch does neither: it writes
nothing to disk, and it was already exempt from the company-research budget (see step 4.1 — "This
fetch does not count against the company-research budget"). What it buys in return is real: the
manifest can show the *company and role the fetch actually extracted*, so a bad extraction or a
mis-pasted link gets caught while nothing has been built yet, instead of discovered after the fact.

State the risk plainly, because it's real and not hypothetical: this is the first exception to the
strongest sentence in this skill, and exceptions attract more exceptions. Any future proposal to widen
this one — a second fetch, a bit of company research squeezed in before approval, anything — is a
redesign of the gate, not a tweak, and should be treated with that much scrutiny.

For a URL-resolved job, the manifest entry carries the amended shape:

```
1. Acme Corp — Senior Product Manager        Fit: unscored (URL-sourced)
   source: https://boards.greenhouse.io/acme/jobs/12345
   → applications/Acme-Corp-Senior-Product-Manager/
   Files: job-post.md, company-context.md, tailored-resume.md, lint-report.md,
          gap-analysis.md, notes.md
   Research budget: ~5 fetches (company-context.md) + 1 tracer subagent

Total: 1 job, ~5 research fetches, 1 tracer subagent.
```

The job-post fetch isn't listed as pending research here — per the carve-out above, it already
happened before this manifest was printed, and listing it as pending would misrepresent what's left to
do. The `Total:` line still always appears, exactly as it does for a scan-sourced build.

**"URL-sourced" is deliberately neutral, not a placeholder for "fetched successfully."** §4.1 draws a
sharp line between `provenance: user-supplied URL (<url>)` (the fetch worked) and `provenance:
user-pasted (<url>)` (it didn't, and the student pasted the text instead) — that distinction matters
and belongs in `job-post.md`, which is built to carry it precisely. It doesn't need a second home in
the manifest: printing "(user-supplied URL)" here would be wrong on every job where the fetch failed
and the student had to paste, which is not a rare outcome (see step 1). "URL-sourced" is true in both
cases, so the manifest label never has to track which one actually happened — it just says the job
came from a URL, and `job-post.md`'s provenance line is where the fetched-vs-pasted distinction lives.

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

**For a URL-resolved job, none of the chain below runs.** There's no `**Apply:**` shortlink and no
`jk=` to resolve, because this job never came from a report entry — it came from the fetch already
done in step 1. Write the JD fetched there directly into `job-post.md`, with a provenance line of
`provenance: user-supplied URL (<url>)`, or `provenance: user-pasted (<url>)` if that fetch failed and
the student pasted the text instead. The shortlink chain immediately below — and the citation
instruction that closes out this section — applies only to scan-sourced jobs; a URL-resolved job runs
neither. Everything from `company-context.md` onward is unchanged and applies the same way regardless
of which mode built this job.

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

**This "cite the source report and entry number" instruction is scan-sourced only** — it names a
report entry, and a URL-resolved job doesn't have one to name. Don't improvise a substitute `source:`
line for it. For a URL-resolved job, `job-post.md` carries only the provenance line already specified
above (`provenance: user-supplied URL (<url>)` or `provenance: user-pasted (<url>)`) — that line
already embeds the URL this job came from, so there's nothing left to cite and no report-and-entry-
number line to add.

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

**There's a middle case between "cite it" and "leave it out": a claim seen in a `WebSearch` snippet
but never fetched.** The rule above is binary — fetched-this-run gets a citation, nothing gets `Not
found.` — and a real, plausible claim that only ever showed up in a search result doesn't fit either
box: it's too specific to invent a citation for, and dropping a true claim just because nothing here
licenses citing it throws away real signal. Don't hedge it into vague prose to paper over the gap
either. Instead, state it plainly and mark it explicitly as unverified, with no citation attached —
e.g. "unverified, from search results only: [claim]." The label carries the caveat instead of a URL.
What's still off the table, unchanged, is writing it as though a source backed it: no link, no "per
[company]," nothing that reads as checked when it wasn't. The hard rule above still stands — a
fabricated citation is worse than none.

**The fetched-this-run citation rule covers URLs that arrive inside a tool's response too, not just
ones found via `WebSearch`.**
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

**This file contains the résumé, and nothing else** — no HTML comments, no working notes, because
`honesty_lint.py` has no comment awareness and scans every line as résumé content, silently inflating
the findings it reports.

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

**Spawn one subagent.** The identical verbatim prompt below, run twice over near-identical résumé
text during this skill's own dry runs, disagreed — 29 claims/7 NO SOURCE versus 22 claims/5 NO
SOURCE — and two verdicts flipped in *opposite* directions on claims neither run had touched. One
flip was severe: "end-to-end ownership of a tool build," a claim the registry backs only as discrete
task fragments — exactly the re-crediting the generation-time rule in 4.3 forbids — was NO SOURCE on
one pass and TRACED, i.e. certified, on the other. A later run saw the same instability on "a track
record of turning an operational need into a shipped, adopted tool": NO SOURCE on one pass, TRACED on
another, split across a third. A single tracer pass is a sample of a model's judgment, not a verdict,
and both of those escalations were observed slipping through a lone pass — that risk doesn't go away
just because this skill now runs only one pass; it's the reason the ledger has to be read as a sample,
never a certification (§6 says this to the user directly). Spawning three subagents and combining
their NO SOURCE sets by union was tried and reverted: subagent spawn overhead runs roughly 50k tokens
each regardless of payload size, so three tracers cost ~150k tokens per job, and a ten-job batch
carried ~1M tokens of overhead for a check the user was already going to make by reading the tailored
résumé. So: spawn one subagent (via the Agent tool), giving it **only** the contents of
`tailored-resume.md` and `facts.md` — not the job post, not `company-context.md`, not this
conversation. Paste both files' full contents directly into the prompt (don't just hand it file
paths — a subagent with tool access could go read the JD anyway, and withholding it is the entire
mechanism). Fill in the two marked insertions verbatim:

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
<the tracer's table, citing the registry row(s) per claim, plus its summary line, pasted verbatim>

## Lint findings — tailored-resume.md
<the script's captured stdout, verbatim>
```

Both halves land in the file; neither is a chat-only finding. A finding that only appears in chat
evaporates when the session ends, while `lint-report.md` persists as the record the user actually
comes back to and trusts — so anything either check produced has to be in the file, not just
summarized to them in the moment. With a single tracer pass, that file is the only sample of the
model's judgment the user gets — there's no second run's table on disk to check it against, the way
there was when this skill spawned three. That's exactly why §6's wrap-up leans on telling the user to
read this file line by line rather than trust a clean count in it. This isn't the file's final form:
`gap-analysis.md`'s
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

1. **What this job asks for** — the JD's requirements, quoted from `job-post.md`, each one **numbered**
   as it's listed (`R1`, `R2`, `R3`, …). Not lint-checked — these are the JD's words, not the user's
   claims. The numbering exists so section 2 can point back at a requirement without repeating it —
   see below.
2. **What your record evidences** — for each requirement, **reference its identifier from section 1
   (`R1`, `R2`, …) — do not restate the requirement's text.** Measure it **against `facts.md`**, never
   against `tailored-resume.md`'s prose: *meet* / *partially evidence* / *no evidence*, citing the
   row(s), e.g. `R1 — meet (F4, F7)`.
   **This is deliberate and load-bearing — do not "simplify" it into checking the résumé instead.**
   If this section audited the résumé's prose, a
   fabricated bridge in the résumé (say, "led the redesign" where the registry only backs "contributed
   to") would make the résumé *appear* to evidence the requirement, and the gap analysis would fall
   silent exactly where the user needs it most. Measuring against the registry instead means that same
   fabricated bridge shows up as a visible contradiction: the résumé claims it, the gap analysis says
   the registry doesn't back it. This section's claims are in lint scope — see the step below, right
   after this file is written.
   **Referencing by identifier instead of restating is what keeps that lint scope clean, not just
   tidy.** A requirement's own numbers ("2+ years...", "3+ years...") belong to the JD, not to the
   user — but a natural write-up of this section restates the requirement to say whether it's met,
   which drags the JD's numerals into the same lint-scoped section as the user's own claims. The lint
   script can't tell a JD-derived "2" from a résumé-derived one; it flags both as unbacked numeric
   claims. Early dry runs of this skill missed the bug because the JD's number happened to also appear
   in the registry by coincidence (a "3+ years" requirement against a registry row reading "Managed 3
   education programs") — any JD whose requirement numbers don't happen to reuse the registry's own
   numbers throws false ERRORs on the JD's words, not the user's. Pointing at `R1` instead of quoting
   "2+ years in a product, program, or operations role" removes the JD's language from this section
   entirely, so the only numbers left in lint scope are the ones the user's own record adds — row
   citations like `F4`/`F7` aren't numeric claims, they're identifiers, and citing rows inside this
   section is already normal practice that the lint has never had trouble with. This also removes the
   duplication of requirement text between sections 1 and 2 — a side benefit, not the point.
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
JD-derived "what this job asks for" section per `docs/apply-package-spec.md` §5.5. The `--section`
scoping is now a second line of defense rather than the only one: because section 2 references
requirement IDs instead of restating the JD's own numbers (see section 2 above), there's no JD-derived
numeral for the scoping to need to exclude in the first place. After this, `lint-report.md` covers both
claim-bearing files in the package, matching the file table.

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

For a URL-resolved job, two keys change: `source_report:` is replaced with `source: <url>`, and
`fit:` carries the literal `unscored` rather than a score. Both keys stay present either way, just
under different names — so the header block keeps the same shape regardless of which mode built it:

```markdown
company: <Company>
role: <Role>
source: <url>
fit: unscored
folder_created: <YYYY-MM-DD>
status: built
```

## 5. Re-lint (standalone)

A user who edits `tailored-resume.md` after reading the ledger needs to re-verify it without
rebuilding the package. Trigger this when the user asks to re-check, re-lint, or re-verify an
existing application folder (e.g. "relint Acme," "re-check the Globex package").

1. Resolve the folder against `applications/*` (by company/role match, same ask-on-ambiguity rule as
   step 1) — **not** against `reports/`, since this operates on a package that already exists.
2. Re-run the tracer (4.4) on the **current** `tailored-resume.md` + `facts.md` — same prompt, same
   isolation, one fresh subagent.
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
   only "what your record evidences" is in scope, matching `docs/apply-package-spec.md` §5.5 — and
   per 4.5, that section itself now carries no JD-derived numerals to begin with, so `--section` is
   belt-and-suspenders here, not the only thing standing between the JD's numbers and a false ERROR.)
4. Overwrite `lint-report.md` with the fresh ledger + findings, same structure as 4.4. This is **not**
   a rebuild — it doesn't touch any other file in the folder, and it never triggers the `-2` collision
   suffix.
5. Report the new ERROR/WARN counts and the ledger's NO SOURCE count, and note anything that flipped
   since the last lint (newly traced, newly untraceable). **A flip doesn't necessarily mean the
   document changed** — the tracer is a single model pass, not a deterministic check, so a claim can
   flip between two lint runs over *identical* `tailored-resume.md` content purely from run-to-run
   variance. That's truer now than when this skill ran three tracers per lint and combined them by
   union — a single pass has nothing to average against, so its nondeterminism shows up directly in
   what the user sees. Report a flip either way, but don't imply the file changed if it didn't, and
   treat a claim that flips between runs as deserving **more** scrutiny than one that traces the same
   way every time — instability in the verdict is itself signal, not noise to explain away.

## 6. Wrap-up

After a build (or a batch), report per job:

- Files written (or, for a resumed `INCOMPLETE` build, files completed this run).
- Claims ledger: total claims / NO SOURCE count.
- Lint: ERROR count / WARN count.
- The tracer's most notable finding, if any (e.g. a claim that reads as overstated even if traced).
- The biggest gap from `gap-analysis.md`'s section 2.

For a URL-resolved job, add one more line: this job came from a URL, so it will not show up in the
console — the console reads `applications/` zero times, only `reports/`. The package lives in
`applications/<slug>/`. Say this plainly and every time; a student who isn't told will assume the
build failed rather than succeeded somewhere the console simply doesn't look.

Then say, plainly, once per session rather than per job: **passing the lint and the tracer is not the
same as a claim being true** — both check traceability to `facts.md`, not whether the underlying
fact is accurately represented or whether the user can defend it. Add, in the same breath: **the
claims ledger is one sample of a model's judgment, not a verdict** — a single tracer pass has been
observed certifying a re-credited claim ("end-to-end ownership" of work the registry backs only as
fragments) that a second pass on the same material caught as NO SOURCE, and a later run saw the same
instability split three ways across three passes on a different claim. This skill used to run three
tracers per job and combine their NO SOURCE sets by union specifically to catch that instability
before the user ever saw it; that costs roughly 50k tokens per subagent spawn — ~150k per job, ~1M
across a ten-job batch — and it's been reverted to a single pass on the reasoning that the user reads
the tailored résumé line by line anyway. That reasoning only holds if the reading actually happens:
with one pass, the user's own review is the mitigation, not a backstop behind one. Encourage them to
read `lint-report.md` and `gap-analysis.md` line by line, not skim the counts, and cut anything they
can't say out loud in an interview before they send the package.

## Out of scope

No depth tiers — every approved job gets the full package; the manifest gate is the only cost
control. No console changes (the console doesn't read `applications/` in this version). No cover
letters, outreach drafts, or a reviewer pass — none of that is part of this build. No wiring the
console's Queue panel into `/apply` — it's `localStorage` and this session cannot read it; naming
jobs explicitly is the only input path for now.
