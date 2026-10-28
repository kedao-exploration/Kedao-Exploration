import type { Answers, SurveyDefinition } from "../types";

const url = (import.meta.env.VITE_SUPABASE_URL || "").replace(/\/$/, "");
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || "";

function ensureConfig() {
  if (!url || !key) {
    throw new Error("页面尚未配置 Supabase，请联系书院老师。");
  }
}

async function rpc<T>(name: string, body: Record<string, unknown>): Promise<T> {
  ensureConfig();
  const response = await fetch(`${url}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload?.message === "string" ? payload.message : "提交失败，请稍后再试。";
    throw new Error(message);
  }
  return payload as T;
}

export async function submitOnboarding(answers: Answers) {
  return rpc<{ ok: boolean; student_id: string }>("submit_open_onboarding", {
    p_payload: answers,
  });
}

export async function loadSurvey(token: string) {
  return rpc<SurveyDefinition>("get_survey_by_token", { p_token: token });
}

export async function submitSurvey(token: string, answers: Answers) {
  return rpc<{ ok: boolean }>("submit_survey_response", {
    p_token: token,
    p_answers: answers,
  });
}
