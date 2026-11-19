---
"bg-skills": patch
---

Decomp skills (in progress): `search` reads natural and steering alternatives under the contract's fakematch rule (spec #162).

- **Steering tag.** An alternative led by `/* steer: <why> */` is steering. Every other alternative is natural.
- **Refusal.** A template holding a steering alternative is refused, with nothing built, when `fakematch` is `forbidden`.
- **Natural first.** A natural match ends the round. A match that needs steering keeps the round going for a natural one, then drops each steering choice it does not need.
- **Winner.** Each surviving steering line carries a `fakematch: <why>` comment.
