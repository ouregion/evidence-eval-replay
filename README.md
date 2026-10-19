# Evidence Evaluation Replay

An offline evaluation slice that separates response structure, quotation matching, reference-field checks, and semantic review. It uses one fictional case and three hand-authored response variants. No model, API key, news feed, database, or network connection is required at runtime.

## Run

From this directory, with Python 3.12 and the declared dependencies available:

```sh
python -m pip install -e '.[test]'
python -m evidence_eval.demo
python -m pytest -q
```

Dependency installation is a setup step; this preparation used already installed Pydantic 2.11.7 and pytest 8.4.2 without downloading dependencies. The package declares Python >=3.11; only Python 3.12.4 was tested here.

The demo also accepts `--fixtures fixtures --output demo-output/results.json`. `config.example.json` documents the fixture paths and expected output location; the demo uses CLI arguments, not automatic configuration loading.

## What the demo proves

| Hand-authored response | Boundary | Reference fields | Authored semantic label |
|---|---|---|---|
| Faithfully reports an unsigned contract | Pass | Pass | Pass |
| Quotes the negative sentence but claims a contract is signed | Pass | Pass | Fail |
| Fabricates an affirmative quotation | Fail | Fail | Fail |

The future document is removed before checking the responses. The middle row deliberately exposes a scoring gap: the existing field grader does not check the meaning of the fact statement. Semantic labels are fixture-author expectations, not automated semantic validation or independent blind review.

The retained CLIs can prepare a request or validate an existing response:

```sh
python -m evidence_eval.probe prepare --cases fixtures/cases.json --output demo-output/request
python -m evidence_eval.probe validate --request demo-output/request/request.json \
  --response fixtures/response-correct.json --output demo-output/validation
```

## Validation and remaining work

**8 tests passed** in this standalone slice on 2026-10-18: the seven extracted probe/field-grading tests and one demo acceptance test. The demo was executed separately. The test suite includes future-material filtering, strict JSON/type checks, broken references, incorrect quotations, and the intentionally undetected semantic contradiction.

This is not a comparison of named models. There is no live-model adapter, representative holdout set, automatic semantic oracle, production accuracy estimate, or CI execution result. A clean dependency installation and Python 3.11 remain untested. Expanding beyond this small synthetic case requires a versioned rubric and separately authorized model runs.

See [UPSTREAM.md](UPSTREAM.md) and [LICENSE.upstream](LICENSE.upstream) for required attribution. The owner's code and additions are licensed under [MIT](LICENSE); the retained upstream MIT notice continues to apply to its respective material. No Git history or historical model/news outputs are included.
