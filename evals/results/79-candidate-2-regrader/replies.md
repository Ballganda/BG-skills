# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> Understood: add an exported `titleCase(s)` to `utils.js`, make `slugify` collapse repeated dashes, and edit only without running anything.
> 
> Both changes are in `utils.js`, but nothing has been run or tested yet.
> 
> - `slugify` now runs `.replace(/-+/g, "-")` after turning whitespace into dashes (`utils.js:2`).
> - So `"a -- b"` now becomes `"a-b"` instead of `"a---b"`.
> - `titleCase` is new and capitalises any letter that starts a word (`utils.js:5-7`).
> - It doesn't change the rest of each word, so `"hELLO"` becomes `"HELLO"`.
> - It treats apostrophes as word breaks, so `"don't"` becomes `"Don'T"`.
> - It treats hyphens as word breaks too, so `"well-known"` becomes `"Well-Known"`.
> - `slugify` still keeps dashes at the start or end, so `"-a-"` stays `"-a-"`.
> - The module now exports both functions: `{ slugify, titleCase }`.
> 
> 1. Should I change `titleCase` so `"don't"` comes out as `"Don't"`, by splitting words only on spaces? I recommend yes.
> 2. Should I make `slugify` remove dashes at the start and end? I recommend yes, because it's usually what you want from a slug.
> 3. Should I add tests for both functions? I recommend yes, and I wouldn't run them unless you ask.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 2

Reply:

> Understood: add an exported `titleCase(s)` and make `slugify` collapse repeated dashes, edit only, run nothing.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so `"a -- b"` becomes `"a-b"` (`utils.js:2`).
> - `titleCase` uppercases the first letter of each word and leaves the rest unchanged (`utils.js:5-7`).
> - `titleCase` is now exported next to `slugify` (`utils.js:9`).
> - `titleCase` counts an apostrophe as a word break, so `"don't"` becomes `"Don'T"`.
> - `titleCase` also leaves letters after the first as they are, so `"hELLO"` stays `"HELLO"`.
> - `slugify` still keeps dashes at the start or end, so `"-a-"` stays `"-a-"`.
> - There are no tests for either function in the repo.
> 
> 1. Change `titleCase` so it only breaks words on whitespace, which fixes the apostrophe case? Recommended: yes.
> 2. Make `slugify` also remove dashes at the start and end? Recommended: yes.
> 3. Add unit tests for both functions? Recommended: yes, though you'd run them yourself.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 3

Reply:

> Understood: add and export `titleCase(s)`, make `slugify` collapse repeated dashes, and edit `utils.js` without running anything.
> 
> Both changes are in `utils.js`, but I haven't run or tested them.
> 
> - `titleCase` is defined at `utils.js:5` and exported next to `slugify`.
> - It capitalises the first character after the start of the string or after any whitespace.
> - That stops apostrophes from starting a new word, so "don't" becomes "Don't" rather than "Don'T".
> - It doesn't change the rest of each word, so "hELLO" becomes "HELLO".
> - `slugify` now also turns runs of dashes into one, so "a - - b" becomes "a-b".
> - `slugify` still keeps dashes at the start or end, so "-foo-" stays "-foo-".
> - I didn't find or add any tests.
> 
> 1. Should I make `slugify` remove leading and trailing dashes too? I recommend yes, since slugs usually don't start or end with a dash.
> 2. Should I add a few unit tests for both functions? I recommend yes, because nothing checks these changes right now.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 4

Reply:

> Understood: add an exported `titleCase(s)` and make `slugify` collapse repeated dashes, editing `utils.js` only and running nothing.
> I've edited `utils.js` with both changes, but none of it has been run or tested.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so `"a -- b"` becomes `"a-b"`.
> - `titleCase` capitalises the first non-space character after the start of the string or after any whitespace.
> - It counts only whitespace as a word break, so `"don't"` becomes `"Don't"`, not `"Don'T"`.
> - Letters after the first one are left as they are, so `"hELLO"` becomes `"HELLO"`.
> - `module.exports` now exports `{ slugify, titleCase }`.
> - Nothing else in the repo uses `slugify` or `titleCase`, so no other files needed changing.
> - The repo has no tests for either function.
> 
> 1. Should I add a small test file for `slugify` and `titleCase`? I recommend yes, so the regexes get checked before anything depends on them.
> 2. Should `titleCase` lowercase the rest of each word (`"hELLO"` → `"Hello"`)? I recommend no, because that would break acronyms like `"NASA"`.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)

### with, run 5

Reply:

> Understood: add an exported `titleCase(s)` and make `slugify` collapse repeated dashes, editing only and running nothing.
> 
> I've made both edits to `utils.js`, but none of it has been run or tested.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so `"a -- b"` becomes `"a-b"`.
> - `titleCase` capitalises the first character after the start of the string or after any whitespace.
> - I split words on whitespace rather than using `\b`, so `"don't"` becomes `"Don't"` and not `"Don'T"`.
> - `titleCase` leaves the rest of each word alone, so `"hELLO"` becomes `"HELLO"`.
> - `module.exports` is now `{ slugify, titleCase }`.
> - `slugify` still keeps leading or trailing dashes from input like `"-foo-"`, because that wasn't asked for.
> 
> 1. Should I lowercase the rest of each word in `titleCase`, so `"hELLO"` becomes `"Hello"`? I recommend yes, since that's what most people expect from title case.
> 2. Should I make `slugify` strip leading and trailing dashes? I recommend yes.
> 3. Should I add tests for both functions? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: PASS PASS PASS (passed)
