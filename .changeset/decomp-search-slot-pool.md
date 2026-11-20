---
"bg-skills": patch
---

Decomp skills (in progress): searches on one machine share a pool of compile slots (spec #162).

- **Pool.** `.decomp/slots/` holds one slot per physical core. A worker holds a slot only while it builds, and a search divides the slots by the active writers.
- **Reclaim.** A slot whose holder stops its heartbeat for 30 seconds is taken back.
- **Wine.** On Wine hosts a block keeps one wineserver running across its builds.
