---
"bg-skills": patch
---

Decomp skills (in progress): parallel Tickets stop conflicting in the layout reference and the block call. No behaviour of the decomp tool and no fact in the reference changes.

- **The layout reference** keeps short tables for lookup and gives each command, path and record with detail its own section, where every fact is one bullet on one line. Existing anchors keep their names.
- **The skills check** fails when any line of the layout reference is over 300 characters, naming the file, the line and its length.
- **The template-search block runner** takes one options value with named fields in place of ten positional arguments, so a new option adds a field and not an edit to every call.
