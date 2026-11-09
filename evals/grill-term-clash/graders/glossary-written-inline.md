---
type: llm
focus: {source: file, path: GLOSSARY.md}
---

This is GLOSSARY.md after the session. Before the session it held exactly four terms: Order, Line Item, Dispatch, Cancellation (whole Order, before Dispatch).

PASS only if all of these hold:
- It now has a new bolded term entry for the concept of a customer sending back one delivered Line Item for a refund of that item (for example **Return**), with a one or two sentence definition.
- The Cancellation entry still means withdrawing an entire Order before Dispatch; it has not been redefined to cover the new concept.
- The file contains no implementation details (no code, endpoints, database tables or task lists).

FAIL otherwise, including when the file is unchanged.
