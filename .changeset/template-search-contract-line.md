---
"bg-skills": patch
---

Decomp skills (in progress): the contract's permuter line becomes a template-search line (spec #162).

- **Contract.** "Template search: allowed or not" replaces "Permuter: allowed or not", with an ADR. `decomp.json` gains `template_search` and `fakematch` keys that mirror the contract.
- **`doctor`** prints both rules, and names the skill upgrade when a project's `decomp.json` lacks the keys.
- **`contract-keys`** prints the keys an upgrade writes, reading an old permuter line as the template-search line.
- **Guardrail rule 7** names template-search steering instead of permuter output.
