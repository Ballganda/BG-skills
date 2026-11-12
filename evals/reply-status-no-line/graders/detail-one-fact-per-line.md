---
type: llm
focus: trace
---

This is the session transcript, one JSON message per line. Judge only what the assistant itself wrote to the user in chat, in its final message. Ignore tool calls, tool results, file contents and any skill text.

The outcome line is the first line of the final message, or its second line when the first line opens with "Understood:".

PASS only if every part of the final message after the outcome line that carries detail is a bullet or numbered list in which each item states one fact. Items that join several unrelated facts with "and", semicolons or sentences are not one fact per line.

FAIL if the detail is written as paragraphs or narrative, if it is missing and the message is prose, or if items bundle several facts.
