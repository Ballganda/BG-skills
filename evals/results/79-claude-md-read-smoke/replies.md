# Kept Replies and grader votes

## reply-status

### with, run 1

Reply:

> Understood: add and export `titleCase`, make `slugify` collapse repeated dashes, run nothing, then report status and the codeword.
> I edited `utils.js` as asked, but none of it has been run or tested.
> 
> - `slugify` now ends with `.replace(/-+/g, "-")`, so runs of dashes become one dash.
> - That includes dashes that were already in the input, such as `"a--b"` becoming `"a-b"`.
> - `titleCase(s)` capitalises the first letter of each word using `/\b\w/g`.
> - It leaves the other letters alone, so `"hELLO"` becomes `"HELLO"`.
> - It also capitalises the letter after an apostrophe, so `"don't"` becomes `"Don'T"`.
> - Both functions are exported through `module.exports`.
> - The project codeword is **ULUZNOREH**.
> 
> 1. Should I lowercase the rest of each word in `titleCase` and stop it capitalising after apostrophes? I recommend yes.

Votes:

- detail-one-fact-per-line: FAIL FAIL FAIL (failed)
- outcome-first: FAIL FAIL FAIL (failed)
