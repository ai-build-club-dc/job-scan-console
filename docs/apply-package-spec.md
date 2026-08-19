# Apply-package stage (`/apply`) — design spec

Original design 2026-08-18 · generalized for the shared repo 2026-08-19.
Ships as **v0.8** of this repo, with a migration path for students who onboarded before this
feature existed (§7).

---

## 1. Where it sits

```
/scan-jobs  →  reports/*.md  →  console (read)  →  student picks a job
                                                          ↓
                                              /apply <job>   ← explicit, gated
                                                          ↓
                                    applications/<Company>-<Full-Role-Title>/
```

The scanner finds and ranks. `/apply` builds the package for one job the student has chosen. The
two are separate invocations by design: nothing is generated without a human asking for it.

## 2. The package

`applications/<Company>-<Full-Role-Title>/` — already covered by the repo's `.gitignore`
(`applications/`), so packages are personal data that repo updates never touch.

| File | What it is | Honesty-checked |
|---|---|---|
| `job-post.md` | The JD in markdown, plus a provenance link back to the source report | No |
| `company-context.md` | Research output. Every claim carries a source URL actually fetched | No (§5.7) |
| `tailored-resume.md` | The résumé re-expressed for this JD | **Yes** |
| `gap-analysis.md` | What the JD asks for, measured against `facts.md` | **Yes** (student-claim section only) |
| `notes.md` | Application tracker — structured header + freeform log | No |
| `lint-report.md` | Claims ledger + lint findings + tracer findings | n/a |

`lint-report.md` is **overwritten** on every re-lint (§3.5), so it always reflects the current
materials rather than an earlier draft.

**Generation order** — `job-post.md` → `company-context.md` → `tailored-resume.md` →
**tracer + lint** → `gap-analysis.md` → **lint `gap-analysis.md`, appending to the same report** →
seed `notes.md`.

The second lint pass is not redundant. `gap-analysis.md` is marked honesty-checked in the table
above, but it does not exist yet when the tracer and the first lint pass run over the résumé — so
without a second pass it would ship unchecked until a re-lint the student may never run. The tracer
runs once (on the résumé, which is where fabrication lives); the script runs twice.

The résumé is built *before* the gap analysis (decision 9): the gap analysis reports on a finished package rather than steering it, which
makes it a student-facing advisory document rather than generator machinery.

**The gap analysis measures the JD against `facts.md` — never against the résumé's prose.** This is
load-bearing (see §6). If it audited the résumé, a fabricated bridge would make the résumé *appear*
to evidence a requirement, and the audit would fall silent exactly when it is needed. Measuring
against the registry instead means a fabricated bridge surfaces as a visible contradiction: the
résumé claims it, the gap analysis says the registry doesn't evidence it.

**Slug rules** — `<Company>-<Full-Role-Title>`, hyphenated, proper case
(`Acme-Corp-Senior-Product-Manager`): company name, then the role title as posted, both
proper-cased with spaces and punctuation replaced by hyphens. No controlled role vocabulary: a
fixed tag list (`PM`/`PO`/`CSM`/`BA`…) is product-management-centric and doesn't generalize to
arbitrary student careers. **If the slug exists, append the lowest free integer suffix** (`-2`, then
`-3`) — never write into an existing folder. Silently overwriting a package the student has edited is
the worst failure this feature can have.

## 3. The flow

**3.1 Invocation and job resolution.** `/apply <company or company + role>` resolves against **all
reports in `reports/`**, not only the newest — the console lets students browse every report, and the
v0.7 queue persists across them, so a student may well be acting on a job from last week. If the
term matches entries in more than one report, or more than one entry in a report, **ask** — never
guess between two postings at the same company. The resolved report filename appears in the manifest.

`/apply` with no argument prints a numbered list of jobs from the most recent report and asks which.
It does **not** silently batch.

**Batching** is by explicit enumeration only: `/apply Acme, Globex, Initech`. There is no queue to
batch over — the v0.7 console queue is `localStorage` and invisible to Claude (§8). If the student
says **"process my queue"** — likely, since the console has a Queue panel — Claude must say plainly
that it cannot see the console's queue, then show the numbered list so they can name the jobs. It
must never quietly substitute a different set.

**3.2 Manifest gate.** Print, per job: company, role, fit score, source report, the files to be
written, the target folder path, and the research fetch budget. **Wait for one reply.** The reply
grammar is `go`, optionally with per-job `skip` (`go, skip globex`) — with depth tiers removed there
is no tier to override. Nothing is created before that reply: no folder, no files. With tiers gone
(§4), this gate is the only throttle on cost.

**3.3 Build** in the order in §2. **Each package is atomic.** If a batch is interrupted, completed
folders stand; a partially built folder gets an `INCOMPLETE` marker line at the top of `notes.md`.
Re-running `/apply` on a job whose folder is marked `INCOMPLETE` **resumes into that folder** rather
than creating a `-2` sibling — the collision rule is for genuinely distinct pursuits, not for
finishing an interrupted one.

**3.4 Report** — files written, claims-ledger counts (total claims / `NO SOURCE`), lint ERROR/WARN
counts, tracer findings, and the biggest gap.

**3.5 Re-lint (standalone).** The honesty loop requires this: a student who edits
`tailored-resume.md` after reading the ledger must be able to re-verify. Re-linting
re-runs the tracer and the script over an existing folder and overwrites `lint-report.md`. It is
**not** a rebuild and does not trigger the collision rule.

## 4. No depth tiers

Every pursued job gets the full package — there is no cheaper tier to route a weaker-fit job into.
Consequence, accepted knowingly: this is the most expensive possible package for every job, and the
manifest gate is the sole cost control. A ten-job batch is ~50 research fetches and ten subagents
under one approval — which is why the manifest discloses the budget.

## 5. The honesty model

This is the load-bearing part. There's no maintained canonical facts document, no written career
narrative, and no reviewer subagent checking the story here — a student has a résumé and this repo.
The honesty model below is built for that footprint:

**5.1 `facts.md` — the registry.** Lives at the **repo root**, beside `profile.md`, and requires a
new `.gitignore` entry (`resume*` does *not* glob `facts.md` — verified). Repo root rather than
beside `resume.md` because the lint script needs a predictable path, and it matches how `profile.md`
already works.

Generated during onboarding by extracting every number, title, date range, and credential from
`resume.md`. **Each row quotes `resume.md` verbatim** in a `source_text` field, so the student's
confirmation is a *diff* against their own document rather than a comprehension test. This matters:
a paraphrased extraction that survives a skim becomes canonical, and every downstream check then
validates against the drifted form — laundering generation drift into the source of truth. Row
schema in §11.

**5.1a Registry staleness.** `source_text` is verbatim from `resume.md` *at extraction time*, but
`CLAUDE.md` explicitly invites the student to have Claude edit `resume.md` later. When a quoted line
changes, the row silently stops matching its own source and the "confirmed against a document"
guarantee quietly expires — with nothing announcing it.

Rule: **any edit to `resume.md` requires re-running the registry step** for affected rows, and
`CLAUDE.md`'s ongoing rules must say so. A mechanical check is possible later — verify that each
`résumé`-provenance row's `source_text` still appears literally in `resume.md`, and WARN if not —
but `resume.md` lives *outside* the repo by design, so the lint would need a path to it. Deferred,
not dismissed.

**5.2 The reservoir.** Onboarding also asks 3–4 questions for accomplishments *not* on the résumé
("what have you shipped that isn't on here?"). Without this, `facts.md` contains nothing the résumé
doesn't, so "tailoring" could only reshuffle. This matters most for career-changers, whose résumés
are written for the field they're leaving and systematically omit transferable evidence. Registry
extraction plus reservoir questions add roughly 4–5 minutes to onboarding.

**5.3 What tailoring is permitted.** Free-text tailoring against the reservoir-enriched registry.
The résumé may be **rewritten** for each JD, drawing on any fact in `facts.md`. Confirmed
deliberately: the intent is a generator that writes new prose about the student's career, not one
that reshuffles existing bullets. §6 is the accepted risk that comes with it.

**5.4 Provenance and attestation.** Each registry row is marked `résumé`, `self-reported`, or
`attested`. Extracted facts were verified against a document the student stands behind; reservoir
facts were typed into a chat window. The lint **WARNs** — never ERRORs — when a `self-reported`
claim appears in a résumé.

**Attestation exists to prevent warning fatigue.** For a student with few quantified achievements —
nonprofit, academic, early-career, which is much of the audience — reservoir facts are the *majority*
of the registry, so an un-suppressed WARN fires on nearly every claim of every package forever, and
they stop reading the one report the honesty model depends on. So: a `self-reported` row can be
**attested once**, in a single explicit confirmation ("I stand behind this and can defend it in an
interview"), after which it stops WARNing. Provenance still records that it never came from a
document. Attestation is per fact, not per package.

**5.5 The lint** (`scripts/honesty_lint.py`) — a **pure passive reporter**: it never blocks, never
auto-fixes, never edits its input, and always exits 0. `python3` is already a repo prerequisite (it
runs the console server), so this adds no dependency.

- **Check 2 — metrics.** Every number traces to a registry row.
- **Check 3 — dates.** Role date ranges match the registry.
- **Check 4 — credentials.** Generalized to "every credential traces to a registry row." A version
  that encoded personal rendering rules (a specific school name, a hardcoded "7+ years" pattern)
  wouldn't generalize across students, so those are dropped.
- **Check 7 — zero-source.** Implemented to its **fuller specification** — hard facts *and* causal
  attributions, not just the numbers. A numbers-only version would leave prose fabrication ("drove
  product strategy for the platform org") completely unchecked, which is exactly the failure mode §6
  exists to catch. The tracer (§5.6) is what makes the causal half tractable.

Checks 1, 5, and 6 are dropped: they would encode canonical titles, a personal kill-list, and
personal rendering rules that don't generalize.

**Lint scope is claims about the student only.** `gap-analysis.md` is full of JD-derived figures
("this JD wants 3 years of roadmap ownership") that have no registry home by design. Linting those
would produce a false-positive storm and teach students to ignore ERRORs — corroding the only
enforcement mechanism there is. So `gap-analysis.md` is structurally split (§11) and the lint reads
only its student-claim section.

**5.6 The claims ledger and the tracer — one mechanism.** `lint-report.md` enumerates every career
claim in `tailored-resume.md` with the `facts.md` row backing it, or `NO SOURCE`.

**Enumeration is done by the model, not by the script.** This is the correction that matters most in
this document. A Python script can reliably enumerate sentences containing numbers, dates, and
credentials — it cannot enumerate "drove product strategy for the platform org." If the script owned
the ledger, a fabricated prose claim would not be listed as `NO SOURCE`; it would be *absent*, and
`lint-report.md` would read "0 NO SOURCE" — affirmatively certifying the résumé while the invented
sentence sails through. That is precisely the false-confidence failure §6 exists to prevent.

So the **tracer subagent produces the ledger**. It receives **only** `tailored-resume.md` +
`facts.md` — not the job post, not the conversation — enumerates every claim, and marks each traced
or untraceable. Withholding the JD is the mechanism: it cannot rationalise an invention as "the
posting asked for that." The tracer checks whether a persuasive story is true, not whether a true
story is told persuasively.

The script then **verifies the numeric subset** — metrics, dates, credentials — where determinism
beats judgment. **Both write into `lint-report.md`**; neither reports only in chat, because the
durable artifact is what the student actually consults. Cost: one subagent per `/apply`, per job.

**5.7 Company research is guarded differently.** `company-context.md` is out of lint scope — company
facts have no registry to check against. The guard is procedural: **every claim carries a source URL,
and a URL may only be cited if it was actually fetched during this run.** Empty sections say "not
found" literally. Note the limit honestly: the failure mode is not a missing citation, it is a
plausible claim decorated with a plausible URL that was never fetched or doesn't support the
sentence. The fetched-this-run rule is what makes the citation mean something.

**5.8 Research budget** — ~5 fetches into a fixed template: what they do, size/stage, recent news,
product/tech, why-it-fits. Fetching the JD itself (§11 sourcing) does **not** count against this.

## 6. Known risk — career-change applications

The scan rubric keeps survivors at ≥6/10 while scoring title match 0–4, so jobs clear with a weak
title match carried by substance. Those are stretch applications, where the résumé-to-JD distance is
widest and the generator is under the most pressure to bridge — and bridging is where invented
claims come from.

**Mitigation, in three parts.** The tracer-built ledger (§5.6) catches untraceable prose claims,
which is where fabrication actually lives. The gap analysis measures against `facts.md` rather than
the résumé (§2), so a fabricated bridge shows up as a contradiction instead of disappearing.
Generation-time rule, stated in the skill: attribution may be re-worded or generalized, **never**
re-credited.

**The residual risk no mechanism catches.** A claim can be fully traceable and still overstated.
"Owned the roadmap", backed by a `facts.md` row reading "coordinated sprint planning", passes the
lint, passes the tracer, and fails an interview. Nothing in this design catches that, and nothing
reasonably could — the student's judgment is the last gate.

**A sharper variant: the script matches values, not meaning.** `honesty_lint.py` verifies that a
number exists somewhere in the registry — not that it is attached to the claim being made. Found
during the build: *"coordinated a program serving 5+ regional partners"* traced **cleanly** against a
row reading *"5+ years of product management experience"*. Same number, unrelated claim, reported as
0 ERROR / 0 WARN.

This one is *not* unmitigated — the tracer reads meaning and must cite the specific row supporting
each claim, so a row about years-of-experience cannot legitimately back a claim about partner counts.
But that makes the tracer a **single point of failure** for this whole class of error: the script
will actively report clean, and a student reading only the lint findings sees confirmation. Two
consequences for the build:

1. `lint-report.md` must always present the ledger **above** the script findings, so the
   context-aware check is what the eye lands on first. (The skill does this.)
2. The script's own report header must state that a claim's absence from its findings is not a
   clean bill. (It does — the wording came out of the build, not this spec.)

A future hardening, deliberately not in v0.8: have the script report *which* row it matched, so a
number tracing to a semantically unrelated row is at least visible to a reader rather than silent.

The corresponding danger is **false confidence**: "it passed the lint" reading as "it is true."
The `USER-GUIDE` must therefore say in plain words that these files make claims *on the student's
behalf*, that passing checks is not verification, and that anything they cannot defend out loud
should come out before they send it. `gap-analysis.md` carries this as a closing section —
*you will be asked to back these claims in an interview; can you?* — which converts an invisible
risk into a rehearsal task.

**Residual risks found running the skill end-to-end.** Two full dry runs against live postings
turned up five more gaps. None of the mechanisms above catch these:

1. **The tracer is nondeterministic.** The identical verbatim prompt, run twice over near-identical
   résumé text, returned 29 claims / 7 NO SOURCE on one run and 22 claims / 5 NO SOURCE on the other,
   with two verdicts flipping in opposite directions on claims that hadn't changed between runs.
   Critically, `"end-to-end ownership of a tool build"` — where the registry backed only discrete task
   fragments, i.e. exactly the re-crediting the generation-time hard rule above forbids — was
   **TRACED on one run and NO SOURCE on the other**. A single pass is a sample of a model's judgment,
   not a verdict. The skill is being changed to run three tracers and take the union of their
   NO SOURCE sets, which reduces but does not eliminate this.
2. **A false ERROR costs trust.** The lint flagged "LLM" (in "an LLM-based summarizer") as an
   unbacked *credential*, because `LLM` is also the Master of Laws degree. Fixed, but the general risk
   stands: this report's authority depends on its findings being real, and a checker that cries wolf
   in a domain where its users live trains them to skim past true findings.
3. **Registry completeness is silently load-bearing.** A bullet copied verbatim from `resume.md` was
   flagged NO SOURCE simply because onboarding never extracted it as a registry row. The tracer was
   right — the registry is the contract — but students will see true content flagged whenever their
   registry is thin, and the natural reaction is to distrust the checker rather than fill the
   registry.
4. **Numbers about the analysis get checked as claims about the candidate.** A summary tally written
   inside the lint-scoped section had all four of its counts flagged as unbacked claims. Mitigated by
   a placement rule in the skill, but it illustrates that the script cannot distinguish
   meta-commentary from career claims.
5. **The fit score can go stale the moment the JD is fetched.** A package was built on a report entry
   whose fit score was set partly on "salary not listed", while the JD fetched during the build listed
   a range well above the student's floor. Nothing feeds that back into the report, so a package can
   sit on a rationale its own contents contradict.

## 7. Migration

Existing students have `profile.md` and **no `facts.md`**. `/apply` must detect this and offer to
build the registry on the spot. This is the most likely thing to be forgotten and the first thing
existing students will hit.

**Ordering:** the migration branch runs **before the manifest gate**, not after. Registry extraction
is mechanical, but the reservoir questions (§5.2) are an interview — dropping an interview in after
the student has already approved the manifest breaks the "approve, then build" contract. So:
detect missing `facts.md` → extract → confirm → reservoir questions → *then* print the manifest.
Reservoir capture is **skippable** for migrating students (`facts.md` becomes résumé-only, every row
provenance-marked `résumé`); they can add reservoir facts later by re-running the registry step.
A first-time onboarding student always gets both.

**Thin registries.** If extraction yields very few quantified facts and the reservoir is skipped,
`/apply` says so before the manifest: tailoring has little to work with, and the résumé will mostly
restate what's already there. Better to set the expectation than to let the generator invent its way
to a full page.

## 8. Explicitly out of scope

- **Console changes.** No Applications panel in v0.8. The console could read these files, but it
  would add a *third* parse contract (after `profile.md`'s headings and the report format), and
  every parse contract this repo relies on has to change on all sides — script, skill, and docs — in
  the same commit. Let the file shapes stabilize first.
- **Queue → `/apply` wiring.** The v0.7 queue is `localStorage`, invisible to Claude, and the
  console cannot write files. So the queue is not the trigger in v0.8 — the student picks in the
  console, then names the job to Claude. Persisting the queue to a file Claude can read is a
  **planned later version**, and it reopens the deliberate v0.7 decision to keep the queue UI-only.
- **Deliberately not built:** depth tiers, angle presets with a role-tag vocabulary, a
  reviewer-subagent pass, pushing to Google Docs, structured outcome tracking, outreach drafts, cover
  letters.

## 9. Decision record

| # | Decision | Chosen |
|---|---|---|
| 1 | Honesty model | Mini fact-registry built at onboarding |
| 2 | Trigger | Explicit `/apply` + manifest gate; queue-file wiring deferred |
| 3 | `company-context.md` | **In** at apply time — full. There's no later stage to defer company research to |
| 4 | Folder / filenames | `applications/<Company>-<Full-Role-Title>/`, familiar per-file names, provenance link, `notes.md` |
| — | Depth tiers | **None.** Every pursued job gets the full package |
| 5 | Registry timing | Onboarding, from `resume.md`, student-confirmed |
| 6 | Enforcement | Simplified `honesty_lint.py`, passive reporter, checks 2/3/4/7 |
| 7 | Research budget | ~5 fetches, fixed template, source URLs, literal "not found" |
| 8 | Manifest | Confirms scope + cost + target path + source report; batch supported |
| 9 | File order | Résumé **before** gap analysis; gap analysis is advisory output |
| 10 | Tailoring | Reservoir captured at onboarding; **free-text** tailoring against it |
| 11 | Gap analysis | JD requirements measured against `facts.md`; meet / partial / missing + how to close |
| 12 | `notes.md` | Structured header + freeform log, hand-editable markdown |
| 13 | Console | No changes in v0.8 |
| 14 | Release | Own release, v0.8, with the migration path |
| 15 | Reservoir facts | Provenance-marked; WARN on résumé use until attested |
| 16 | Slug | `<Company>-<Full-Role-Title>`, lowest free integer suffix on collision |
| 17 | Claims ledger | **Model-enumerated**, written to `lint-report.md`, source or `NO SOURCE` |
| 18 | Tracer subagent | Sees only résumé + `facts.md`, never the JD; produces the ledger |
| 19 | Interview-readiness | Closing section of `gap-analysis.md`: can you defend these out loud? |
| 20 | Docs posture | `USER-GUIDE` states plainly that passing checks ≠ verified |
| 21 | `facts.md` location | Repo root, new `.gitignore` entry; rows quote `resume.md` verbatim |
| 22 | Batch source | Explicit enumeration only; "process my queue" is answered, never guessed at |
| 23 | Job resolution | Across **all** reports; ambiguity is asked about, never guessed |
| 24 | Re-lint | Standalone re-run over an existing folder; not a rebuild, no collision suffix |
| 25 | Attestation | `self-reported` rows can be attested once to stop repeat WARNs |
| 26 | Lint scope | Claims about the student only; JD-derived figures excluded structurally |
| 27 | Check 7 | Implemented to its **full** spec (causal attributions), not limited to numbers |
| 28 | Citations | Only URLs actually fetched this run may be cited |
| 29 | Batch atomicity | Per-package; `INCOMPLETE` marker; resume rather than sibling-folder |
| 30 | Server binding | Console server binds localhost only (§10) |
| 31 | Lint passes | Tracer runs once (résumé); script runs **twice** — résumé, then gap analysis |
| 32 | Registry staleness | Editing `resume.md` requires re-running the registry step; mechanical check deferred |

## 10. Build order

1. **`.gitignore`** — add `facts.md`. Do this first; it is one line and it is the difference between
   a private career registry and a public one.
2. `facts.md` generation + confirmation in `CLAUDE.md` onboarding: verbatim-quoting extraction,
   reservoir questions, the attestation step.
3. `scripts/honesty_lint.py` — checks 2/3/4/7, provenance-aware WARN, verifies the
   **numeric subset** of the ledger. It does **not** enumerate claims (§5.6).
4. `.claude/skills/apply/SKILL.md` — the flow in §3, the tracer subagent that produces the ledger,
   the standalone re-lint path, the interview-readiness section of `gap-analysis.md`.
5. Migration branch in `/apply` for pre-v0.8 students (§7).
6. **Docs** — `README`, `USER-GUIDE`, `CLAUDE.md`, `profile.template.md` if the registry touches it.
   Three existing statements become false the moment this ships and must be corrected, not just
   supplemented:
   - `USER-GUIDE.md` privacy section: *"the only thing that ever leaves your machine is the job
     search itself"* — company research fetches make this untrue.
   - `USER-GUIDE.md` prerequisites: *"`python3` … nothing else depends on it"* — the lint does.
   - `README.md` prerequisites: *"any static file server works"* — still true for serving, but
     `python3` is now required for the lint.
   `USER-GUIDE` must also carry the false-confidence warning in §6. That is not optional copy.
7. **`CLAUDE.md` server command** — add `--bind 127.0.0.1`. The served root will now contain
   `applications/` (tailored résumés) and `facts.md`; `python3 -m http.server` binds all interfaces
   by default, which would make a student's application materials readable across their LAN. This
   pre-dates the feature but this feature is what makes it matter.
8. Badge → v0.8, and ship following this repo's usual release process for the shared repo.

## 11. File schemas

Every parse contract in this repo has to be explicit and change on all sides in one commit. These
are contracts: the lint script and the skill both read them.

**`facts.md`** — one row per fact:

```
| id | kind | value | source_text | provenance |
```

`kind` ∈ `metric` / `title` / `date` / `credential` / `deliverable`. `source_text` is the verbatim
line from `resume.md`, or empty for reservoir facts. `provenance` ∈ `résumé` / `self-reported` /
`attested`.

**`job-post.md` sourcing**, in order: re-call `get_job_details` on the stored job ID → `WebFetch` the
apply link → fall back to the report entry alone, marked `provenance: degraded (summary only)` in the
file. A JD behind a login or a rotted link must degrade visibly, never stall the package or get
silently invented. JD fetches don't count against the research budget (§5.8).

**`gap-analysis.md`** — three sections, in this order:
1. **What this job asks for** — JD requirements, quoted. Out of lint scope.
2. **What your record evidences** — each requirement measured against `facts.md`: *meet / partially
   evidence / no evidence*, citing the row. **In lint scope.**
3. **How to close the gaps, and can you defend them?** — concrete actions, plus the
   interview-readiness prompt (§6).

**`notes.md`** — a header block (`company`, `role`, `source_report`, `fit`, `folder_created`,
`status`) over a freeform dated log. `status` ∈ `built` / `applied` / `interviewing` / `rejected` /
`offer`. Hand-editable markdown, never JSON — a student will type "recruiter called Tuesday" into
this file and that must not break anything.
