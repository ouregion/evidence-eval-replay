from evidence_eval.grade import grade_response


def example():
    request = {"suite_id": "smoke", "as_of": "2026-09-24T16:00:00Z", "cases": [{
        "id": "case", "hypothesis": "An order exists.", "entities": [{"id": "firm", "name": "Fictional Firm"}],
        "documents": [{"id": "d", "source": "Issuer", "quality": "primary", "published_at": None,
                       "received_at": "2026-09-24T15:00:00Z", "text": "No order has been signed."}]}]}
    response = {"results": [{"case_id": "case", "state": "challenged", "independent_source_count": 1,
        "facts": [{"document_id": "d", "quote": "No order has been signed.", "statement": "No signed order.", "entity_ids": ["firm"], "stance": "oppose"}],
        "relationships": [], "reasoning": "The issuer denies a signed order.", "unknowns": ["Future negotiations."]}]}
    gold = {"suite_id": "smoke", "cases": {"case": {"state": ["challenged"], "independent_source_count": 1,
                        "required_fact_docs": ["d"], "note": "No signed order."}}}
    return request, response, gold


def test_field_checks_detect_wrong_direction_but_do_not_claim_semantic_validation():
    request, response, gold = example()
    assert grade_response(request, response, gold)["passed"] is True
    response["results"][0]["state"] = "supported"
    graded = grade_response(request, response, gold)
    assert graded["passed"] is False
    assert graded["failures"] == ["case.state"]
    assert graded["semantic_verification"] is False


def test_bad_quotes_cannot_pass_by_matching_expected_state():
    request, response, gold = example()
    response["results"][0]["facts"][0]["quote"] = "An order is signed."
    graded = grade_response(request, response, gold)
    assert graded["passed"] is False and graded["checks"] == 0
    assert graded["failures"] == ["response_boundary_failed"]
