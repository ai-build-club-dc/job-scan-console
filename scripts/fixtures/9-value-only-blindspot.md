<!-- fixture: documents a known limitation that SURVIVES the value-only fix, not a
     correctness claim. The floor figure on the claim line below happens to equal,
     digit for digit, the floor figure in facts.md row f3's own `value` ("5+") --
     not just its source_text -- so restricting the matcher to scan `value` alone
     (see FactRow.text()) does not change this fixture's outcome. This is a
     DIFFERENT, narrower limitation than the source_text-widening bug that fix
     addresses: row_has_number compares numeric value only, with no awareness of
     what the number is a count OF, so a claim about "5+ regional partners" still
     traces cleanly against a row recorded for "5+ years of experience." That is
     current, documented behavior to watch, not asserted as "correct" -- see the
     test runner's comment on this fixture and the final report. Fixing it would
     require unit/context-aware matching, which is out of scope here and risks its
     own regression (e.g. falsely rejecting "5+ years" against a differently-
     worded but equally-valid registry row). -->

# Tailored Resume - Jordan Rivera

### Product Manager, Acme Corp (Jan 2022 - Mar 2024)
- Coordinated a program serving 5+ regional partners.
