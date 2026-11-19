# Template search replaces the permuter line in the contract

The contract's matching section held one line, "Permuter: allowed or not". Spec #162 gives stuck functions template search instead: the writer writes one template with marked choice points, and `decomp.py search` compiles the candidates the choices expand to. The permuter line becomes "Template search: allowed or not".

- Template search covers natural alternatives. A steering alternative (written only to steer the compiler) is allowed only where the contract's fakematch rule allows it, and the winner carries a `fakematch: <why>` comment on each steering line it keeps.
- Random permutation has no contract line, because no skill or tool offers it. Every candidate is built only from alternatives the writer wrote, so there is no random mutation to govern.
- `decomp.json` gains `template_search` (true or false) and `fakematch` (`forbidden` or `allowed`), mirroring the contract, because the fakematch and permuter rules were prose the tool could not read. The tool refuses template search when it is off, and steering when fakematch is forbidden.
- Existing projects upgrade through the skill-upgrade flow: `decomp.py contract-keys` reads the old "Permuter:" line as the template-search line, and `doctor` names the upgrade when the keys are missing.

Consequences: a project that allowed the permuter allows template search, which is narrower (no random edits), so no project loses a capability it could use. Guardrail rule 7 names template-search steering instead of permuter output.
