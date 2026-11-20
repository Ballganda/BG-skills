---
"bg-skills": patch
---

Decomp skills (in progress): template search reads a missing object identity as unknown (spec #186, finding 3).

- **Counts.** When the compiler's objects differ between two compiles and the diff adapter prints no `function_sha256`, the summary's `unique_objects` and `object_hits` and the performance record's `unique_objects` are `null`, not zero.
- **Notice.** That summary carries one `no-object-identity` line: object dedupe and the inert freeze are off, and the fix is a diff adapter that prints `function_sha256`, through `/decomp-setup`'s upgrade.
- **Layout document.** It says when the two counts are `null`, and that the plateau rule then rests on the best score alone.
