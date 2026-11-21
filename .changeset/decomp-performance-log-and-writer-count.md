---
"bg-skills": patch
---

Decomp skills (in progress): the performance log, the summary's cap and the writer count say what is so (spec #242).

- **Skipped probes.** A probe's `skipped` calibration record is written once per ticket and reason. A skip for another reason, and every record with another outcome, is still written.
- **Rounded numbers.** Every number of a block record is rounded where it is written: milliseconds to 2 places, seconds and shares to 3. The median compile time no longer shows the mean of two rounded values.
- **The cap.** The summary's cap counts the whole printed line, the `background` report, `repeat` and `continues_s` included. The `background` report is never dropped or cut. The summary of a collected natural match follows the same rule.
- **Hung compiles.** A block that killed a compile raises no `slow-compile`. It is passed over in that flag's streak, and its rate is left out of the medians later blocks are compared with. The other flags are unchanged.
- **Writer count.** A search counts the active writers again at its first heartbeat. A higher count becomes its starting count: the block's worker count is cut to the cores divided by the writers when above that, the tuner's floor follows, and the summary's `workers` and `writers_active` and the block record's `writers_active` report it. A set `workers` corrects only `writers_active`.
- **Layout document.** The rows on the calibration records, the block record, the summary's cap, `slow-compile`, `workers` and `writers_active` state these.
