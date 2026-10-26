from app.llm import scrub_pii


def test_scrub_pii_removes_direct_identifiers():
    value = {
        "name": "张三",
        "note": "请联系 test@example.com 或 13800138000，学号 202612345678",
        "nested": ["another@example.org"],
    }
    result = scrub_pii(value)
    assert "name" not in result
    rendered = str(result)
    assert "test@example.com" not in rendered
    assert "13800138000" not in rendered
    assert "202612345678" not in rendered


def test_scrub_preserves_non_identifying_evidence():
    result = scrub_pii({"interest_topics": ["保研与科研"], "goal_clarity": 4})
    assert result["interest_topics"] == ["保研与科研"]
    assert result["goal_clarity"] == 4
