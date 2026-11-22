---
"bg-skills": patch
---

Decomp skills (in progress): a background search starts no build once its time is over, and says when it waited its whole budget on the foreground (spec #238, finding 7).

- **No build after the time.** A worker looks at the search's time when its wait on the foreground ends, and again once it holds a slot. When the time is over, or the search was stopped, it gives the slot back and builds nothing: its candidate stays untried. A build in hand runs to its end.
- **The log and the report.** A search that never built because foreground searches were beating until its time ended writes `ended: deadline, waited its whole budget on the foreground: <names>, no build started`, and its report holds `waited_on_foreground: true`. Its `tried` is 0, so its log is kept as `background.log`.
