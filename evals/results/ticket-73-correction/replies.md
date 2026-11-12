# Kept Replies and grader votes

## reply-correction

### with, run 1

Reply:

> Understood: `slugify` should only lowercase and trim, the dash collapsing should move into its own function, and `titleCase` should still be added.
> 
> I've edited `utils.js` that way and haven't run anything.
> 
> - `slugify(s)` now only lowercases and trims (`utils.js:1`).
> - The whitespace-to-dash replacement moved, unchanged, into a new function, `collapseDashes(s)` (`utils.js:5`).
> - `titleCase(s)` capitalises the first letter of each word (`utils.js:9`).
> - All three are exported.
> - Nothing else in the repo calls `slugify`, so no callers break.
> - Calling `slugify` alone no longer produces dashes.
> - To get the old output, call `collapseDashes(slugify(s))`.
> - `titleCase` leaves the rest of each word as it is, so `"hELLO"` becomes `"HELLO"`.
> - `titleCase` also treats an apostrophe as a word break, so `"don't"` becomes `"Don'T"`.
> 
> 1. Should `titleCase` lowercase the rest of each word and handle apostrophes? I recommend yes.
> 2. Should `collapseDashes` also merge dashes that are already in the text (`"a--b"` → `"a-b"`)? I recommend yes, since that's what the name suggests.

Votes:

- understood-own-words: PASS PASS PASS (passed)
