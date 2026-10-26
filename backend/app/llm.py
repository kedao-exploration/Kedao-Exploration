from __future__ import annotations

import json
import re
import time
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from .config import Settings
from .models import ActivityMatch, AggregateReport, StudentModel


T = TypeVar("T", bound=BaseModel)
PROMPT_VERSION = "student-model-v1"

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
STUDENT_ID_RE = re.compile(r"(?<!\d)\d{8,16}(?!\d)")


def scrub_pii(value: Any) -> Any:
    """Best-effort scrub before any payload leaves the server."""
    if isinstance(value, str):
        value = EMAIL_RE.sub("[已移除邮箱]", value)
        value = PHONE_RE.sub("[已移除手机号]", value)
        return STUDENT_ID_RE.sub("[已移除编号]", value)
    if isinstance(value, list):
        return [scrub_pii(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_pii(item) for key, item in value.items() if key.lower() not in {"name", "email", "student_number", "invite", "token"}}
    return value


class LLMService:
    def __init__(self, settings: Settings):
        api_key = settings.siliconflow_api_key.get_secret_value()
        if not api_key:
            raise RuntimeError("SILICONFLOW_API_KEY is not configured")
        self.settings = settings
        self.client = OpenAI(api_key=api_key, base_url=settings.siliconflow_base_url, timeout=90.0, max_retries=0)

    def _complete(self, schema: type[T], system: str, payload: dict[str, Any], schema_name: str) -> T:
        safe_payload = scrub_pii(payload)
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema.model_json_schema()},
        }
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.siliconflow_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"))},
                    ],
                    response_format=response_format,
                )
                content = response.choices[0].message.content or "{}"
                return schema.model_validate_json(content)
            except Exception as exc:  # provider/network/validation failures share retry policy
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError(f"LLM structured-output failure: {last_error}") from last_error

    def build_student_model(self, student_ref: str, evidence: list[dict[str, Any]]) -> StudentModel:
        system = """你是科道书院的学生画像分析器。只依据提供的证据建立可更新、可解释的学生模型。
要求：1) 不诊断心理疾病，不贴人格或能力标签；2) 事实和推断都必须给出 evidence_refs；
3) 不补造经历；证据不足时写入 uncertainties；4) 心理状态只用于自愿支持，不用于普通活动排除；
5) odyssey_a/b/c 是平行的假设情景，不是学生已经承诺的目标，必须作为可能性分别保留；
6) summary 控制在 180 字以内；7) 不输出姓名、邮箱、学号或其他可识别信息。"""
        return self._complete(StudentModel, system, {"student_ref": student_ref, "evidence": evidence}, "student_model")

    def build_aggregate_report(self, metrics: dict[str, Any], profiles: list[dict[str, Any]]) -> AggregateReport:
        system = """你是书院培养工作的群体洞察助手。确定性人数和比例以 metrics 为准，禁止自行改写数字。
分别给出主流需求和少数需求；少数需求即使只有一人也不能忽略，但最多列出八项最可行动的内容。
建议必须简洁、可实施，并说明预估覆盖人数和目标学生内部随机 ID。心理信号只可用于自愿支持类活动。
不要输出姓名、邮箱、学号，不要作医学诊断。"""
        return self._complete(AggregateReport, system, {"metrics": metrics, "profiles": profiles}, "aggregate_report")

    def match_activity(self, activity: dict[str, Any], student_ref: str, profile: dict[str, Any]) -> ActivityMatch:
        system = """判断该活动是否值得向这名学生推荐。必须逐个学生独立判断，不因其属于少数而降低权重。
综合兴趣、发展需要、已知时间限制和活动形式；心理状态不得用于普通活动的排除或负面评分。
理由必须引用画像中的 evidence_refs。include 代表建议进入 advisor 可编辑的候选名单，并非自动发送。"""
        return self._complete(ActivityMatch, system, {"activity": scrub_pii(activity), "student_ref": student_ref, "student_profile": profile}, "activity_match")
