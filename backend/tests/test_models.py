import pytest
from pydantic import ValidationError

from app.llm import advisor_question_requests_student_list
from app.models import ActivityMatch, AdvisorChatAnswer, AdvisorChatRequest, SurveySchema


def test_survey_schema_accepts_supported_questions():
    schema = SurveySchema.model_validate({"questions": [{"id": "goal_update", "type": "single", "label": "目标是否变化？", "options": [{"value": "yes", "label": "是"}, {"value": "no", "label": "否"}]}]})
    assert schema.questions[0].id == "goal_update"


def test_survey_schema_rejects_unsafe_question_id():
    with pytest.raises(ValidationError):
        SurveySchema.model_validate({"questions": [{"id": "../../x", "type": "short_text", "label": "x"}]})


def test_match_score_range_is_enforced():
    with pytest.raises(ValidationError):
        ActivityMatch.model_validate({"include": True, "fit_score": 101, "interest_score": 50, "need_score": 50, "availability_score": 50, "reasons": [], "evidence_refs": []})


def test_advisor_chat_limits_history_and_question_length():
    request = AdvisorChatRequest.model_validate({"question": "哪些学生关注保研？", "history": [{"role": "user", "content": "先看大二"}]})
    assert request.history[0].role == "user"
    with pytest.raises(ValidationError):
        AdvisorChatRequest.model_validate({"question": "x" * 2001})


def test_advisor_chat_does_not_cap_matching_students():
    answer = AdvisorChatAnswer.model_validate({
        "answer": "共有多名学生匹配。",
        "student_refs": [
            {"student_ref": f"student-{index}", "reason": "画像证据匹配", "evidence_refs": []}
            for index in range(250)
        ],
        "follow_up_suggestions": [],
        "limitations": [],
    })
    assert len(answer.student_refs) == 250


@pytest.mark.parametrize("question", ["哪些学生关注保研？", "列出所有匹配学生", "这个活动谁适合参加？"])
def test_advisor_chat_detects_student_list_questions(question):
    assert advisor_question_requests_student_list(question)
