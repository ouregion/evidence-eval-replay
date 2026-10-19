"""Offline request/response boundary for temporary research-model probes.

This module prepares visible synthetic material and validates a model response.
It neither calls a model nor reads application configuration or databases.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError, field_validator, model_validator


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _strict_json_loads(value: str) -> Any:
    def reject_constant(token: str):
        raise ValueError(f"invalid JSON constant: {token}")
    def reject_duplicate_keys(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = item
        return result
    return json.loads(value, parse_constant=reject_constant, object_pairs_hook=reject_duplicate_keys)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProbeEntity(_Strict):
    id: str
    name: str

    @field_validator("id", "name")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must be nonempty")
        return value


class ProbeDocument(_Strict):
    id: str
    source: str
    quality: Literal["primary", "secondary", "unverified"]
    published_at: datetime | None = None
    received_at: datetime
    text: str

    @field_validator("id", "source", "text")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must be nonempty")
        return value

    @field_validator("published_at", "received_at")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)


class ProbeCase(_Strict):
    id: str
    hypothesis: str
    entities: list[ProbeEntity]
    documents: list[ProbeDocument]

    @field_validator("id", "hypothesis")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must be nonempty")
        return value

    @model_validator(mode="after")
    def unique_local_ids(self):
        for name, rows in (("entity", self.entities), ("document", self.documents)):
            values = [row.id for row in rows]
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {name} ids in case")
        return self


class ProbeSuite(_Strict):
    suite_id: str
    as_of: datetime
    cases: list[ProbeCase]

    @field_validator("suite_id")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("suite_id must be nonempty")
        return value

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def unique_suite_ids(self):
        if not self.cases:
            raise ValueError("cases must be nonempty")
        case_ids = [case.id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("duplicate case ids")
        return self


class ProbeFact(_Strict):
    document_id: str
    quote: str
    statement: str
    entity_ids: list[str]
    stance: Literal["support", "oppose", "context", "unverified"]

    @field_validator("document_id", "quote", "statement")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("fact text must be nonempty")
        return value

    @field_validator("entity_ids")
    @classmethod
    def unique_entities(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("entity_ids must be unique nonempty identifiers")
        return value


class ProbeRelationship(_Strict):
    from_entity_id: str
    to_entity_id: str
    kind: str
    document_ids: list[str]
    explanation: str

    @field_validator("from_entity_id", "to_entity_id", "kind", "explanation")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("relationship text must be nonempty")
        return value

    @field_validator("document_ids")
    @classmethod
    def documents_present(cls, value: list[str]) -> list[str]:
        if not value or any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("document_ids must be nonempty and unique")
        return value


class ProbeResult(_Strict):
    case_id: str
    state: Literal["supported", "challenged", "contested", "insufficient_evidence"]
    independent_source_count: StrictInt
    facts: list[ProbeFact]
    relationships: list[ProbeRelationship]
    reasoning: str
    unknowns: list[str]

    @field_validator("case_id", "reasoning")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("result text must be nonempty")
        return value

    @field_validator("independent_source_count")
    @classmethod
    def nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("independent_source_count must be nonnegative")
        return value

    @field_validator("unknowns")
    @classmethod
    def nonblank_unknowns(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("unknowns cannot contain blank text")
        return value


class ProbeResponse(_Strict):
    results: list[ProbeResult]


def prepare_request(raw: dict) -> dict:
    """Validate a suite and return only material visible at its declared as_of."""
    suite = ProbeSuite.model_validate(raw)
    cases = []
    for case in suite.cases:
        documents = [
            document for document in case.documents
            if document.received_at <= suite.as_of
            and (document.published_at is None or document.published_at <= suite.as_of)
        ]
        cases.append({
            "id": case.id,
            "hypothesis": case.hypothesis,
            "entities": [entity.model_dump(mode="json") for entity in case.entities],
            "documents": [document.model_dump(mode="json") for document in documents],
        })
    return {"suite_id": suite.suite_id, "as_of": _iso(suite.as_of), "cases": cases}


def response_schema() -> dict:
    """Return the strict JSON schema expected from the temporary model call."""
    return ProbeResponse.model_json_schema()


def _failure(kind: str, message: str, **extra: object) -> dict:
    return {"kind": kind, "message": message, **extra}


def _validation_errors(error: ValidationError) -> list[dict]:
    """Pydantic error contexts can contain exceptions, so make them JSON-safe."""
    return json.loads(error.json(include_input=False))


def validate_response(request: dict, raw: str | dict) -> dict:
    """Validate boundary and grounding only; semantic correctness remains manual."""
    checks: list[dict] = []
    failures: list[dict] = []
    try:
        prepared = ProbeSuite.model_validate(request)
    except ValidationError as exc:
        return {"passed": False, "checks": checks, "failures": [_failure("invalid_request", "request does not match the probe contract", errors=_validation_errors(exc))], "semantic_verification": False}
    # A request file is already filtered. Re-run preparation to reject accidental
    # future content if a caller supplied the original suite instead.
    request = prepare_request(prepared.model_dump(mode="json"))
    try:
        decoded = _strict_json_loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"passed": False, "checks": checks, "failures": [_failure("invalid_json", str(exc))], "semantic_verification": False}
    try:
        response = ProbeResponse.model_validate(decoded)
        checks.append({"name": "response_schema", "passed": True})
    except ValidationError as exc:
        return {"passed": False, "checks": checks, "failures": [_failure("invalid_response_schema", "response must be strict JSON matching response-schema.json", errors=_validation_errors(exc))], "semantic_verification": False}

    cases = {case["id"]: case for case in request["cases"]}
    result_ids = [result.case_id for result in response.results]
    expected_ids = set(cases)
    if len(result_ids) != len(set(result_ids)):
        failures.append(_failure("duplicate_case_result", "each case must have exactly one result"))
    if set(result_ids) != expected_ids:
        failures.append(_failure("case_coverage", "results must contain every request case exactly once", expected=sorted(expected_ids), actual=sorted(set(result_ids))))
    checks.append({"name": "case_coverage", "passed": not any(row["kind"] in {"duplicate_case_result", "case_coverage"} for row in failures)})

    for result in response.results:
        case = cases.get(result.case_id)
        if case is None:
            continue
        documents = {document["id"]: document for document in case["documents"]}
        entities = {entity["id"] for entity in case["entities"]}
        for index, fact in enumerate(result.facts):
            if fact.document_id not in documents:
                failures.append(_failure("unknown_fact_document", "fact document_id is not visible in its case", case_id=result.case_id, fact_index=index, document_id=fact.document_id))
            elif not fact.quote or fact.quote not in documents[fact.document_id]["text"]:
                failures.append(_failure("invalid_quote", "fact quote must be a nonempty exact substring of its visible document", case_id=result.case_id, fact_index=index, document_id=fact.document_id))
            if not set(fact.entity_ids) <= entities:
                failures.append(_failure("unknown_fact_entity", "fact entity_ids must resolve in its case", case_id=result.case_id, fact_index=index))
        for index, relationship in enumerate(result.relationships):
            if relationship.from_entity_id not in entities or relationship.to_entity_id not in entities:
                failures.append(_failure("unknown_relationship_entity", "relationship entity ids must resolve in its case", case_id=result.case_id, relationship_index=index))
            if not set(relationship.document_ids) <= set(documents):
                failures.append(_failure("unknown_relationship_document", "relationship document ids must be visible in its case", case_id=result.case_id, relationship_index=index))
    checks.append({"name": "grounded_references", "passed": not any(row["kind"] in {"unknown_fact_document", "invalid_quote", "unknown_fact_entity", "unknown_relationship_entity", "unknown_relationship_document"} for row in failures)})
    return {"passed": not failures, "checks": checks, "failures": failures, "semantic_verification": False}


def _read_json(path: Path) -> dict:
    value = _strict_json_loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _ensure_outputs_are_not_inputs(output: Path, inputs: set[Path], names: tuple[str, ...]) -> None:
    targets = {output / name for name in names}
    if targets & inputs:
        raise ValueError("output paths must not overwrite input files")


def _prepare_cli(args) -> int:
    source, output = Path(args.cases).resolve(), Path(args.output).resolve()
    _ensure_outputs_are_not_inputs(output, {source}, ("request.json", "response-schema.json"))
    prepared = prepare_request(_read_json(source))
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "request.json", prepared)
    _write_json(output / "response-schema.json", response_schema())
    return 0


def _validate_cli(args) -> int:
    request_path, response_path, output = Path(args.request).resolve(), Path(args.response).resolve(), Path(args.output).resolve()
    _ensure_outputs_are_not_inputs(output, {request_path, response_path}, ("validation.json",))
    result = validate_response(_read_json(request_path), response_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "validation.json", result)
    return 0 if result["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline temporary research LLM probe boundary")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--cases", required=True)
    prepare.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--request", required=True)
    validate.add_argument("--response", required=True)
    validate.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        return _prepare_cli(args) if args.command == "prepare" else _validate_cli(args)
    except (OSError, ValueError, ValidationError) as exc:
        parser.exit(2, f"llm-probe: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
