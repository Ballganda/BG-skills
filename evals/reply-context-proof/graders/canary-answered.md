---
# Deterministic: no LLM judge. The seeded CLAUDE.md says the codeword is the
# letters of HERONZULU reversed, so ULUZNOREH appears nowhere in the seeded
# file or the prompt. It can show in the transcript only if the agent read the
# instruction, so this passes only when the file was loaded.
type: regex
target: trace
pattern: 'ULUZNOREH'
---
