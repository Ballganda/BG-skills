---
"bg-skills": patch
---

Decomp skills (in progress): the guardrail scan follows every include.

- **Include chain**: the scan covers each project file a source includes, directly or through another header, beside the source or under `include/`, in whatever letter case the name is written. Before, only headers named directly under `include/` were scanned.
- **Hidden includes refused**: an `#include` whose file a macro names, an absolute path, and a path that climbs out of the project are guardrail violations.
- **`revalidate --header`** rebuilds every ticket that reaches the header through any chain of includes.
