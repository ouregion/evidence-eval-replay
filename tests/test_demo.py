from pathlib import Path

from evidence_eval.demo import replay


def test_demo_separates_semantic_review_from_field_checks():
    result = replay(Path(__file__).resolve().parents[1] / "fixtures")
    assert result["visible_document_ids"] == ["d-visible"]
    assert result["model_called"] is False
    assert [(r["boundary_passed"], r["reference_fields_passed"], r["authored_semantic_label"])
            for r in result["results"]] == [(True, True, "pass"), (True, True, "fail"), (False, False, "fail")]
    assert not any(r["automatic_semantic_verification"] for r in result["results"])
