# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes, edit only, run nothing.
> 
> I made both changes in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so runs of dashes become a single dash (`utils.js:2`).
> - This also collapses dashes that were already in the input, like `"a--b"` → `"a-b"`.
> - `titleCase` uppercases the first letter after each word boundary (`utils.js:5-7`).
> - It doesn't lowercase the other letters, so `"hELLO"` becomes `"HELLO"`.
> - Apostrophes count as word boundaries, so `"don't"` becomes `"Don'T"`.
> - Hyphens count too, so `"foo-bar"` becomes `"Foo-Bar"`.
> - Both functions are exported: `module.exports = { slugify, titleCase }`.
> - There are no tests for either function.
> 
> 1. Should I make `titleCase` split on whitespace only, so `"don't"` stays `"Don't"`? I recommend yes.
> 2. Should I add a small test file for both functions? I recommend yes.

Votes:

- detail-one-fact-per-line: PASS FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: add an exported `titleCase(s)` to `utils.js` and make `slugify` collapse repeated dashes, editing only and running nothing.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so `"a - b"` becomes `a-b` instead of `a---b` (`utils.js:2`).
> - `titleCase` uppercases the first letter of each word using `/\b\w/g` (`utils.js:5`).
> - `titleCase` leaves the rest of each word as it was, so `"hELLO"` becomes `"HELLO"`.
> - Apostrophes count as word breaks, so `"don't"` becomes `"Don'T"`.
> - `slugify` still keeps dashes at the start and end, so `"-a-"` stays `-a-`.
> - Both functions are exported from `utils.js:9`.
> - I found no test files and added none.
> 
> 1. Should `titleCase` lowercase the rest of each word and treat apostrophes as part of a word? I recommend yes, so `"hELLO don't"` becomes `"Hello Don't"`.
> 2. Should `slugify` also strip dashes from the start and end? I recommend yes, since slugs usually don't have them.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes, and edit only without running anything.
> 
> Both changes are in `utils.js`, but I haven't run or tested them because you asked me not to.
> 
> - `titleCase(s)` capitalises the first character after the start of the string or after any whitespace.
> - Apostrophes don't start a new word, so "don't stop" becomes "Don't Stop".
> - `titleCase` leaves the rest of each word as it is, so "hELLO" stays "HELLO".
> - `slugify` now turns runs of dashes into one dash, so "a -- b" becomes "a-b".
> - Dashes at the start or end of a slug are kept, so "-a-" stays "-a-".
> - The exports are now `{ slugify, titleCase }`.
> - There are no tests for either function.
> 
> 1. Should I make `titleCase` lowercase the rest of each word, so "hELLO" becomes "Hello"? I recommend yes if you want real title case.
> 2. Should I make `slugify` strip dashes from the start and end too? I recommend yes, because that's what most slug functions do.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: add and export `titleCase(s)` in `utils.js`, make `slugify` collapse repeated dashes, and don't run anything.
> 
> I've edited `utils.js` and haven't run or tested anything.
> 
> - `titleCase` is added and exported next to `slugify`.
> - A "word" is any text between spaces, so `"don't stop"` becomes `"Don't Stop"`.
> - A simpler `\b\w` pattern would have turned `"don't"` into `"Don'T"`, so I didn't use it.
> - `titleCase` doesn't change the rest of each word, so `"hELLO"` becomes `"HELLO"`.
> - `slugify` now turns any run of dashes into a single dash, so `"a - b"` becomes `"a-b"`.
> - `slugify` still leaves dashes at the start or end, so `"-a-"` stays `"-a-"`.
> - `utils.js:9` exports `{ slugify, titleCase }`.
> 
> 1. Should `slugify` also trim dashes from the start and end? I recommend yes.
> 2. Should I add tests for both functions? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: add an exported `titleCase(s)` to `utils.js` and make `slugify` collapse repeated dashes, but edit only, without running anything.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so runs like `a--b` become `a-b`.
> - `titleCase` capitalises the first character after the start of the string or after any whitespace.
> - I made it split on whitespace so "don't" stays "don't" and doesn't become "Don'T".
> - It leaves the rest of each word as it is, so "hELLO" becomes "HELLO".
> - `module.exports` now exports `{ slugify, titleCase }`.
> - `slugify` still keeps leading and trailing dashes (e.g. from input like `"-a-"`), because you didn't ask me to strip them.
> 
> ```js
> function titleCase(s) {
>   return s.replace(/(^|\s)(\S)/g, (_, sp, c) => sp + c.toUpperCase());
> }
> ```
> 
> 1. Should I add unit tests for both functions? I'd recommend yes, since nothing has been run.
> 2. Should `titleCase` also lowercase the rest of each word ("hELLO" → "Hello")? I'd recommend no, to keep the current behaviour.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)
