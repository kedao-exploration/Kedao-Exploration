from app.llm import ADVISOR_LIST_BATCH_SIZE, LLMService
from app.models import AdvisorChatAnswer


def test_list_questions_merge_every_batch_without_person_cap():
    service = object.__new__(LLMService)
    calls = []

    def fake_complete(schema, system, payload, schema_name):
        students = payload["attached_file"]["content"]["students"]
        calls.append(students)
        return AdvisorChatAnswer(
            answer="本批匹配完成。",
            student_refs=[
                {"student_ref": row["student_ref"], "reason": "画像证据匹配", "evidence_refs": []}
                for row in students
            ],
            follow_up_suggestions=[],
            limitations=[],
        )

    service._complete = fake_complete
    total = ADVISOR_LIST_BATCH_SIZE * 3 + 5
    attachment = {
        "attachment_type": "advisor_student_context",
        "students": [{"student_ref": f"student-{index}", "profile": {"summary": "匹配"}} for index in range(total)],
    }
    result = service.answer_advisor_chat(attachment, "列出所有匹配学生", [], list_requested=True)

    assert len(calls) == 4
    assert len(result.student_refs) == total
    assert "未按人数截断" in result.answer
