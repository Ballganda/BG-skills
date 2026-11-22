---
"bg-skills": patch
---

The decomp summary's diff window is centred on the instruction that holds the first differing byte, also when that byte is an operand or a displacement. Only the offset a report line leads with is read as its offset, so a jump target or a count elsewhere on a line is never taken for it.
