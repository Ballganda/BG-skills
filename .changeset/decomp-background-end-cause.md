---
"bg-skills": patch
---

Decomp skills (in progress): a collected background search says why it ended, so the next one that builds nothing explains itself (spec #206, after finding 6 of spec #186).

- **End reasons.** A collected report's `end` now tells three cases apart. `stopped`: the collecting call cut the search short while it was working. `error`: it died, and the report's `error` holds the error's text, or says that the process was gone and left no report. `killed`: it would not go within the 10-second stop bound, or it was still alive after its budget plus that bound, and the report then holds `overrun`.
- **Seconds against budget.** The report and the kept log's `collected:` line hold `ran_s`, the seconds from the search's start to its collection, and `budget_s`.
- **Traceback.** A background search that dies of an error writes a `died of an error:` line to its log, followed by the traceback of an error nothing caught.
- **Heartbeat removal.** A call that cannot remove its own heartbeat as it leaves the slot pool still does not fail, but keeps a line with the heartbeat's name and the error. The background search it then starts copies that line into its log at its start.
- **Call time.** The summary's counts and the performance record gain `collect_s`: the seconds the call spent collecting the ticket's background search. It sits beside `call_s` and is part of it.
- **Closing rule for the finding.** The finding is confirmed when one kept log (`.decomp/search/<ticket id>/background.log`, named by the report's `log`) names a cause. It is closed as not reproduced after 30 collected background searches on the real project with none reporting `tried: 0`. The result is reported on spec #206.
