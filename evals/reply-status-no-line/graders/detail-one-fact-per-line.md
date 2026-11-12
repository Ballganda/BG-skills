---
type: llm
focus: trace
---

This is the session transcript, one JSON message per line. Judge only what the assistant itself wrote to the user in chat, in its final message. Ignore tool calls, tool results, file contents and any skill text.

The outcome line is the first line of the final message, or its second line when the first line opens with "Understood:".

PASS only if every part of the final message after the outcome line that carries detail is a bullet or numbered list in which each item states one fact. A fact together with its direct consequence or example ("X, so Y", "X, like Y") is one fact. Items that join two independent facts with "and", semicolons or sentences are not one fact per line, and neither is a numbered item that holds two offers of further work.

FAIL if the detail is written as paragraphs or narrative, if it is missing and the message is prose, or if items bundle independent facts or offers.

How to judge: first find the final message and its outcome line. Then take each bullet and numbered item after it in turn and decide, against the criterion above, whether it is one fact (or one offer). Only when every item has been checked, give the overall verdict: PASS when every item is one fact or one offer, FAIL when any item is not.
