---
type: llm
focus: trace
---

This is the session transcript, one JSON message per line. Skill text loaded through the Skill tool explains how to handle glossary clashes; ignore it and judge only what the assistant itself said to the user, in any of its messages, not only the last.

The workspace GLOSSARY.md defines **Cancellation** as withdrawing an entire Order before Dispatch. The user's prompt used "cancel an item" for returning one delivered line item for a refund, which clashes with that definition.

PASS if the assistant's own text explicitly points out that the user's use of "cancel" or "cancellation" conflicts with the glossary's existing definition (whole Order, before Dispatch), and keeps the two concepts apart (for example by naming the new concept with a different term such as Return).

FAIL if the assistant never mentions the conflict with the glossary, or silently treats the new concept as a kind of Cancellation.
