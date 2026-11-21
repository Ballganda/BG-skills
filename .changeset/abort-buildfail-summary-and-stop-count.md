---
"bg-skills": patch
---

A decomp round that ends `abort-buildfail` now gives the compiler's message in `failure` and names the choice points whose alternatives failed to build in `build_failed`, also when the baseline scored. Stop advice counts the flat template rounds since the ticket's last new best score and passes over `check` records between them, and a round that matches carries none.
