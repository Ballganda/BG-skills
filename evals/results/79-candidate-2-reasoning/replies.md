# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> Understood: you want `titleCase(s)` added and exported from `utils.js`, `slugify` changed to collapse repeated dashes, and nothing run.
> 
> Both edits are in `utils.js`, but nothing has been run or tested.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so `"a - b"` becomes `"a-b"` instead of `"a---b"`.
> - `slugify` still keeps dashes at the start or end, so `"-a-"` stays `"-a-"`.
> - `titleCase` capitalises the first letter after each word boundary.
> - `titleCase` leaves the other letters as they are, so `"hELLO"` becomes `"HELLO"`.
> - `titleCase` also capitalises after apostrophes, so `"don't"` becomes `"Don'T"`.
> - `module.exports` now exports `{ slugify, titleCase }`.
> 
> 1. Should `titleCase` treat only spaces as word breaks, so `"don't"` becomes `"Don't"`? I recommend yes.
> 2. Should I add unit tests for both functions without running them? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL PASS PASS (passed)
- outcome-first: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: add an exported `titleCase(s)` to `utils.js`, make `slugify` collapse repeated dashes, and edit the file without running anything.
> 
> I've edited `utils.js` with both changes, but I haven't run or tested anything, as you asked.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so runs of dashes become one dash.
> - That includes dashes already in the input, so `"a--b"` becomes `"a-b"`.
> - `titleCase` capitalises the first letter after the start of the string or after any whitespace.
> - It leaves all other letters as they are, so `"hELLO"` becomes `"HELLO"`.
> - `module.exports` now exports `{ slugify, titleCase }`.
> - I found no test files in the repo, so no tests cover either function.
> 
> Possible next steps:
> 
> 1. Make `titleCase` lowercase the rest of each word too (`"hELLO"` → `"Hello"`). I recommend this only if you want strict title case.
> 2. Add unit tests for both functions. I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: add an exported `titleCase(s)` to `utils.js` and make `slugify` collapse repeated dashes, editing only and running nothing.
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so runs of dashes become one dash (`utils.js:2`).
> - This covers dashes that were already in the input, like `"a -- b"` → `"a-b"`.
> - `titleCase` capitalises the first non-space character after the start of the string or after any whitespace (`utils.js:5-7`).
> - It leaves the rest of each word as it is, so `"hELLO world"` → `"HELLO World"`.
> - It doesn't use `\b\w`, which would wrongly turn `"don't"` into `"Don'T"`.
> - `module.exports` now exports both `slugify` and `titleCase` (`utils.js:9`).
> - I didn't find any tests for `utils.js`, and I didn't add any.
> 
> 1. Should I add tests for both functions? I recommend yes.
> 2. Should `titleCase` also lowercase the rest of each word, so `"hELLO"` → `"Hello"`? I recommend no, because it would break acronyms like `"NASA"`.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: add and export `titleCase(s)`, make `slugify` collapse repeated dashes, edit only and run nothing.
> 
> I made both changes in `utils.js`, but they're untested because I ran nothing.
> 
> - `titleCase` capitalises the first character after each run of whitespace (`utils.js:5`).
> - I chose whitespace as the word boundary on purpose, so "don't" becomes "Don't" and not "Don'T".
> - `titleCase` leaves the other letters as they are, so "hELLO" becomes "HELLO".
> - `slugify` now turns any run of dashes into a single dash, including dashes that were already in the input (`utils.js:2`).
> - `module.exports` now exports both `slugify` and `titleCase`.
> - I haven't looked for tests or callers that rely on the old `slugify` output.
> 
> 1. Should `titleCase` lowercase the rest of each word, so "hELLO" becomes "Hello"? I recommend no and keeping it as it is, so acronyms like "NASA" stay intact.
> 2. Should I add tests for both functions? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes into one, and run nothing.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `titleCase` uppercases the first character after the start of the string or after any whitespace.
> - I split words on whitespace so "don't" becomes "Don't", not "Don'T".
> - `titleCase` doesn't lowercase the rest of a word, so "hELLO" becomes "HELLO".
> - `slugify` now turns any run of dashes into a single dash, including dashes that were already in the input.
> - `slugify` still keeps dashes at the start or end, so "-a-" stays "-a-".
> - `titleCase` is now exported next to `slugify` in `module.exports`.
> 
> 1. Should I add unit tests for both functions? I recommend yes, because nothing has checked the new behaviour yet.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)
