#!/usr/bin/env python3
"""Tests of the decomp test runner at its one seam: the command line.

Each case writes a small scratch test module that hands its own names and file
to the runner in scripts/test-decomp.py, runs it as a child process, and asserts
on the exit code and the printed lines. No network. Standard library only.

Run: python scripts/test-decomp-runner.py [name-filter]
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "scripts" / "test-decomp.py"
NO_MATCH, COLLISION = 2, 3

HEAD = f'''import importlib.util, sys
spec = importlib.util.spec_from_file_location("runner", {str(RUNNER)!r})
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
'''
TAIL = '''

if __name__ == "__main__":
    runner.main(sys.argv[1:], globals(), __file__)
'''
CASES = '''
def test_search_picks_one(base):
    pass


def test_search_picks_one_more(base):
    pass


def test_research_picks(base):
    pass


def test_verify_fails(base):
    raise AssertionError("boom")
'''


def expect(cond, what, r=None):
    if not cond:
        detail = f"\n  exit={r.returncode}\n  stdout={r.stdout!r}\n  stderr={r.stderr!r}" if r is not None else ""
        raise AssertionError(what + detail)


def module(base, body=CASES):
    path = Path(base) / "scratch_tests.py"
    path.write_text(HEAD + body + TAIL, encoding="utf-8")
    return path


def run(base, *args, body=CASES):
    return subprocess.run([sys.executable, str(module(base, body)), *args], capture_output=True, text=True)


def listed(r):
    return r.stdout.split()


def test_exact_name_selects_only_that_case_though_it_starts_other_names(base):
    r = run(base, "--list", "test_search_picks_one")
    expect(r.returncode == 0 and listed(r) == ["test_search_picks_one"], "an exact name should select that case alone", r)


def test_partial_filter_selects_names_holding_its_words_in_a_row(base):
    r = run(base, "--list", "picks_one")
    expect(listed(r) == ["test_search_picks_one", "test_search_picks_one_more"], "whole words in a row should match", r)
    r = run(base, "--list", "search")
    expect(listed(r) == ["test_search_picks_one", "test_search_picks_one_more"], "a word should not match inside a longer word", r)
    r = run(base, "--list", "picks_search")
    expect(r.returncode == NO_MATCH, "words out of order should not match", r)


def test_the_leading_word_may_be_in_the_filter_or_left_out(base):
    a, b = run(base, "--list", "test_search"), run(base, "--list", "search")
    expect(listed(a) == listed(b) and len(listed(a)) == 2, "the shared leading word is a word like any other", a)


def test_two_filters_select_the_union(base):
    r = run(base, "--list", "research", "verify")
    expect(listed(r) == ["test_research_picks", "test_verify_fails"], "either filter selects a case", r)


def test_a_filter_that_selects_nothing_fails_before_any_case_runs(base):
    r = run(base, "verify", "typo")
    expect(r.returncode == NO_MATCH and "'typo'" in r.stdout, "the unmatched filter should be named", r)
    expect("FAIL" not in r.stdout and "PASS" not in r.stdout, "no case should have run", r)


def test_list_mode_runs_no_case(base):
    r = run(base, "--list", "verify")
    expect(r.returncode == 0 and listed(r) == ["test_verify_fails"], "a failing case is only listed", r)


def test_a_run_prints_each_result_and_exits_1_on_a_failure(base):
    r = run(base, "research", "verify")
    expect(r.returncode == 1 and "PASS test_research_picks" in r.stdout and "FAIL test_verify_fails: boom" in r.stdout
           and "1 passed, 1 failed" in r.stdout, "results and the exit code", r)


def test_a_duplicated_function_stops_the_run_naming_both_lines(base):
    body = CASES + "\n\ndef helper():\n    return 1\n\n\ndef helper():\n    return 2\n"
    r = run(base, body=body)
    expect(r.returncode == COLLISION and "helper" in r.stdout and "PASS" not in r.stdout, "a duplicated function", r)
    lines = [i + 1 for i, l in enumerate((HEAD + body).split("\n")) if l == "def helper():"]
    expect(all(str(n) in r.stdout for n in lines), f"both lines {lines} should be named", r)
    expect(run(base, "--list", body=body).returncode == COLLISION, "the list mode checks too", r)


def test_a_duplicated_assignment_stops_the_run(base):
    r = run(base, body=CASES + "\nSCRIPT = 'a'\nSCRIPT = 'b'\n")
    expect(r.returncode == COLLISION and "SCRIPT" in r.stdout, "a duplicated assignment", r)


def test_a_clean_module_runs(base):
    r = run(base, "research")
    expect(r.returncode == 0 and "1 passed, 0 failed" in r.stdout, "no collision, no complaint", r)


def test_a_result_line_arrives_while_a_later_case_still_runs(base):
    body = "import time\n\n\ndef test_a_first(base):\n    pass\n\n\ndef test_b_slow(base):\n    time.sleep(20)\n"
    p = subprocess.Popen([sys.executable, str(module(base, body))], stdout=subprocess.PIPE, text=True)
    try:
        began = time.time()
        line = p.stdout.readline()
        expect(line.strip() == "PASS test_a_first" and time.time() - began < 15, f"the first line should arrive at once: {line!r}")
    finally:
        p.kill()
        p.wait()
        p.stdout.close()


def rmtree(path):
    def retry(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=retry)


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and want in n]
    failed = 0
    for name, f in tests:
        base = tempfile.mkdtemp(prefix="decomp-runner-test-")
        try:
            f(base)
            print(f"PASS {name}")
        except Exception as e:  # a crash in one case must not hide the others
            failed += 1
            print(f"FAIL {name}: {e if isinstance(e, AssertionError) else traceback.format_exc()}")
        finally:
            try:
                rmtree(base)
            except OSError:
                pass
    print(f"{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
