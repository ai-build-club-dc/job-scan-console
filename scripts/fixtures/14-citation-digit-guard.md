<!-- fixture: alphanumeric row citations sitting next to a real, genuinely
     unbacked two-digit number on the same line. Regression fixture for the
     NUM_TOKEN_RE two-digit citation bug: the LEFT guard used to only block a
     digit directly preceded by a letter, so it caught the first digit of a
     citation but not the rest of a multi-digit id, leaking its tail digit as
     a phantom zero-source claim -- while a single-digit citation was fully
     blocked, which hid the bug until a registry grew past single digits and
     citations started needing two-digit ids. The citations here must now
     produce zero findings; the real unbacked number must still ERROR
     (control). Paired with the metrics-only registry fixture in this same
     directory (no date rows in it, so this material deliberately carries no
     date-range heading either). -->

# Tailored Resume - Jordan Rivera

## Experience

### Senior Product Manager, Acme Corp
- Onboarded 47 new enterprise clients in six months (F18, R11).
