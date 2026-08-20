<!-- fixture registry: reproduces the exact false-CLEAN bug this suite regression-
     tests. Both rows quote the SAME source sentence, which -- being a verbatim
     résumé line -- names a programs-count figure that neither row's `value` is
     actually about. Pairs with 13-source-text-scope-regression.md. Before the
     fix (row_has_number scanning value + source_text), a claim using that
     figure traced cleanly against either row purely because the digit rides
     along inside the shared quoted sentence -- a false CLEAN, not because any
     row is about that many of anything. After the fix (value only), neither
     row's `value` contains it, so that claim correctly reports zero-source. -->
| id | kind | value | source_text | provenance |
|----|------|-------|--------------|------------|
| g1 | metric | 1,200 students annually | "Managed 3 education programs serving 1,200 students annually across 4 sites" | résumé |
| g2 | metric | 4 sites | "Managed 3 education programs serving 1,200 students annually across 4 sites" | résumé |
