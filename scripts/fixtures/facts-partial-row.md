<!-- fixture registry: a valid header and two valid data rows, with one malformed
     row (only three cells) sandwiched between them. Probes that parse_registry
     skips the malformed row with a note and still keeps the valid rows around it,
     rather than truncating the table or crashing. -->
| id | kind | value | source_text | provenance |
|----|------|-------|--------------|------------|
| f1 | metric | $120,000 | "grew quarterly revenue to $120,000" | résumé |
| broken row with only three cells | metric | oops
| f2 | metric | 5+ | 5+ years experience | resume
