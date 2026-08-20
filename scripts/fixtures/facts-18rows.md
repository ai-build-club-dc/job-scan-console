<!-- fixture registry: 18 metric rows (résumé provenance), used only to test the
     NUM_TOKEN_RE two-digit citation guard (see honesty_lint.py
     iter_claim_number_matches / _is_alphanumeric_identifier_tail). Row citations
     like "F18" and "R11" must not leak their tail digits ("8", "1") as phantom
     claim numbers. None of these 18 values collide with 1, 8, 11, 18, or 47, so a
     leaked digit -- or the real unbacked "47" used as this fixture's control --
     would show up unambiguously as its own zero-source ERROR. -->
| id | kind | value | source_text | provenance |
|----|------|-------|--------------|------------|
| f1 | metric | $100,000 | "grew quarterly revenue to $100,000" | résumé |
| f2 | metric | $101,000 | "grew quarterly revenue to $101,000" | résumé |
| f3 | metric | $102,000 | "grew quarterly revenue to $102,000" | résumé |
| f4 | metric | $103,000 | "grew quarterly revenue to $103,000" | résumé |
| f5 | metric | $104,000 | "grew quarterly revenue to $104,000" | résumé |
| f6 | metric | $105,000 | "grew quarterly revenue to $105,000" | résumé |
| f7 | metric | $106,000 | "grew quarterly revenue to $106,000" | résumé |
| f8 | metric | $107,000 | "grew quarterly revenue to $107,000" | résumé |
| f9 | metric | $108,000 | "grew quarterly revenue to $108,000" | résumé |
| f10 | metric | $109,000 | "grew quarterly revenue to $109,000" | résumé |
| f11 | metric | $110,000 | "grew quarterly revenue to $110,000" | résumé |
| f12 | metric | $111,000 | "grew quarterly revenue to $111,000" | résumé |
| f13 | metric | $112,000 | "grew quarterly revenue to $112,000" | résumé |
| f14 | metric | $113,000 | "grew quarterly revenue to $113,000" | résumé |
| f15 | metric | $114,000 | "grew quarterly revenue to $114,000" | résumé |
| f16 | metric | $115,000 | "grew quarterly revenue to $115,000" | résumé |
| f17 | metric | $116,000 | "grew quarterly revenue to $116,000" | résumé |
| f18 | metric | $117,000 | "grew quarterly revenue to $117,000" | résumé |
