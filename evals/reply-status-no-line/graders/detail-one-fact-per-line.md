---
type: llm
focus: trace
---

This is the session transcript, one JSON message per line. Judge only what the assistant itself wrote to the user in chat, in its final message. Ignore tool calls, tool results, file contents and any skill text.

PASS only if the detail in the final message, everything after its first line, is written as bullets or numbered lists (short bold labels or headings between lists are fine), and each item is about one subject: a finding with its example, value or reason. A fix and its reason, or a finding and the trade-off it carries, are one item. Do not fail an item for having a second clause that supports the same subject.

FAIL if any part of the detail is a paragraph or narrative, if the message after its first line is prose, or if an item packs several unrelated findings into one line (for example a change to one function, a risk in another and a note about tests, joined by "and", semicolons or run-on sentences).
