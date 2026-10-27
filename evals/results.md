# Eval results

Six golden cases, two runs each. Version A lets the agent read the code. Version B tells it to answer from memory.

## with-code

```text
PASS RATE: 6/6 (100%)  [a case passes when every run of it passes]
PASS@K:    6/6  [a case passes when at least one run passes]
RUNS:      12/12 passed
COST:      $0.1767
```

## from-memory

```text
PASS RATE: 1/6 (17%)  [a case passes when every run of it passes]
PASS@K:    1/6  [a case passes when at least one run passes]
RUNS:      2/12 passed
COST:      $0.0666
```

## Notes

- day-30-late passed under from-memory by a lucky guess: the agent said it did not know OrderLoop's window, assumed 30 days, and answered "no". The answer is right for the wrong reason. A code grader that only matches the answer cannot see that; add a check that the agent read rules.py, or use a rubric grader.
- Five of six cases failed under from-memory because the agent refused to guess. That is the safe behaviour, and the eval caught it.

Decision: keep the with-code version. Do not add "answer from memory" to any prompt.
