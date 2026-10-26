import pytest
from pydantic import ValidationError

from app.models import ActivityMatch, SurveySchema


def test_survey_schema_accepts_supported_questions():
    schema = SurveySchema.model_validate({"questions": [{"id": "goal_update", "type": "single", "label": "目标是否变化？", "options": [{"value": "yes", "label": "是"}, {"value": "no", "label": "否"}]}]})
    assert schema.questions[0].id == "goal_update"


def test_survey_schema_rejects_unsafe_question_id():
    with pytest.raises(ValidationError):
        SurveySchema.model_validate({"questions": [{"id": "../../x", "type": "short_text", "label": "x"}]})


def test_match_score_range_is_enforced():
    with pytest.raises(ValidationError):
        ActivityMatch.model_validate({"include": True, "fit_score": 101, "interest_score": 50, "need_score": 50, "availability_score": 50, "reasons": [], "evidence_refs": []})
