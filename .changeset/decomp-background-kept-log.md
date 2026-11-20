---
"bg-skills": patch
---

Decomp skills (in progress): a background search that built nothing leaves its log, and does not yield to its own caller (spec #186, finding 6).

- **Kept log.** A collected background report with `tried: 0` names `log`: the search's log is kept as `.decomp/search/<ticket id>/background.log`, in place of the last kept one. A search that tried candidates keeps none.
- **What the log holds.** The search writes a line when it starts, when it is ready, when the foreground searches it waits on change, and when it ends. The collecting call adds what it saw: the search's files, its heartbeat's age, whether it was killed, and the foreground heartbeats in the pool.
- **Its own caller.** A background search no longer waits on a heartbeat left in the pool under the name of the call that started it. It still yields its slots to every other foreground block.
- **Bounded stop.** Stopping a background search waits for its process to be gone for no longer than 10 seconds, then kills its process tree once more and returns what the search had written. No host command the stop runs is waited for past that bound.
