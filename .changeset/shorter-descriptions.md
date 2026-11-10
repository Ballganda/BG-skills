---
"bg-skills": patch
---

Shorter skill descriptions, enforced by `check-skills`.

- **Limits**: a user-invoked skill's description is at most 20 words, a model-invoked one's at most 40. `scripts/check-skills.mjs` fails on any skill over its limit, in every bucket.
- **Trimmed**: twelve descriptions shortened. Model-invoked ones still say when to use them.
