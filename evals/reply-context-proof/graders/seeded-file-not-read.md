---
# Deterministic: no LLM judge. The canary needs no tool, so a call to a tool
# that can read files means the answer may have come from reading the seeded
# file rather than from the agent's context. Such a run fails.
type: regex
target: trace
pattern: '"type":"tool_use",[^{}]*"name":"(Read|Glob|Grep|Bash|PowerShell|Task|Agent)"'
match: not_contains
---
