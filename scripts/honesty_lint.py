#!/usr/bin/env python3
"""
honesty_lint.py -- verifies the NUMERIC SUBSET of claims in a generated application
material against the fact registry (facts.md).

WHAT THIS SCRIPT DOES (spec docs/apply-package-spec.md, section 5.5):
  Check 2  metrics      every number in a material traces to a facts.md row of kind `metric`.
  Check 3  dates        role date ranges trace to facts.md rows of kind `date`.
  Check 4  credentials  degree/certification mentions trace to facts.md rows of kind `credential`.
                         Generalized: the detection patterns below are generic degree
                         abbreviations and certification phrasing, not any person's school
                         name or a hardcoded "N+ years" rule.
  Check 7  zero-source  any hard numeric claim that has no home in facts.md at all
                         (a stricter escalation of check 2 -- see resolve_metric below).

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO (spec section 5.6):
  It does NOT enumerate prose/causal claims ("drove product strategy for the platform
  org"). A regex can reliably find a number, a date range, or "M.S. in Computer Science"
  -- it cannot reliably decide whether a sentence with no digits in it is true. Trying
  would produce false confidence: a claims ledger that looks complete but silently
  omits the exact fabrications it exists to catch. That job belongs to a model-driven
  tracer subagent that reads the material with judgment. This script only ever looks
  at things containing digits (numbers, dates) or matching a closed set of credential
  patterns. If a claim has no number, no date, and no degree/certification phrase in
  it, this script has nothing to say about it -- by design, not by omission.

CONTRACT (do not change without updating the other pieces this is built against):
  Invocation:  python3 scripts/honesty_lint.py <material.md> [<material2.md> ...] [--registry PATH]
  Default registry path: facts.md at the CURRENT WORKING DIRECTORY (repo root, by convention).
  Output: markdown to stdout, ranked ERROR before WARN, grouped by source file, with a
          combined header giving counts. `--report PATH` additionally writes the same
          markdown to a file. This script never writes lint-report.md itself -- the
          /apply skill assembles that file from the tracer's ledger plus this script's
          stdout.
  Exit code: always 0 on a successful lint. Non-zero ONLY if a material file or the
          registry is missing (or otherwise unreadable) -- never as a pass/fail signal.
  Passive reporter only: never blocks, never auto-fixes, never edits its input.

Python 3.9, standard library only (no pip installs -- this runs on a plain student Mac).
"""

import argparse
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------------------
# Registry (facts.md) parsing
# --------------------------------------------------------------------------------------

class FactRow:
    """One row of facts.md: | id | kind | value | source_text | provenance |"""

    __slots__ = ("id", "kind", "value", "source_text", "provenance", "line_no")

    def __init__(self, id_, kind, value, source_text, provenance, line_no):
        self.id = id_
        self.kind = kind
        self.value = value
        self.source_text = source_text
        self.provenance = provenance
        self.line_no = line_no

    def text(self):
        """Combined text the number/date/credential matchers search over."""
        return self.value + " " + self.source_text


# A markdown table separator row: "|---|---|" / "| :--- | ---: |" / with or without
# outer pipes. Matched purely so we can skip it -- it carries no data.
SEPARATOR_RE = re.compile(r"^\s*\|?[\s\-:|]+\|?\s*$")


def split_row(line):
    """Split a markdown table row into cells, tolerant of a missing leading and/or
    trailing pipe (the spec asks us to tolerate that in facts.md)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def normalize_provenance(raw):
    """Fold the accented and unaccented spellings, and anything unrecognized, into
    one of three buckets. An unrecognized/garbled provenance is treated the same as
    'self-reported' for WARN purposes -- the conservative direction, since we cannot
    confirm it has a paper trail."""
    v = raw.strip().lower()
    if v in ("résumé", "resume", "résume", "resumé"):
        return "résumé"
    if v in ("attested",):
        return "attested"
    if v in ("self-reported", "self reported", "self_reported"):
        return "self-reported"
    # Anything else (blank, misspelled, garbled) is treated as self-reported too --
    # the conservative default when we can't confirm a paper trail exists.
    return "self-reported"


def parse_registry(path):
    """Parse facts.md. Returns (rows, notes). Never raises on a malformed table --
    a garbled or empty registry is reported in `notes`, not a crash, per the spec's
    'thin résumé' and 'garbled registry' requirements."""
    notes = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        notes.append(f"Could not read facts.md at {path}: {exc}")
        return [], notes

    lines = text.splitlines()

    header_idx = None
    for i, line in enumerate(lines):
        cells = [c.lower() for c in split_row(line)]
        if len(cells) >= 5 and cells[:5] == ["id", "kind", "value", "source_text", "provenance"]:
            header_idx = i
            break

    if header_idx is None:
        notes.append(
            'Could not find a table header "| id | kind | value | source_text | '
            'provenance |" anywhere in facts.md. Treating the registry as empty -- '
            "every numeric/date/credential claim below will report as zero-source "
            "until this is fixed."
        )
        return [], notes

    i = header_idx + 1
    if i < len(lines) and SEPARATOR_RE.match(lines[i]):
        i += 1

    rows = []
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            if rows:
                break  # blank line after we've started collecting rows -- table's over
            i += 1
            continue
        if raw.lstrip().startswith("#"):
            break  # next markdown section
        cells = split_row(raw)
        if len(cells) < 5:
            notes.append(
                f"facts.md line {i + 1}: skipped (expected 5 columns, found "
                f"{len(cells)}): {raw.strip()!r}"
            )
            i += 1
            continue
        id_, kind, value, source_text, provenance = cells[:5]
        rows.append(
            FactRow(
                id_.strip(),
                kind.strip().lower(),
                value.strip(),
                source_text.strip(),
                normalize_provenance(provenance),
                i + 1,
            )
        )
        i += 1

    if not rows:
        notes.append(
            "facts.md has a header but no data rows. Every numeric/date/credential "
            "claim below will report as zero-source until rows are added."
        )

    return rows, notes


# --------------------------------------------------------------------------------------
# Number extraction and matching (Check 2 / Check 7)
# --------------------------------------------------------------------------------------

# Alternatives are tried in order at each position, so the more decorated forms
# (commas, K/M/B suffix, currency, percent, "+") must come before the bare-integer
# fallback, or the bare-integer alternative would win first and strand the decoration.
NUM_TOKEN_RE = re.compile(
    r"""
    (?<![A-Za-z])                              # LEFT guard: a digit immediately
                                                # preceded by a letter is part of an
                                                # alphanumeric token, not a claim --
                                                # without this, "B2B" reads as the
                                                # start of a number at its "2", and
                                                # combined with the K/M/B suffix
                                                # alternative below, "B2B SaaS" was
                                                # observed parsing as "2B" = 2 billion
                                                # during testing. Also guards version
                                                # strings like "v2.5".
    (?:
      \$?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?        # comma-grouped: 120,000 or $1,200.50
      | \$?\d+(?:\.\d+)?[KkMmBb]\+?(?![A-Za-z0-9])  # suffixed: 120K, $1.5M, 400K+ --
                                                # RIGHT guard so "K8s" or "3Mbps"
                                                # don't parse as a bare magnitude either.
      | \$\d+(?:\.\d+)?                        # currency, no suffix: $500
      | \d+(?:\.\d+)?%                         # percent: 25%, 3.5%
      | \d+(?:\.\d+)?\+                        # floor notation: 400+
      | \d+(?:\.\d+)?                          # plain integer/decimal
    )
    """,
    re.VERBOSE,
)


def parse_number(token):
    """Normalize '$120K', '120,000', '25%', '400+' etc. to a comparable float, so
    that '$120K' == '$120,000' == '120000' the way the spec requires. Percent
    sign is dropped after use (25% and 25 compare equal) since facts.md rows render
    percentages inconsistently too; this is a documented judgment call, not a claim
    that 25% and 25 always mean the same thing in every sentence."""
    t = token.strip().replace(",", "")
    t = t.lstrip("$")
    t = t.rstrip("+")
    t = t.rstrip("%")
    multiplier = 1.0
    if t and t[-1] in "KkMmBb":
        multiplier = {"k": 1e3, "m": 1e6, "b": 1e9}[t[-1].lower()]
        t = t[:-1]
    try:
        return float(t) * multiplier
    except ValueError:
        return None


def numbers_in_text(text):
    """All numeric values found in a blob of text (used to scan a facts.md row's
    value + source_text for a matching figure)."""
    out = []
    for m in NUM_TOKEN_RE.finditer(text):
        v = parse_number(m.group(0))
        if v is not None:
            out.append(v)
    return out


def numbers_match(a, b):
    """Exact-after-normalization equality. Deliberately NOT a fuzzy/percentage
    tolerance: since $120K, $120,000 and 120000 already normalize to the identical
    float 120000.0, no tolerance is needed to satisfy the formatting requirement --
    and adding one (e.g. +/-0.5%) would let a materially different number like
    $120,500 pass against a $120,000 registry row, which is exactly the kind of
    drift this check exists to catch. A tiny epsilon only absorbs float rounding."""
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


def row_has_number(row, value):
    return any(numbers_match(value, other) for other in numbers_in_text(row.text()))


# Bare 4-digit tokens that look like calendar years (1900-2099) are excluded from
# metric scanning UNLESS they carry $, %, K/M/B, a comma, or a "+" -- i.e. unless
# something marks them as a quantity rather than a year. Flagging every "2024" in a
# résumé as an unsourced metric would drown the real findings in noise. This is a
# documented false-negative trade: a genuine metric that happens to equal a plausible
# year (e.g. "grew from 40 to 2020 users") would be missed. Accepted knowingly.
BARE_YEAR_RE = re.compile(r"^\d{4}$")


def is_probable_calendar_year(token, value):
    return bool(BARE_YEAR_RE.match(token)) and 1900 <= value <= 2099


def best_provenance(rows):
    """Given rows that all matched the same claim, decide clean vs. WARN. If ANY
    matching row carries a paper trail (résumé/attested), the claim is clean --
    it doesn't matter that some *other* row for the same figure is self-reported.
    Only WARN when every match is self-reported. Picking the first match instead of
    scanning all of them was an earlier draft bug: it could emit a spurious WARN when
    a self-reported row happened to be listed before an attested one for the same
    number. Fixed by checking the whole match set here."""
    for r in rows:
        if r.provenance in ("résumé", "attested"):
            return "clean", r
    return "warn", rows[0]


# --------------------------------------------------------------------------------------
# Date range extraction and matching (Check 3)
# --------------------------------------------------------------------------------------

MONTH_RE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE_TOKEN_RE = rf"(?:{MONTH_RE}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
OPEN_ENDED_WORD_RE = r"(?:Present|Current|Ongoing)"
END_TOKEN_RE = rf"(?:{DATE_TOKEN_RE}|{OPEN_ENDED_WORD_RE})"
DATE_RANGE_RE = re.compile(
    rf"({DATE_TOKEN_RE})\s*(?:[-–—]|to)\s*({END_TOKEN_RE})", re.IGNORECASE
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
MONTH_YEAR_RE = re.compile(rf"({MONTH_RE})\s+(\d{{4}})", re.IGNORECASE)
OPEN_ENDED_RE = re.compile(rf"\b{OPEN_ENDED_WORD_RE}\b", re.IGNORECASE)


def normalize_month(tok):
    return tok[:3].lower().rstrip(".")


def parse_date_token(tok):
    """Return (month_or_None, year) for a single date token like 'Jan 2020',
    '01/2020', or '2020'."""
    my = MONTH_YEAR_RE.search(tok)
    if my:
        return normalize_month(my.group(1)), int(my.group(2))
    slash = re.search(r"(\d{1,2})/(\d{4})", tok)
    if slash:
        return None, int(slash.group(2))  # numeric month not compared -- see limitations
    y = YEAR_RE.search(tok)
    if y:
        return None, int(y.group(0))
    return None, None


def registry_date_signature(text):
    """Extract everything a date-kind facts.md row tells us: every year mentioned,
    which months are attached to which years (when the row spells them out), and
    whether the row itself reads as open-ended (contains Present/Current/Ongoing)."""
    years = set()
    year_months = defaultdict(set)
    for m in MONTH_YEAR_RE.finditer(text):
        year = int(m.group(2))
        years.add(year)
        year_months[year].add(normalize_month(m.group(1)))
    for y in YEAR_RE.findall(text):
        years.add(int(y))
    open_ended = bool(OPEN_ENDED_RE.search(text))
    return years, year_months, open_ended


def date_row_matches(row, start_month, start_year, end_open, end_month, end_year):
    """Returns (matched, reason). `reason` is only populated on a specific,
    explainable rejection (currently: the open-ended-vs-closed contradiction) so the
    caller can tell the student what's actually wrong instead of a generic 'no match'
    -- see the open-ended branch below for why that distinction matters."""
    years, year_months, row_open = registry_date_signature(row.text())
    if start_year not in years:
        return False, None
    if start_month and year_months.get(start_year) and start_month not in year_months[start_year]:
        return False, None  # both sides name a month for the start year, and they disagree
    if end_open:
        # Material claims the role is still ongoing. That's only backed if the
        # registry also reads as ongoing, OR the registry simply doesn't mention a
        # later year at all (too coarse to contradict). If the registry names a
        # later year with no open-ended marker, it is recording the role as having
        # ended -- a claim of "Present" against that is the highest-consequence
        # date error this check can catch, so it does not get waved through.
        #
        # This rejection gets its own reason string: a generic "no matching row"
        # message would read as "the registry is missing this role," and a student
        # fixing that by adding a fresh Present-dated row would launder a real
        # discrepancy into the source of truth instead of catching it (spec §5.1's
        # exact failure mode). The reason spells out that the registry HAS a row for
        # this start date, and it disagrees about whether the role has ended.
        if not row_open and years and max(years) > start_year:
            registry_end = max(years)
            return False, (
                f"facts.md row {row.id} covers this start date but records it as "
                f"ending in {registry_end}, not still ongoing"
            )
    else:
        if end_year is not None and end_year not in years:
            return False, None
        if (
            end_year is not None
            and end_month
            and year_months.get(end_year)
            and end_month not in year_months[end_year]
        ):
            return False, None
    return True, None


# --------------------------------------------------------------------------------------
# Credential extraction and matching (Check 4) -- GENERALIZED, no school names, no
# hardcoded "N+ years" rule. Two classes of pattern:
#   1. Multi-letter degree/credential abbreviations (MBA, PhD, MPH, ...) -- low
#      collision risk with ordinary words, safe to match bare.
#   2. Two-letter degrees (BA, BS, MA, MS, JD, MD, ...) -- HIGH collision risk (MA =
#      Massachusetts, MS = "MS Office", BS = a common word). These are only matched
#      in period form ("B.S.", "M.A.") or when immediately followed by "in"/"of"
#      ("MS in Computer Science"), which is how résumés actually write the degree
#      itself as opposed to an abbreviation meaning something else.
#
#   LLM (Legum Magister, Master of Laws) belongs in class 2, not class 1, even though
#   it isn't literally a two-letter initialism. This repo's users are applying to
#   product/AI roles, where bare "LLM" means Large Language Model essentially always
#   ("prototyped an LLM-based summarizer over support tickets", "an LLM", "LLM
#   evaluation") and essentially never means the law degree. Matching it bare (as it
#   originally lived, in MULTI_LETTER_DEGREE_RE below) threw a false check-4 ERROR on
#   ordinary AI-work language -- observed twice in a live dry run. The fix is the same
#   high-collision treatment already applied to MA/MS/BS: only "LL.M." (period form)
#   or "LLM in/of ..." (how the law degree is actually written on a résumé) counts as
#   a match; bare "LLM" does not. Do not move it back to the bare-safe class -- the
#   collision isn't a corner case here, it's the dominant reading.
# --------------------------------------------------------------------------------------

MULTI_LETTER_DEGREE_RE = re.compile(
    r"\b(MBA|MFA|BFA|MSW|BSW|MPH|MPA|MEng|BEng|MSc|BSc|LLB|PhD|EdD)\b"
)
TWO_LETTER_DEGREE_RE = re.compile(
    # period form, e.g. "M.S." (also covers "LL.M.")
    r"\b(?:[BM]\.A\.|[BM]\.S\.|J\.D\.|M\.D\.|Ph\.D\.|Ed\.D\.|LL\.M\.)"
    # A trailing \b straight after a period form would fail: "." is a non-word
    # character, so the boundary between "." and a following space is not a \b at
    # all, and the match would silently never fire. So the period-form alternative
    # deliberately has no trailing \b -- the leading \b plus the literal dots is
    # already unambiguous. Applies to "LL.M." too, for the same reason.
    r"|\b(?:BA|BS|MA|MS|JD|MD|LLM)(?=\s+(?:in|of)\b)"  # bare form only before "in"/"of"
)
CERT_RE = re.compile(
    r"\b("
    r"Certified\s+[A-Z][A-Za-z0-9&/\- ]{2,50}"
    r"|[A-Z][A-Za-z0-9&/\- ]{2,50}\s+Certification"
    r"|Certificate(?:\s+in)?\s+[A-Za-z0-9&/\- ]{2,50}"
    r"|Licensed\s+[A-Za-z0-9&/\- ]{2,50}"
    r"|PMP|CPA|CFA|CISSP|CISA|SHRM-CP|SHRM-SCP"
    r"|Six\s+Sigma(?:\s+(?:Green|Black|Yellow)\s+Belt)?"
    r"|AWS\s+Certified[A-Za-z0-9&/\- ]*"
    r")\b"
)


def find_credential_matches(text):
    """Run all three credential patterns and merge overlapping hits, keeping the
    earliest/longest match at each position so the same phrase isn't reported twice
    (e.g. 'Certified' + 'PMP' both matching inside 'Certified PMP')."""
    raw = (
        list(MULTI_LETTER_DEGREE_RE.finditer(text))
        + list(TWO_LETTER_DEGREE_RE.finditer(text))
        + list(CERT_RE.finditer(text))
    )
    raw.sort(key=lambda m: (m.start(), -(m.end() - m.start())))
    kept = []
    last_end = -1
    for m in raw:
        if m.start() < last_end:
            continue
        kept.append(m)
        last_end = m.end()
    return kept


def normalize_credential_text(s):
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


def credential_row_matches(row, mention_norm):
    """Loose two-way substring match after stripping punctuation/whitespace and
    case. This is intentionally forgiving -- a résumé might render a credential
    differently from how the student typed it into facts.md -- and that leniency is
    a documented limitation: a heavily reworded credential can false-negative
    (report clean when it shouldn't), and a very short registry value (e.g. just
    "MBA") can loosely match unrelated bare text containing those letters."""
    registry_norm = normalize_credential_text(row.text())
    if not mention_norm or not registry_norm:
        return False
    return mention_norm in registry_norm or registry_norm in mention_norm


# --------------------------------------------------------------------------------------
# Line-level exclusions: things that look numeric but are not career claims.
# --------------------------------------------------------------------------------------

# Document metadata lines ("Generated: 2026-08-18", "Last Updated: ...") describe the
# FILE, not the student -- not claims to verify. Requires the label to be *immediately*
# followed by a colon so real content like "Date of graduation: 2020" (no colon right
# after "Date") is NOT swallowed by this exclusion.
METADATA_DATE_LINE_RE = re.compile(
    r"^\s*#{0,6}\s*(Generated|Date|Last\s+Updated|Updated|Created|As\s+of|Report\s+Date)\s*:",
    re.IGNORECASE,
)

# A line that is ONLY a page-footer marker.
PAGE_FOOTER_LINE_RE = re.compile(
    r"^(page\s+\d+(\s+of\s+\d+)?|-+\s*\d+\s*-+|\d+\s*/\s*\d+)$", re.IGNORECASE
)
# "Page 2 of 5" appearing inline within a longer line.
PAGE_INLINE_RE = re.compile(r"\bPage\s+\d+(\s+of\s+\d+)?\b", re.IGNORECASE)

# Phone numbers: (555) 555-5555 / 555-555-5555 / 555.555.5555
PHONE_RE = re.compile(r"(\(\d{3}\)\s?|\b\d{3}[-.\s])\d{3}[-.\s]\d{4}\b")

# ZIP codes as they appear in a "City, ST 12345" address line.
ADDRESS_ZIP_RE = re.compile(r",\s*[A-Z]{2}\s+\d{5}(-\d{4})?\b")

# Street addresses: "123 Main St", "4500 Fifth Avenue, Suite 200". The optional
# trailing group also swallows a "Suite 200" / "Apt 4B" unit number that follows the
# street name, so that unit number doesn't survive as a bare "200" metric candidate.
STREET_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][a-zA-Z']*\s+){1,3}"
    r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|Way|"
    r"Suite|Ste|Apt|Pl|Place)\.?"
    r"(?:,?\s+(?:Suite|Ste|Apt|Unit|#)\s*[A-Za-z0-9]+)?"
    r"\b"
)


def blank_spans(text, spans):
    """Replace matched spans with equal-length whitespace so later regex passes on
    the same line don't see the blanked-out text, while everything else on the line
    (and every character offset) is undisturbed."""
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for idx in range(start, end):
            chars[idx] = " "
    return "".join(chars)


# --------------------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------------------

class Finding:
    """One reportable finding, possibly aggregating several identical occurrences
    (same severity/check/message) across different lines -- e.g. the same fabricated
    number repeated in three bullets is one finding with three line references, not
    three separate top-level findings."""

    def __init__(self, severity, check, message):
        self.severity = severity  # "ERROR" or "WARN"
        self.check = check  # "metrics" | "dates" | "credentials" | "zero-source"
        self.message = message
        self.occurrences = []  # list of (line_no, snippet)

    def add(self, line_no, snippet):
        self.occurrences.append((line_no, snippet))


def record(findings_map, severity, check, message, line_no, snippet):
    key = (severity, check, message)
    f = findings_map.get(key)
    if f is None:
        f = Finding(severity, check, message)
        findings_map[key] = f
    f.add(line_no, snippet)


# --------------------------------------------------------------------------------------
# Per-material linting
# --------------------------------------------------------------------------------------

class FileStats:
    def __init__(self):
        self.metrics_checked = 0
        self.metrics_clean = 0
        self.dates_checked = 0
        self.dates_clean = 0
        self.credentials_checked = 0
        self.credentials_clean = 0
        self.ignored_years = 0
        self.ignored_phone = 0
        self.ignored_zip = 0
        self.ignored_street = 0
        self.ignored_page = 0
        self.ignored_metadata_lines = 0


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def find_section_bounds(lines, section):
    """Locate the line range (start index inclusive, end index exclusive) of the
    first markdown heading whose text contains `section` as a case-insensitive
    substring, bounded by the next heading at the same-or-shallower level (or EOF).
    Returns None if no heading matches.

    This exists for gap-analysis.md (spec §5.5/§11): that file is structurally split
    into "what the JD asks for" (JD-derived numbers, explicitly OUT of lint scope --
    linting those is a false-positive storm by design, per the spec) and "what your
    record evidences" (student claims, IN scope). Filename alone can't tell this
    script which half to read, so the caller passes --section "<heading text>" to
    scope the scan instead of linting the whole file."""
    headings = []
    for idx, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            headings.append((idx, len(m.group(1)), m.group(2)))

    target = None
    for h_idx, level, text in headings:
        if section.lower() in text.lower():
            target = (h_idx, level)
            break
    if target is None:
        return None

    start_idx, level = target
    end_idx = len(lines)
    for h_idx, h_level, _text in headings:
        if h_idx > start_idx and h_level <= level:
            end_idx = h_idx
            break
    return start_idx, end_idx


def lint_material(path, metric_rows, date_rows, credential_rows, all_rows, section=None):
    """Returns (findings: list[Finding], stats: FileStats, error: str|None, fatal: bool).
    `error` is set (and findings/stats empty) if the file could not be read, OR if
    `section` was given but no matching heading was found -- deliberately NOT falling
    back to scanning the whole file in that case, since for gap-analysis.md that
    fallback would scan the out-of-scope JD-requirements section too.

    `fatal` distinguishes the two: a read failure is equivalent to a missing file
    (the contract says the script exits non-zero for that); a not-found --section is
    a usage/contract mismatch between the caller and this invocation, not a missing
    file, so it does NOT flip the exit code -- it's surfaced in the report instead."""
    stats = FileStats()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], stats, str(exc), True

    all_lines = text.splitlines()
    if section is not None:
        bounds = find_section_bounds(all_lines, section)
        if bounds is None:
            return (
                [],
                stats,
                f'--section "{section}" not found -- no markdown heading in this '
                "file matched, so nothing was scanned (refusing to silently fall "
                "back to linting the whole file).",
                False,
            )
        start_idx, end_idx = bounds
        scan_lines = all_lines[start_idx:end_idx]
        line_offset = start_idx
    else:
        scan_lines = all_lines
        line_offset = 0

    findings_map = {}
    # Collapsed buckets used ONLY when the registry has zero rows of a given kind:
    # every candidate claim of that kind is guaranteed to be unverifiable, so they
    # are grouped into a single finding naming the registry gap, instead of spewing
    # one top-level ERROR per claim (spec's "must not crash or spew" requirement for
    # a thin/near-empty registry).
    collapsed_metrics = []
    collapsed_dates = []
    collapsed_credentials = []

    in_frontmatter = False

    for offset, raw_line in enumerate(scan_lines):
        i = line_offset + offset + 1  # 1-indexed line number in the ORIGINAL file
        line = raw_line

        # Frontmatter only appears at the very top of a whole file, so this only
        # ever fires when scanning from the real start of the file (section=None,
        # or a --section match that happens to begin at line 1).
        if i == 1 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            continue

        if METADATA_DATE_LINE_RE.match(line):
            stats.ignored_metadata_lines += 1
            continue
        if PAGE_FOOTER_LINE_RE.match(line.strip()):
            stats.ignored_page += 1
            continue

        working = line
        for pat, counter in (
            (PHONE_RE, "ignored_phone"),
            (ADDRESS_ZIP_RE, "ignored_zip"),
            (STREET_ADDRESS_RE, "ignored_street"),
            (PAGE_INLINE_RE, "ignored_page"),
        ):
            matches = list(pat.finditer(working))
            if matches:
                setattr(stats, counter, getattr(stats, counter) + len(matches))
                working = blank_spans(working, [m.span() for m in matches])

        # ---- Check 3: date ranges ------------------------------------------------
        date_spans = []
        for m in DATE_RANGE_RE.finditer(working):
            date_spans.append(m.span())
            stats.dates_checked += 1
            start_tok, end_tok = m.group(1), m.group(2)
            start_month, start_year = parse_date_token(start_tok)
            if start_year is None:
                continue
            end_open = bool(OPEN_ENDED_RE.fullmatch(end_tok.strip()))
            end_month, end_year = (None, None) if end_open else parse_date_token(end_tok)

            matches = []
            near_miss_reason = None  # first specific rejection reason we hit, if any
            for r in date_rows:
                ok, reason = date_row_matches(r, start_month, start_year, end_open, end_month, end_year)
                if ok:
                    matches.append(r)
                elif reason and near_miss_reason is None:
                    near_miss_reason = reason
            if matches:
                status, row = best_provenance(matches)
                if status == "clean":
                    stats.dates_clean += 1
                else:
                    record(
                        findings_map,
                        "WARN",
                        "dates",
                        f'Date range "{m.group(0)}" traces to facts.md row {row.id}, '
                        "which is self-reported (no paper trail) rather than "
                        "résumé-sourced or attested.",
                        i,
                        line.strip(),
                    )
                continue
            if not date_rows:
                collapsed_dates.append((i, line.strip(), m.group(0)))
            elif near_miss_reason:
                # A specific, explainable contradiction (currently: open-ended vs.
                # closed) beats the generic "no match" message -- see date_row_matches.
                record(
                    findings_map,
                    "ERROR",
                    "dates",
                    f'Date range "{m.group(0)}" contradicts the registry: {near_miss_reason}.',
                    i,
                    line.strip(),
                )
            else:
                record(
                    findings_map,
                    "ERROR",
                    "dates",
                    f'Date range "{m.group(0)}" does not match any `date` row in facts.md.',
                    i,
                    line.strip(),
                )

        working_no_dates = blank_spans(working, date_spans)

        # ---- Check 4: credentials -------------------------------------------------
        cred_spans = []
        for m in find_credential_matches(working_no_dates):
            cred_spans.append(m.span())
            stats.credentials_checked += 1
            mention = m.group(0)
            mention_norm = normalize_credential_text(mention)
            matches = [r for r in credential_rows if credential_row_matches(r, mention_norm)]
            if matches:
                status, row = best_provenance(matches)
                if status == "clean":
                    stats.credentials_clean += 1
                else:
                    record(
                        findings_map,
                        "WARN",
                        "credentials",
                        f'Credential "{mention}" traces to facts.md row {row.id}, '
                        "which is self-reported (no paper trail) rather than "
                        "résumé-sourced or attested.",
                        i,
                        line.strip(),
                    )
                continue
            if not credential_rows:
                collapsed_credentials.append((i, line.strip(), mention))
            else:
                record(
                    findings_map,
                    "ERROR",
                    "credentials",
                    f'Credential "{mention}" does not match any `credential` row in facts.md.',
                    i,
                    line.strip(),
                )

        working_no_cred = blank_spans(working_no_dates, cred_spans)

        # ---- Check 2 / Check 7: metrics and zero-source ---------------------------
        for m in NUM_TOKEN_RE.finditer(working_no_cred):
            token = m.group(0)
            value = parse_number(token)
            if value is None:
                continue
            if is_probable_calendar_year(token, value):
                stats.ignored_years += 1
                continue

            stats.metrics_checked += 1
            metric_matches = [r for r in metric_rows if row_has_number(r, value)]
            if metric_matches:
                status, row = best_provenance(metric_matches)
                if status == "clean":
                    stats.metrics_clean += 1
                else:
                    record(
                        findings_map,
                        "WARN",
                        "metrics",
                        f'"{token}" traces to facts.md row {row.id}, which is '
                        "self-reported (no paper trail) rather than "
                        "résumé-sourced or attested.",
                        i,
                        line.strip(),
                    )
                continue

            # No metric-kind match. Before calling it zero-source, check whether it
            # matches a row filed under a DIFFERENT kind -- that's a real fact, just
            # mis-classified (or the material rendered something that happens to
            # equal a title/date/credential's number), and check 2 requires a
            # metric-kind row specifically.
            other_matches = [r for r in all_rows if r.kind != "metric" and row_has_number(r, value)]
            if other_matches:
                row = other_matches[0]
                record(
                    findings_map,
                    "ERROR",
                    "metrics",
                    f'"{token}" matches facts.md row {row.id}, but that row is kind '
                    f'"{row.kind}", not "metric" -- check 2 requires a metric-kind row.',
                    i,
                    line.strip(),
                )
                continue

            if not metric_rows:
                collapsed_metrics.append((i, line.strip(), token))
            else:
                record(
                    findings_map,
                    "ERROR",
                    "zero-source",
                    f'"{token}" does not match any row in facts.md, of any kind.',
                    i,
                    line.strip(),
                )

    # Emit the collapsed "registry has zero rows of this kind" findings, one per kind.
    if collapsed_metrics:
        f = Finding(
            "ERROR",
            "zero-source",
            "facts.md contains 0 metric rows -- none of the numeric claims below could "
            "be checked. This is not a clean bill of health; it means verification is "
            "impossible until metric rows are added to the registry.",
        )
        for line_no, snippet, token in collapsed_metrics:
            f.add(line_no, f'{snippet}  [claim: "{token}"]')
        findings_map[("ERROR", "zero-source", "__collapsed_metrics__")] = f

    if collapsed_dates:
        f = Finding(
            "ERROR",
            "dates",
            "facts.md contains 0 date rows -- none of the date ranges below could be "
            "checked.",
        )
        for line_no, snippet, token in collapsed_dates:
            f.add(line_no, f'{snippet}  [claim: "{token}"]')
        findings_map[("ERROR", "dates", "__collapsed_dates__")] = f

    if collapsed_credentials:
        f = Finding(
            "ERROR",
            "credentials",
            "facts.md contains 0 credential rows -- none of the credentials below "
            "could be checked.",
        )
        for line_no, snippet, token in collapsed_credentials:
            f.add(line_no, f'{snippet}  [claim: "{token}"]')
        findings_map[("ERROR", "credentials", "__collapsed_credentials__")] = f

    findings = list(findings_map.values())
    return findings, stats, None, False


# --------------------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------------------

SEVERITY_ORDER = {"ERROR": 0, "WARN": 1}
CHECK_LABEL = {
    "metrics": "check 2 · metrics",
    "dates": "check 3 · dates",
    "credentials": "check 4 · credentials",
    "zero-source": "check 7 · zero-source",
}


def render_finding(f):
    out = [f"- **[{CHECK_LABEL.get(f.check, f.check)}] {f.severity}** -- {f.message}"]
    for line_no, snippet in f.occurrences:
        snippet = snippet if len(snippet) <= 160 else snippet[:157] + "..."
        out.append(f"  - line {line_no}: `{snippet}`")
    return "\n".join(out)


def render_report(registry_path, rows, registry_notes, results):
    """`results` is a list of (path, findings_or_None, stats_or_None, error_or_None)."""
    kind_counts = defaultdict(int)
    for r in rows:
        kind_counts[r.kind] += 1

    total_error = 0
    total_warn = 0
    for _path, findings, _stats, _err in results:
        if not findings:
            continue
        for f in findings:
            n = len(f.occurrences)
            if f.severity == "ERROR":
                total_error += n
            else:
                total_warn += n

    out = []
    out.append("# Honesty Lint Report")
    out.append("")
    out.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    out.append(
        f"Registry: `{registry_path}` -- {len(rows)} row(s) "
        f"({kind_counts.get('metric', 0)} metric, {kind_counts.get('date', 0)} date, "
        f"{kind_counts.get('credential', 0)} credential, {kind_counts.get('title', 0)} title, "
        f"{kind_counts.get('deliverable', 0)} deliverable)"
    )
    for note in registry_notes:
        out.append(f"Registry note: {note}")
    out.append(f"Materials checked: {len(results)}")
    out.append(f"**Findings: {total_error} ERROR, {total_warn} WARN**")
    out.append("")
    out.append(
        "Scope: this script verifies numbers, date ranges, and credentials against "
        "facts.md only. It does not enumerate prose or causal claims (e.g. \"drove "
        "product strategy\") -- that ledger is built separately by the tracer "
        "subagent, per docs/apply-package-spec.md §5.6. A finding here means a number/date/"
        "credential could not be traced; a claim not appearing here was never checked "
        "by this script, not certified true by it."
    )
    out.append("")

    for path, findings, stats, err in results:
        out.append(f"## {path}")
        out.append("")
        if err is not None:
            out.append(f"**ERROR:** {err}")
            out.append("")
            continue

        errors = sorted(
            (f for f in findings if f.severity == "ERROR"), key=lambda f: f.occurrences[0][0]
        )
        warns = sorted(
            (f for f in findings if f.severity == "WARN"), key=lambda f: f.occurrences[0][0]
        )

        if not errors and not warns:
            out.append("No findings -- every number, date range, and credential this "
                        "script checked traced cleanly to facts.md.")
        else:
            for f in errors + warns:
                out.append(render_finding(f))

        out.append("")
        out.append(
            f"_Checked: {stats.metrics_checked} numeric claim(s) "
            f"({stats.metrics_clean} traced cleanly), "
            f"{stats.dates_checked} date range(s) ({stats.dates_clean} traced cleanly), "
            f"{stats.credentials_checked} credential mention(s) "
            f"({stats.credentials_clean} traced cleanly). "
            f"Ignored: {stats.ignored_years} calendar-year-like number(s), "
            f"{stats.ignored_phone} phone number(s), {stats.ignored_zip} ZIP code(s), "
            f"{stats.ignored_street} street address(es), {stats.ignored_page} page "
            f"marker(s), {stats.ignored_metadata_lines} document-metadata line(s)._"
        )
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render_missing_registry_report(resolved_path, argv_path):
    return (
        "# Honesty Lint Report\n\n"
        f"**ERROR -- registry not found.** Looked for `{argv_path}`, resolved to "
        f"`{resolved_path}`, and it does not exist.\n\n"
        "No claims could be checked. Run the facts.md onboarding step (spec section 7 "
        "migration branch), or pass `--registry PATH` if the registry lives somewhere "
        "else.\n"
    )


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="honesty_lint.py",
        description=(
            "Verify the numeric subset of claims (metrics, dates, credentials) in one "
            "or more application materials against facts.md. Passive reporter: never "
            "blocks, never edits input, always exits 0 unless a material or the "
            "registry is missing/unreadable."
        ),
    )
    parser.add_argument("materials", nargs="+", help="Path(s) to material markdown file(s).")
    parser.add_argument(
        "--registry", default="facts.md", help="Path to facts.md (default: ./facts.md)."
    )
    parser.add_argument(
        "--report", default=None, help="Optional path to also write the markdown report to."
    )
    parser.add_argument(
        "--section",
        default=None,
        help=(
            "Optional markdown heading text (substring match) to scope the scan to. "
            "Applies to every material passed in this invocation. Needed for "
            'gap-analysis.md: per spec §5.5/§11, only its "What your record '
            "evidences\" section is in lint scope -- the JD-requirements section is "
            "deliberately unchecked, and linting it produces a false-positive storm "
            "of unrelated JD figures. Pass e.g. "
            '--section "What your record evidences" when linting that file.'
        ),
    )
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    if not registry_path.exists():
        report = render_missing_registry_report(registry_path.resolve(), args.registry)
        print(report)
        if args.report:
            Path(args.report).write_text(report, encoding="utf-8")
        return 1

    rows, registry_notes = parse_registry(registry_path)
    metric_rows = [r for r in rows if r.kind == "metric"]
    date_rows = [r for r in rows if r.kind == "date"]
    credential_rows = [r for r in rows if r.kind == "credential"]

    results = []
    any_missing_or_unreadable = False
    for m in args.materials:
        p = Path(m)
        if not p.exists():
            results.append((p, None, None, "file not found"))
            any_missing_or_unreadable = True
            continue
        findings, stats, err, fatal = lint_material(
            p, metric_rows, date_rows, credential_rows, rows, section=args.section
        )
        if fatal:
            any_missing_or_unreadable = True
        results.append((p, findings, stats, err))

    report = render_report(registry_path, rows, registry_notes, results)
    print(report)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")

    return 1 if any_missing_or_unreadable else 0


if __name__ == "__main__":
    sys.exit(main())
