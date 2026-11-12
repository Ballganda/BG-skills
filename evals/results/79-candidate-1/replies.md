# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> Understood: you wanted `titleCase(s)` added to `utils.js` and exported, and `slugify` changed so repeated dashes become one, with only file edits and nothing run.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so dashes that were already in the input, like `"a -- b"`, now come out as `a-b`.
> - `titleCase` uses `s.replace(/\b\w/g, c => c.toUpperCase())`, which capitalises the first letter of each word and leaves the other letters as they are.
> - `module.exports` now exports `{ slugify, titleCase }`.
> - `titleCase` treats an apostrophe as a word break, so `"don't"` becomes `"Don'T"`.
> - It also capitalises after hyphens and underscores, so `"well-known"` becomes `"Well-Known"`.
> - `slugify` still keeps dashes at the start or end, so `"-a-"` stays `-a-`.
> - `titleCase` doesn't lowercase anything, so `"hELLO"` becomes `"HELLO"`.
> 
> 1. Should I make `titleCase` handle apostrophes correctly by splitting only on whitespace? I recommend it, and "yes" means I'll make that edit.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes, and edit only without running anything.
> 
> Both changes are in `utils.js`, but nothing has been run or tested.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so input like `"a - b"` or `"a--b"` gives `"a-b"`.
> - `titleCase` uppercases the first letter of each word and leaves the other letters as they are, so `"hELLO"` becomes `"HELLO"`.
> - `module.exports` now exports both `{ slugify, titleCase }`.
> - One known catch: `titleCase` treats an apostrophe as the start of a new word, so `"don't"` becomes `"Don'T"`.
> - `slugify` still keeps dashes at the start or end, so `"-a-"` stays `"-a-"`.
> 
> 1. Should I change `titleCase` to split words only on whitespace so apostrophes work, and strip dashes from the ends in `slugify`? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes into one, and run nothing.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with an extra `.replace(/-+/g, "-")`, so `"a - - b"` becomes `"a-b"` instead of `"a-----b"`.
> - `titleCase` (`utils.js:5`) capitalises any letter that starts a word and leaves the other letters as they were, so `"hELLO"` becomes `"HELLO"`.
> - One catch: `titleCase` treats an apostrophe as the end of a word, so `"don't"` comes out as `"Don'T"`.
> - `module.exports` now exports both `slugify` and `titleCase`.
> - `slugify` still keeps dashes at the very start or end, so `"-a-"` stays `"-a-"`.
> 
> 1. Should I change `titleCase` to split on whitespace so apostrophes stop causing the `"Don'T"` problem? I'd recommend it, and "yes" means I'll make that edit.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: add and export `titleCase(s)`, make `slugify` collapse repeated dashes into one, and only edit files without running anything.
> 
> I've made both changes in `utils.js`, but I haven't run or tested them because you asked me not to.
> 
> - `slugify` now runs `.replace(/-+/g, "-")` after turning whitespace into dashes, so `"a - b"` and `"a--b"` both become `"a-b"`.
> - `titleCase` capitalises the first non-space character after the start or any whitespace, and leaves the rest of each word as it is (`"hELLO world"` becomes `"HELLO World"`).
> - Both functions are exported: `module.exports = { slugify, titleCase }`.
> - `utils.js` was the only file I changed, and there are no tests for either function in the repo.
> - `slugify` still keeps dashes at the start or end of the string, such as `"-a-"`, because you didn't ask me to strip them.
> 
> 1. Do you want me to add unit tests for `slugify` and `titleCase`? I recommend yes, since nothing has been checked yet.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes, and edit only without running anything.
> 
> Both changes are in `utils.js`, but nothing has been run or tested.
> 
> - `slugify` now runs `.replace(/-+/g, "-")` after the whitespace replacement, so `"a - - b"` and `"a--b"` both become `a-b` (`utils.js:2`).
> - `titleCase` is new (`utils.js:5`); it capitalises the first letter of each word and leaves the other letters as they are, so `"hELLO world"` becomes `"HELLO World"`.
> - `module.exports` now exports both `slugify` and `titleCase`.
> - `titleCase` treats an apostrophe as the start of a new word, so `"don't stop"` becomes `"Don'T Stop"`.
> - `slugify` still leaves dashes at the start and end, so `"-hello-"` stays `-hello-`.
> - No tests or other files call `titleCase` yet.
> 
> 1. Should I change `titleCase` to split only on spaces so contractions like "don't" come out right? I recommend yes.
> 2. Should I make `slugify` remove dashes at the start and end? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)
