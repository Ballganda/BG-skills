---
# Checks the trace, not only the last message: grilling may dispatch a
# sub-agent and send a follow-up after the first round. The pattern stays
# inside one JSON string, so it matches a single message that numbers at least
# three questions (Q1, Q2, Q3), each followed by a recommendation arrow. The
# grilling skill text shows only Q1 and Q2, so loading it cannot match.
type: regex
target: trace
pattern: 'Q1\*\*(?:[^"\\]|\\.)*?➡(?:[^"\\]|\\.)*?Q2\*\*(?:[^"\\]|\\.)*?➡(?:[^"\\]|\\.)*?Q3\*\*(?:[^"\\]|\\.)*?➡'
---
