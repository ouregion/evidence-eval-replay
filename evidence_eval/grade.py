"""Compare explicit smoke-test fields; this is not a semantic or trading grader."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .probe import validate_response, _read_json


def grade_response(request: dict, response: dict, gold: dict) -> dict:
    boundary = validate_response(request, response)
    if not boundary["passed"]:
        return {"passed": False, "boundary": boundary, "cases": [],
                "checks": 0, "failures": ["response_boundary_failed"],
                "semantic_verification": False, "trading_effectiveness_evaluated": False}
    if gold["suite_id"] != request["suite_id"]:
        raise ValueError("gold suite must match request")
    if set(gold["cases"]) != {case["id"] for case in request["cases"]}:
        raise ValueError("gold cases must exactly match request")
    cases, failures, checks = [], [], 0
    for row in response["results"]:
        expected = gold["cases"][row["case_id"]]
        checked = []

        def check(name: str, ok: bool):
            nonlocal checks
            checks += 1
            checked.append({"name": name, "passed": bool(ok)})
            if not ok:
                failures.append(f"{row['case_id']}.{name}")

        check("state", row["state"] in expected["state"])
        check("independent_source_count", row["independent_source_count"] == expected["independent_source_count"])
        citations = {fact["document_id"] for fact in row["facts"]}
        check("required_fact_documents", set(expected["required_fact_docs"]) <= citations)
        pairs = {(r["from_entity_id"], r["to_entity_id"]) for r in row["relationships"]}
        for pair in expected.get("required_relationship_pairs", []):
            check("required_relationship:" + ":".join(pair), tuple(pair) in pairs)
        for pair in expected.get("forbidden_relationship_pairs", []):
            check("forbidden_relationship:" + ":".join(pair), tuple(pair) not in pairs)
        text = json.dumps(row, ensure_ascii=False)
        for value in expected.get("forbidden_output", []):
            check("forbidden_output:" + value, value not in text)
        cases.append({"case_id": row["case_id"], "passed": all(c["passed"] for c in checked),
                      "checks": checked, "reference_note": expected["note"]})
    return {"passed": not failures, "boundary": boundary, "cases": cases,
            "checks": checks, "failures": failures,
            "semantic_verification": False, "trading_effectiveness_evaluated": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "response", "gold", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    sources = [Path(getattr(args, name)).resolve() for name in ("request", "response", "gold")]
    if output in sources:
        parser.error("output must not overwrite inputs")
    try:
        request, response, gold = [_read_json(p) for p in sources]
        result = grade_response(request, response, gold)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "checks", "failures")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
