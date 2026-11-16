import json
import stat

from app.advisor_chat import ATTACHMENT_FILENAME, build_advisor_chat_attachment, deidentify_chat_text


class FakeDB:
    def select(self, table, *, select="*", params=None, limit=None):
        if table == "students":
            return [{
                "id": "38b74b34-1b4d-4aa2-9ae0-4f73777a9101",
                "name": "张三",
                "email": "zhangsan@example.edu.cn",
                "student_number": "2026123456",
                "major": "人工智能",
                "year_level": "大二",
                "model_status": "ready",
                "last_profile_input_at": "2026-11-15T08:00:00Z",
                "current_model_version_id": "model-version-1",
            }]
        if table == "student_model_versions":
            return [{
                "id": "model-version-1",
                "profile": {
                    "summary": "对保研与机器人方向感兴趣",
                    "interests": [{"statement": "机器人", "evidence_refs": ["onboarding:1:interest_topics"]}],
                },
                "summary": "对保研与机器人方向感兴趣",
                "generated_at": "2026-11-15T08:05:00Z",
                "prompt_version": "student-model-v1",
            }]
        raise AssertionError(table)


def test_attachment_is_private_and_deidentified(tmp_path):
    attachment, identities = build_advisor_chat_attachment(FakeDB(), tmp_path)
    path = tmp_path / ATTACHMENT_FILENAME
    content = path.read_text(encoding="utf-8")

    assert attachment["student_count"] == 1
    assert attachment["modeled_count"] == 1
    assert identities["38b74b34-1b4d-4aa2-9ae0-4f73777a9101"]["name"] == "张三"
    assert "张三" not in content
    assert "zhangsan@example.edu.cn" not in content
    assert "2026123456" not in content
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(content)["students"][0]["major"] == "人工智能"


def test_known_identifiers_are_replaced_before_llm_use(tmp_path):
    _, identities = build_advisor_chat_attachment(FakeDB(), tmp_path)
    safe = deidentify_chat_text("张三（2026123456，zhangsan@example.edu.cn）适合什么活动？", identities)

    assert "张三" not in safe
    assert "2026123456" not in safe
    assert "zhangsan@example.edu.cn" not in safe
    assert "学生[38b74b34-1b4d-4aa2-9ae0-4f73777a9101]" in safe
