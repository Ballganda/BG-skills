---
"bg-skills": patch
---

Decomp skills (in progress): `search` keeps searching between rounds (spec #162).

- **Background search.** When a block ends on a plateau or at its deadline with time left under the ceiling, `search` returns its summary, with `continues_s`, and leaves a detached process searching the same template on. It inherits no standard handle, so the call returns at once.
- **Reported on the next call.** The next `search` for the ticket stops it and reports it under `background`. When it found a natural match, the call returns that match and drops the new template, with no new attempt.
- **Stopping.** `search <id> --stop` and `release` end it with every process it started (its Job Object on Windows, its process tree elsewhere). Its liveness is a heartbeat file.
- **Yielding.** A background search starts no build while a foreground block is running on this machine, so the block has its compile slots back within one compile.
- **Override.** `"background": 0` under `"search"` in `.decomp/local.json` turns it off.
