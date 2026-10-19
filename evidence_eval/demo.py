"""Replay hand-authored response variants; never calls a model or network."""
import argparse
import json
from pathlib import Path

from .probe import prepare_request, validate_response
from .grade import grade_response


def replay(root: Path) -> dict:
    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    request = prepare_request(read("cases.json"))
    rows = []
    for name, label in [("response-correct.json", "pass"),
                        ("response-semantic-error.json", "fail"),
                        ("response-invalid-quote.json", "fail")]:
        response = read(name)
        boundary = validate_response(request, response)
        grade = grade_response(request, response, read("gold.json"))
        rows.append({"response": name, "response_origin": "hand-authored fixture",
                     "boundary_passed": boundary["passed"], "reference_fields_passed": grade["passed"],
                     "authored_semantic_label": label, "automatic_semantic_verification": False})
    return {"dataset_kind": "synthetic", "model_called": False,
            "visible_document_ids": [d["id"] for c in request["cases"] for d in c["documents"]],
            "results": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(args.fixtures)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        if args.output.resolve().is_relative_to(args.fixtures.resolve()):
            parser.error("output must not overwrite the fixture directory")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
