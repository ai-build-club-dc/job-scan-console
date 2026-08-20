#!/usr/bin/env python3
"""
test_honesty_lint.py -- regression suite for honesty_lint.py.

Standard library only (unittest + subprocess). Invokes the linter the way a real
caller does -- as a subprocess against the CLI -- so this suite also covers
argument handling and stdout formatting, not just internal functions.

Every expectation in this file (ERROR/WARN counts, exact finding-message
substrings, "checked" stats) was derived by actually running honesty_lint.py
against the fixtures in fixtures/ and reading its real stdout -- not guessed.
Where the script's current behavior looked questionable, that is called out in
comments on the relevant test rather than silently encoded as "correct" --
see especially test_value_only_match_documents_current_blind_spot and
test_registry_error_messages_hardcode_facts_md_literal below.

Run from anywhere:
    python3 scripts/test_honesty_lint.py
    (or, from the repo root:  python3 scripts/test_honesty_lint.py)

No arguments, no environment setup, no network required.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LINT_SCRIPT = SCRIPT_DIR / "honesty_lint.py"
FIXTURES_DIR = SCRIPT_DIR / "fixtures"

FINDINGS_RE = re.compile(r"\*\*Findings: (\d+) ERROR, (\d+) WARN\*\*")


def run_lint(materials, registry=None, section=None, cwd=None, extra_args=None):
    """Invoke honesty_lint.py as a subprocess, the way a real caller would.

    `materials` may be a single filename or a list of filenames, resolved
    relative to FIXTURES_DIR unless `cwd` is given (in which case they're
    passed through as-is and resolved relative to `cwd`).
    Returns (returncode, stdout).
    """
    if isinstance(materials, str):
        materials = [materials]
    argv = [sys.executable, str(LINT_SCRIPT), *materials]
    if registry is not None:
        argv += ["--registry", registry]
    if section is not None:
        argv += ["--section", section]
    if extra_args:
        argv += extra_args
    proc = subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else str(FIXTURES_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout + proc.stderr


def counts(stdout):
    """Extract (error_count, warn_count) from the report header. Fails loudly
    (rather than returning None) if the header line is missing, since every
    successful-parse invocation of this script must print it."""
    m = FINDINGS_RE.search(stdout)
    if not m:
        raise AssertionError(f"Could not find a '**Findings: N ERROR, N WARN**' "
                              f"line in output:\n{stdout}")
    return int(m.group(1)), int(m.group(2))


class HonestyLintTestCase(unittest.TestCase):
    """Adds an assertion helper for the count line on top of unittest.TestCase."""

    def assert_counts(self, stdout, expected_errors, expected_warns, msg=""):
        got = counts(stdout)
        self.assertEqual(
            got,
            (expected_errors, expected_warns),
            f"{msg}\nExpected (errors, warns)={(expected_errors, expected_warns)}, "
            f"got {got}.\nFull output:\n{stdout}",
        )


# --------------------------------------------------------------------------------------
# 1. Each existing scratch fixture's scenario
# --------------------------------------------------------------------------------------

class TestCleanResume(HonestyLintTestCase):
    """1-clean-resume.md: every number, date range, and credential traces cleanly.
    Also the only fixture exercising frontmatter skipping and the phone/ZIP/street
    exclusion regexes."""

    def test_clean_resume_has_no_findings(self):
        rc, out = run_lint("1-clean-resume.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 0, 0)
        self.assertIn(
            "No findings -- every number, date range, and credential this script "
            "checked traced cleanly to facts.md.",
            out,
        )
        self.assertIn(
            "_Checked: 4 numeric claim(s) (4 traced cleanly), "
            "2 date range(s) (2 traced cleanly), "
            "1 credential mention(s) (1 traced cleanly). "
            "Ignored: 0 calendar-year-like number(s), 1 phone number(s), "
            "1 ZIP code(s), 1 street address(es), 0 page marker(s), "
            "0 document-metadata line(s)._",
            out,
        )


class TestFabricatedMetric(HonestyLintTestCase):
    """2-fabricated-metric.md: one dollar figure with no home in facts.md at all --
    check 7 (zero-source) ERROR. The neighboring clean tenure claim must not also
    be flagged."""

    def test_fabricated_metric_is_zero_source_error(self):
        rc, out = run_lint("2-fabricated-metric.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 1, 0)
        self.assertIn(
            '**[check 7 · zero-source] ERROR** -- "$500,000" does not match any '
            "row in facts.md, of any kind.",
            out,
        )
        # the tenure claim on the next line traces cleanly and is not itself a
        # separate finding
        self.assertIn("_Checked: 2 numeric claim(s) (1 traced cleanly)", out)


class TestProseBoundary(HonestyLintTestCase):
    """3-prose-boundary.md: a pure prose/causal claim with no digits sits next to a
    clean numeric claim. The prose sentence must produce zero findings -- the
    script has nothing to say about it by design, not because it was judged true."""

    def test_prose_claim_produces_no_findings(self):
        rc, out = run_lint("3-prose-boundary.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 0, 0)
        self.assertIn("_Checked: 1 numeric claim(s) (1 traced cleanly)", out)


class TestSelfReportedWarn(HonestyLintTestCase):
    """4-self-reported-warn.md: a metric and a credential that both trace to
    facts.md, but only to a self-reported row -- both should downgrade to WARN,
    not pass silently and not escalate to ERROR."""

    def test_self_reported_matches_are_warn_not_error(self):
        rc, out = run_lint("4-self-reported-warn.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 0, 2)
        self.assertIn(
            '**[check 2 · metrics] WARN** -- "92%" traces to facts.md row f4, '
            "which is self-reported (no paper trail) rather than résumé-sourced "
            "or attested.",
            out,
        )
        self.assertIn(
            '**[check 4 · credentials] WARN** -- Credential "MBA" traces to '
            "facts.md row f8, which is self-reported (no paper trail) rather "
            "than résumé-sourced or attested.",
            out,
        )


class TestThinRegistry(HonestyLintTestCase):
    """5-thin-registry.md against facts-thin.md (title/credential rows only, zero
    metric rows, zero date rows). Probes the collapsed "registry has zero rows of
    this kind" reporting path -- one finding per kind, not one per claim."""

    def test_thin_registry_collapses_findings_by_kind(self):
        rc, out = run_lint("5-thin-registry.md", registry="facts-thin.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 3, 0)
        self.assertIn(
            "facts.md contains 0 date rows -- none of the date ranges below "
            "could be checked.",
            out,
        )
        self.assertIn(
            "facts.md contains 0 metric rows -- none of the numeric claims "
            "below could be checked.",
            out,
        )
        # the collapsed metric finding aggregates BOTH numeric claims (the "4
        # volunteers" and the "3.8" GPA) under one finding, not two
        self.assertIn('[claim: "4"]', out)
        self.assertIn('[claim: "3.8"]', out)
        # the credential (B.A. in Communications) DOES have a registry row and
        # traces cleanly -- it must not appear in the collapsed metric/date findings
        self.assertIn("1 credential mention(s) (1 traced cleanly)", out)


class TestStressTest(HonestyLintTestCase):
    """7-stress-test.md: office-software abbreviations must not false-positive as
    credentials; a role dated Jun 2020 must not match the registry's differently-
    dated Jun role (plain "no matching date row", not the open-ended path)."""

    def test_office_abbreviations_are_not_credentials(self):
        rc, out = run_lint("7-stress-test.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 1, 0)
        self.assertIn("0 credential mention(s) (0 traced cleanly)", out)

    def test_mismatched_start_date_is_plain_no_match_error(self):
        rc, out = run_lint("7-stress-test.md", registry="facts.md")
        self.assertIn(
            '**[check 3 · dates] ERROR** -- Date range "Jun 2020 - Present" does '
            "not match any `date` row in facts.md.",
            out,
        )


class TestOpenEndedMismatch(HonestyLintTestCase):
    """8-open-ended-mismatch.md: material claims a role is still "Present", but
    facts.md records that start date as having ended in a specific year. Must
    produce the SPECIFIC open-ended-vs-closed contradiction message, not a generic
    "no matching row" message."""

    def test_open_ended_contradiction_has_specific_message(self):
        rc, out = run_lint("8-open-ended-mismatch.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 1, 0)
        self.assertIn(
            '**[check 3 · dates] ERROR** -- Date range "Jan 2022 - Present" '
            "contradicts the registry: facts.md row f5 covers this start date "
            "but records it as ending in 2024, not still ongoing.",
            out,
        )


class TestUnitBlindSpot(HonestyLintTestCase):
    """9-value-only-blindspot.md.

    NOTE ON WHY THIS TEST IS NAMED "documents_unit_blind_spot" AND NOT
    "is_correctly_clean": this fixture used to be read as evidence of the
    source_text-widening bug (see TestSourceTextScopeRegression below, which is
    the fix for that bug). It is not that bug: facts.md row f3's `value` field is
    itself "5+" -- the match happens through `value`, not through source_text --
    so scoping the matcher to `value` only (the fix applied to honesty_lint.py)
    does NOT change this fixture's outcome. What remains is a narrower, still-live
    limitation: row_has_number matches a claim to a registry row purely by numeric
    VALUE, with no awareness of what the number is a count OF. This fixture's
    claim ("regional partners") happens to carry the same bare figure as facts.md
    row f3's tenure claim ("years of experience"), and the script reports it as
    fully clean. That is not a correctness claim -- it is the script's documented,
    current behavior, worth flagging on review, and intentionally NOT tightened
    here: unit-aware matching is out of scope and would risk false-ERRORing
    legitimately-backed claims like "5+ years" in 1-clean-resume.md. See the final
    report for a plainer statement of this concern.
    """

    def test_unit_blind_spot_survives_the_value_only_fix(self):
        rc, out = run_lint("9-value-only-blindspot.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 0, 0)
        self.assertIn(
            "No findings -- every number, date range, and credential this "
            "script checked traced cleanly to facts.md.",
            out,
        )


class TestWrongKindRow(HonestyLintTestCase):
    """9b-wrong-kind.md against facts-wrongkind.md: the number DOES appear in the
    registry, but only under kind "deliverable", not "metric". Must be reported as
    a distinct "wrong kind" ERROR, not folded into zero-source."""

    def test_wrong_kind_row_is_a_distinct_error(self):
        rc, out = run_lint("9b-wrong-kind.md", registry="facts-wrongkind.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 1, 0)
        self.assertIn(
            '**[check 2 · metrics] ERROR** -- "17" matches facts.md row d1, but '
            'that row is kind "deliverable", not "metric" -- check 2 requires a '
            "metric-kind row.",
            out,
        )
        # must NOT be reported as the generic zero-source finding
        self.assertNotIn("check 7 · zero-source", out)


class TestGarbledRegistry(HonestyLintTestCase):
    """facts-garbled.md is not a markdown table at all. Must not crash; must
    report the registry as empty with an explanatory note, and treat every
    numeric/date claim in the material as zero-source."""

    def test_garbled_registry_reports_empty_with_note_and_does_not_crash(self):
        rc, out = run_lint("2-fabricated-metric.md", registry="facts-garbled.md")
        self.assertEqual(rc, 0)
        self.assertIn(
            "0 row(s) (0 metric, 0 date, 0 credential, 0 title, 0 deliverable)",
            out,
        )
        self.assertIn(
            'Registry note: Could not find a table header "| id | kind | value | '
            'source_text | provenance |" anywhere in facts.md. Treating the '
            "registry as empty -- every numeric/date/credential claim below will "
            "report as zero-source until this is fixed.",
            out,
        )
        self.assert_counts(out, 3, 0)


class TestPartialRowRegistry(HonestyLintTestCase):
    """facts-partial-row.md: a valid header and two valid rows with one malformed
    (3-cell) row sandwiched between them. The malformed row must be skipped with a
    note, and the valid rows on either side must still be usable."""

    def test_malformed_row_is_skipped_valid_rows_still_used(self):
        rc, out = run_lint("2-fabricated-metric.md", registry="facts-partial-row.md")
        self.assertEqual(rc, 0)
        self.assertIn(
            "2 row(s) (2 metric, 0 date, 0 credential, 0 title, 0 deliverable)",
            out,
        )
        self.assertIn(
            "Registry note: facts.md line 8: skipped (expected 5 columns, "
            "found 3): '| broken row with only three cells | metric | oops'",
            out,
        )
        # f2's "5+" is still usable despite the broken row between it and f1
        self.assert_counts(out, 2, 0)
        self.assertIn("_Checked: 2 numeric claim(s) (1 traced cleanly)", out)


class TestGapAnalysisSection(HonestyLintTestCase):
    """10-gap-analysis.md: JD-derived figures live in one section, candidate
    claims in another. Covered in detail by TestSectionFlag below; this class just
    confirms the whole-file (no --section) baseline this fixture is measured
    against."""

    def test_whole_file_scan_includes_jd_section_figures(self):
        rc, out = run_lint("10-gap-analysis.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 3, 2)
        self.assertIn('"7+" does not match any row in facts.md, of any kind.', out)
        self.assertIn(
            '"$2,000,000" does not match any row in facts.md, of any kind.', out
        )
        self.assertIn(
            '"$999,000,000" does not match any row in facts.md, of any kind.', out
        )


class TestSourceTextScopeRegression(HonestyLintTestCase):
    """13-source-text-scope-regression.md against facts-source-text-regression.md:
    the exact false-CLEAN bug honesty_lint.py was fixed for. Both registry rows
    quote the SAME source sentence, which -- being a verbatim résumé line --
    names a programs-count figure neither row's `value` is actually about. Before
    the fix (row_has_number scanning value + source_text), a claim using that
    figure traced cleanly against either row purely because the digit rode along
    inside the shared quoted sentence. That is a false CLEAN: no row is about
    that many of anything, so a claim built on it should ERROR as zero-source,
    not pass as verified."""

    def test_number_only_in_shared_source_text_is_zero_source_error(self):
        rc, out = run_lint(
            "13-source-text-scope-regression.md",
            registry="facts-source-text-regression.md",
        )
        self.assertEqual(rc, 0)
        # 2 ERROR: the bug claim ("3") and the control ("9"). If either failed to
        # ERROR, this test would catch it -- and the control means an always-ERROR
        # matcher can't pass this test vacuously either.
        self.assert_counts(out, 2, 0)
        self.assertIn(
            '**[check 7 · zero-source] ERROR** -- "3" does not match any row in '
            "facts.md, of any kind.",
            out,
        )
        self.assertIn(
            '**[check 7 · zero-source] ERROR** -- "9" does not match any row in '
            "facts.md, of any kind.",
            out,
        )

    def test_registry_rows_are_still_live_through_their_own_values(self):
        """Proves the fix isn't over-tight: g1 ("1,200 students annually") and g2
        ("4 sites") must still trace cleanly when a claim uses THEIR OWN value,
        not just the shared source_text -- 2 of the 4 numeric claims checked, and
        neither figure appears as an ERROR/WARN finding anywhere in the report."""
        rc, out = run_lint(
            "13-source-text-scope-regression.md",
            registry="facts-source-text-regression.md",
        )
        self.assertIn("_Checked: 4 numeric claim(s) (2 traced cleanly)", out)
        self.assertNotIn('"1,200" does not match', out)
        self.assertNotIn('"4" does not match', out)


class TestTwoDigitCitationRegression(HonestyLintTestCase):
    """14-citation-digit-guard.md against facts-18rows.md: the two-digit row
    citation bug in NUM_TOKEN_RE. Its LEFT guard, `(?<![A-Za-z])`, is a
    fixed-width lookbehind, so it only ever blocks the FIRST digit right after
    a letter. A single-digit citation like "F4" is fully blocked -- there's no
    second position for finditer to retry -- but a two-or-more-digit citation
    like "F18" or "R11" isn't: after "1" is blocked, finditer tries "8" next,
    which is preceded by a DIGIT rather than a letter, so the old guard let it
    through as a bare claim number ("8"). Same for "R11" -> "1". This stayed
    invisible in testing as long as every registry fit in single digits; it
    surfaced once a registry passed 9 rows and citations needed two digits."""

    def test_two_digit_row_citations_produce_no_findings(self):
        rc, out = run_lint(
            "14-citation-digit-guard.md", registry="facts-18rows.md"
        )
        self.assertEqual(rc, 0)
        # Only the real unbacked "47" ERRORs -- "F18" and "R11" must not
        # surface as phantom "8" / "1" zero-source findings.
        self.assert_counts(out, 1, 0)
        self.assertNotIn('"8" does not match', out)
        self.assertNotIn('"1" does not match', out)
        # exactly 1 numeric claim was even considered: proves the citations
        # were never extracted as claims at all, not just filtered afterward.
        self.assertIn("_Checked: 1 numeric claim(s) (0 traced cleanly)", out)

    def test_real_unbacked_two_digit_number_still_errors(self):
        """Control: a genuine unbacked two-digit number on the SAME line as
        the citations must still ERROR as zero-source. Guards against a
        trivially over-broad fix (e.g. one that blanks all digits near
        letters) that would silently swallow real findings too."""
        rc, out = run_lint(
            "14-citation-digit-guard.md", registry="facts-18rows.md"
        )
        self.assertIn(
            '**[check 7 · zero-source] ERROR** -- "47" does not match any '
            "row in facts.md, of any kind.",
            out,
        )


# --------------------------------------------------------------------------------------
# 2. The LLM credential regression, and its neighboring degree patterns
# --------------------------------------------------------------------------------------

class TestLLMCredentialRegression(HonestyLintTestCase):
    """11-llm-credential-regression.md: the exact regression this suite exists
    for. Bare "LLM" (in any of its ordinary AI-work phrasings) must produce NO
    credential finding. The law degree, written the way a résumé actually writes
    it (period form, or bare immediately before "in"/"of"), must still fire."""

    def test_bare_llm_forms_produce_no_credential_finding(self):
        rc, out = run_lint("11-llm-credential-regression.md", registry="facts.md")
        self.assertEqual(rc, 0)
        # exactly 3 credential mentions were even considered -- proves the three
        # bare/hyphenated/"an ... agent" AI-work forms were never candidates at all
        self.assertIn("3 credential mention(s) (0 traced cleanly)", out)
        self.assertNotIn('Credential "LLM-based"', out)
        # none of the three AI-work lines should be quoted back as a finding
        # snippet at all (checked without pinning to a line number, since that's
        # incidental to fixture-file layout, not to the behavior under test)
        self.assertNotIn(
            "`- Prototyped an LLM-based summarizer over support tickets.`", out
        )
        self.assertNotIn(
            "`- Worked closely with an LLM agent to review pull requests.`", out
        )
        self.assertNotIn(
            "`- Ran a bare LLM evaluation harness against three prompts.`", out
        )

    def test_law_degree_forms_still_detected(self):
        rc, out = run_lint("11-llm-credential-regression.md", registry="facts.md")
        self.assert_counts(out, 3, 0)
        self.assertIn(
            '**[check 4 · credentials] ERROR** -- Credential "LL.M." does not '
            "match any `credential` row in facts.md.",
            out,
        )
        self.assertIn(
            '**[check 4 · credentials] ERROR** -- Credential "LLM" does not '
            "match any `credential` row in facts.md.",
            out,
        )
        self.assertIn("- LL.M. in Taxation, State University.", out)
        self.assertIn("- LLM in Taxation, State University.", out)
        self.assertIn("- LLM of Comparative Law, State University.", out)


class TestDegreeCredentialRegression(HonestyLintTestCase):
    """12-degree-credential-regression.md: confirms the neighboring degree
    patterns (MBA/PhD bare-safe class; B.S./MS-in two-letter class) were not
    disturbed by the LLM fix."""

    def test_mba_phd_bs_ms_all_still_detected_correctly(self):
        rc, out = run_lint("12-degree-credential-regression.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 2, 1)
        self.assertIn("4 credential mention(s) (1 traced cleanly)", out)
        self.assertIn(
            '**[check 4 · credentials] WARN** -- Credential "MBA" traces to '
            "facts.md row f8, which is self-reported (no paper trail) rather "
            "than résumé-sourced or attested.",
            out,
        )
        self.assertIn(
            '**[check 4 · credentials] ERROR** -- Credential "PhD" does not '
            "match any `credential` row in facts.md.",
            out,
        )
        self.assertIn(
            '**[check 4 · credentials] ERROR** -- Credential "B.S." does not '
            "match any `credential` row in facts.md.",
            out,
        )
        # "MS in Computer Science" traces cleanly to f7 -- it's the 4th checked
        # mention and the 1 that traces cleanly, and must not appear as a finding
        self.assertNotIn('Credential "MS"', out)


# --------------------------------------------------------------------------------------
# 3. --section behavior
# --------------------------------------------------------------------------------------

class TestSectionFlag(HonestyLintTestCase):
    """10-gap-analysis.md has JD-requirements figures (out of scope) and
    candidate-evidence figures (in scope) in different ## sections."""

    def test_section_scopes_to_matching_heading(self):
        rc, out = run_lint(
            "10-gap-analysis.md",
            registry="facts.md",
            section="What your record evidences",
        )
        self.assertEqual(rc, 0)
        self.assert_counts(out, 0, 1)
        # the JD-section figures must be completely absent once scoped
        self.assertNotIn("7+", out)
        self.assertNotIn("$2,000,000", out)
        self.assertNotIn("$999,000,000", out)
        self.assertIn(
            '**[check 4 · credentials] WARN** -- Credential "MBA" traces to '
            "facts.md row f8",
            out,
        )

    def test_section_not_found_reports_condition_and_exits_zero(self):
        """A --section value matching no heading must refuse to fall back to
        whole-file scanning, and must NOT flip the exit code -- this is a
        caller/contract mismatch, not a missing-file condition."""
        rc, out = run_lint(
            "10-gap-analysis.md",
            registry="facts.md",
            section="Nonexistent Heading XYZ",
        )
        self.assertEqual(rc, 0, "a not-found --section must not cause a non-zero exit")
        self.assert_counts(out, 0, 0)
        self.assertIn(
            '**ERROR:** --section "Nonexistent Heading XYZ" not found -- no '
            "markdown heading in this file matched, so nothing was scanned "
            "(refusing to silently fall back to linting the whole file).",
            out,
        )
        # confirm it really did refuse to fall back: none of the whole-file
        # findings from the unscoped run appear here
        self.assertNotIn("zero-source", out)
        self.assertNotIn("credentials] WARN", out)


# --------------------------------------------------------------------------------------
# 4. Exit-code contract
# --------------------------------------------------------------------------------------

class TestExitCodeContract(HonestyLintTestCase):
    """Exit 0 for normal operation (including when findings are present).
    Non-zero only for a missing material file or missing registry."""

    def test_exit_zero_with_findings_present(self):
        rc, out = run_lint("2-fabricated-metric.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 1, 0)

    def test_exit_zero_when_fully_clean(self):
        rc, out = run_lint("1-clean-resume.md", registry="facts.md")
        self.assertEqual(rc, 0)
        self.assert_counts(out, 0, 0)

    def test_missing_material_file_is_nonzero_exit(self):
        rc, out = run_lint("does-not-exist.md", registry="facts.md")
        self.assertNotEqual(rc, 0)
        self.assertIn("**ERROR:** file not found", out)

    def test_missing_registry_is_nonzero_exit(self):
        rc, out = run_lint("1-clean-resume.md", registry="does-not-exist-facts.md")
        self.assertNotEqual(rc, 0)
        self.assertIn("**ERROR -- registry not found.**", out)


# --------------------------------------------------------------------------------------
# 5. Additional CLI/contract surface: default registry path, multi-material runs
# --------------------------------------------------------------------------------------

class TestCLIContractSurface(HonestyLintTestCase):
    """Covers invocation paths not exercised by the scenario tests above."""

    def test_default_registry_path_is_facts_md_at_cwd(self):
        """No --registry flag at all: the documented default is ./facts.md
        resolved from the current working directory. fixtures/facts.md is
        deliberately named "facts.md" (no qualifier) so this default-path
        behavior is exercised for real, not simulated with an explicit flag."""
        rc, out = run_lint("1-clean-resume.md", registry=None)
        self.assertEqual(rc, 0)
        self.assertIn("Registry: `facts.md`", out)
        self.assert_counts(out, 0, 0)

    def test_multiple_materials_in_one_invocation_aggregate_counts(self):
        rc, out = run_lint(
            ["1-clean-resume.md", "2-fabricated-metric.md"], registry="facts.md"
        )
        self.assertEqual(rc, 0)
        self.assertIn("Materials checked: 2", out)
        # combined header count: 0 findings from file 1 + 1 ERROR from file 2
        self.assert_counts(out, 1, 0)
        self.assertIn("## 1-clean-resume.md", out)
        self.assertIn("## 2-fabricated-metric.md", out)


# --------------------------------------------------------------------------------------
# 6. Behavior worth a second look -- documented here as observed, not "correct"
# --------------------------------------------------------------------------------------

class TestQuestionableCurrentBehavior(HonestyLintTestCase):
    """These tests pin down behavior this suite's author found surprising while
    building it. They pass against the CURRENT script deliberately -- they exist
    to make a future change to this behavior visible in a diff, not to certify it
    as desired. See the final report for the plain-English version of each."""

    def test_registry_error_messages_hardcode_facts_md_literal(self):
        """Every registry-derived message (missing header, malformed row, wrong-
        kind ERROR, collapsed zero-source finding) prints the literal string
        "facts.md" regardless of what --registry actually pointed at. Confirmed
        here against a registry file named something else entirely."""
        rc, out = run_lint("9b-wrong-kind.md", registry="facts-wrongkind.md")
        self.assertIn(
            'ERROR** -- "17" matches facts.md row d1, but that row is kind '
            '"deliverable"',
            out,
        )
        self.assertIn("Registry: `facts-wrongkind.md`", out)
        # the finding text says "facts.md" even though the registry file is
        # named facts-wrongkind.md -- misleading for any caller using --registry
        self.assertNotIn("facts-wrongkind.md row d1", out)


def main():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed
    print()
    print("=" * 72)
    if failed == 0:
        print(f"PASS: {passed}/{total} tests passed.")
    else:
        print(f"FAIL: {passed}/{total} tests passed, {failed} failed.")
    print("=" * 72)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
