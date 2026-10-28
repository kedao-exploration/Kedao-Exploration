import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Leaf,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { onboardingSteps } from "./onboarding";
import { loadSurvey, submitOnboarding, submitSurvey } from "./lib/supabase";
import type { Answers, OdysseyPlanAnswer, SurveyDefinition, SurveyQuestion } from "./types";

type Route = { page: "onboarding" | "survey"; token: string };

function parseRoute(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const params = new URLSearchParams(query);
  return { page: path === "survey" ? "survey" : "onboarding", token: params.get("token") || "" };
}

function App() {
  const [route, setRoute] = useState<Route>(parseRoute);
  useEffect(() => {
    const update = () => setRoute(parseRoute());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  return (
    <main className="page-shell">
      <Decorations />
      <header className="site-header">
        <a className="brand" href="#/onboarding" aria-label="科道书院成长画像首页">
          <span className="brand-mark"><Leaf size={19} /></span>
          <span><b>科道书院</b><small>成长画像 · DISCOVER</small></span>
        </a>
        <span className="privacy-pill"><ShieldCheck size={15} /> 信息仅用于成长支持</span>
      </header>
      {route.page === "survey" ? <FollowUpSurvey initialToken={route.token} /> : <Onboarding />}
      <footer>科道书院 · 尊重每一种成长节奏</footer>
    </main>
  );
}

function Decorations() {
  return <div className="decorations" aria-hidden="true"><i /><i /><i /></div>;
}

function SurveyTokenGate({ onContinue }: { onContinue: (token: string) => void }) {
  const [token, setToken] = useState("");
  return (
    <section className="hero-card token-card">
      <div className="hero-icon"><Sparkles /></div>
      <p className="eyebrow">一次轻量的回访</p>
      <h1>打开你的专属问卷</h1>
      <p className="hero-copy">输入老师发送给你的个人链接码，回答将用于更新成长画像。</p>
      <label className="token-input">
        <span>问卷链接码</span>
        <input value={token} onChange={(event) => setToken(event.target.value.trim())} placeholder="例如 QS-XXXX-XXXX" autoCapitalize="characters" />
      </label>
      <button className="primary-button" disabled={token.length < 8} onClick={() => onContinue(token)}>
        打开问卷 <ArrowRight size={18} />
      </button>
      <p className="fine-print">首次成长画像无需邀请码，可直接从首页填写。此处仅用于老师定向发送的后续问卷。</p>
    </section>
  );
}

function Onboarding() {
  const storageKey = "kedao-onboarding-open-v1";
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>({ consent: false });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!storageKey) return;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) setAnswers(JSON.parse(saved));
    } catch { /* ignore a corrupt local draft */ }
  }, [storageKey]);

  useEffect(() => {
    if (storageKey) localStorage.setItem(storageKey, JSON.stringify(answers));
  }, [answers, storageKey]);

  if (done) return <SuccessCard title="谢谢你认真完成" message="你的回答已经安全保存。书院会在后台生成可解释的成长画像，并据此减少无关信息、推荐更适合你的机会。" />;

  const current = onboardingSteps[step];
  const progress = ((step + 1) / onboardingSteps.length) * 100;

  const update = (id: string, value: Answers[string]) => {
    setError("");
    setAnswers((previous) => ({ ...previous, [id]: value }));
  };

  const validate = () => {
    if (step === 0 && answers.consent !== true) return "请先阅读并同意数据使用说明。";
    for (const question of current.questions) {
      if (!question.required) continue;
      const value = answers[question.id];
      if (value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) return `请完成“${question.label}”。`;
      if (question.type === "matrix") {
        const matrix = typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
        if (question.items?.some((item) => typeof matrix[item.id] !== "number")) return `请完成“${question.label}”中的每一行。`;
      }
      if (question.type === "odyssey") {
        const plan = typeof value === "object" && value !== null && !Array.isArray(value) ? value as Partial<OdysseyPlanAnswer> : {};
        if (["title", "five_year_goal", "core_activities", "capabilities", "challenges"].some((field) => !String(plan[field as keyof OdysseyPlanAnswer] || "").trim())) return `请完整填写“${question.label}”。`;
      }
    }
    if (step === 0) {
      const email = String(answers.email || "");
      if (!/^\S+@\S+\.\S+$/.test(email)) return "请检查邮箱格式。";
    }
    return "";
  };

  const next = async () => {
    const message = validate();
    if (message) { setError(message); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    if (step < onboardingSteps.length - 1) {
      setStep((value) => value + 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    setSubmitting(true);
    try {
      await submitOnboarding({ ...answers, form_version: "3.2.0" });
      localStorage.removeItem(storageKey);
      setDone(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "提交失败，请稍后再试。");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="form-card">
      <div className="form-topline">
        <div><span>第 {step + 1} 步，共 {onboardingSteps.length} 步</span><b>约剩 {[14, 12, 10, 8, 6, 4][step] || 2} 分钟</b></div>
        <div className="progress-track" aria-label={`完成进度 ${Math.round(progress)}%`}><span style={{ width: `${progress}%` }} /></div>
      </div>
      <div className="section-heading">
        <p className="eyebrow">{current.eyebrow}</p>
        <h1>{current.title}</h1>
        <p>{current.description}</p>
      </div>
      {step === 0 && <ConsentPanel checked={answers.consent === true} onChange={(checked) => update("consent", checked)} />}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="questions">
        {current.questions.map((question, index) => <QuestionField key={question.id} question={question} value={answers[question.id]} onChange={(value) => update(question.id, value)} number={index + 1} />)}
      </div>
      <div className="form-actions">
        <button className="secondary-button" disabled={step === 0 || submitting} onClick={() => { setStep((value) => value - 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}><ArrowLeft size={18} /> 上一步</button>
        <button className="primary-button" disabled={submitting} onClick={next}>{submitting ? <><LoaderCircle className="spin" size={18} /> 正在安全保存</> : step === onboardingSteps.length - 1 ? <>提交画像 <Check size={18} /></> : <>继续 <ArrowRight size={18} /></>}</button>
      </div>
      <p className="autosave"><CheckCircle2 size={14} /> 已在这台设备自动暂存</p>
    </section>
  );
}

function ConsentPanel({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <div className="consent-panel">
      <ShieldCheck size={22} />
      <div>
        <b>在开始前，请确认你了解这些信息如何被使用</b>
        <p>回答会持续保存在书院系统中，用于成长支持、活动设计与个性化推荐。去除姓名、邮箱和学号后的内容会发送给第三方大模型生成结构化画像；结果由培养老师复核，不用于医学诊断或高风险自动决策。你可以联系培养老师申请撤回或删除。</p>
        <label className="consent-check"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>我已阅读并同意上述用途</span></label>
      </div>
    </div>
  );
}

function QuestionField({ question, value, onChange, number }: { question: SurveyQuestion; value: Answers[string]; onChange: (value: Answers[string]) => void; number?: number }) {
  const toggle = (option: string) => {
    const current = Array.isArray(value) ? value : [];
    onChange(current.includes(option) ? current.filter((item) => item !== option) : [...current, option]);
  };
  const matrixValue = typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, number> : {};
  const odysseyValue = typeof value === "object" && value !== null && !Array.isArray(value) ? value as Partial<OdysseyPlanAnswer> : {};
  const updateOdyssey = (field: keyof OdysseyPlanAnswer, next: string) => onChange({
    title: "", five_year_goal: "", core_activities: "", capabilities: "", challenges: "",
    ...odysseyValue,
    [field]: next,
  });
  return (
    <fieldset className={`question ${question.sensitive ? "sensitive" : ""} ${question.type === "odyssey" ? "odyssey-question" : ""}`}>
      <legend>{number && <span className="question-number">{number.toString().padStart(2, "0")}</span>}<span>{question.label}{question.required && <em>必填</em>}</span></legend>
      {question.description && question.type !== "odyssey" && <p className="question-description">{question.description}</p>}
      {question.sensitive && <p className="sensitive-note"><LockKeyhole size={13} /> 状态问题，可选择暂不回答</p>}
      {question.type === "short_text" && <input className="text-field" value={typeof value === "string" ? value : ""} maxLength={question.maxLength} onChange={(event) => onChange(event.target.value)} />}
      {question.type === "long_text" && <textarea className="text-field" rows={4} value={typeof value === "string" ? value : ""} maxLength={question.maxLength} onChange={(event) => onChange(event.target.value)} placeholder="不用写很长，一两句话就好" />}
      {(question.type === "single" || question.type === "multiple") && <div className="option-grid">{question.options?.map((option) => {
        const selected = question.type === "multiple" ? Array.isArray(value) && value.includes(option.value) : value === option.value;
        return <button type="button" key={option.value} className={`option-card ${selected ? "selected" : ""}`} aria-pressed={selected} onClick={() => question.type === "multiple" ? toggle(option.value) : onChange(option.value)}><span>{option.label}</span>{selected && <Check size={16} />}</button>;
      })}</div>}
      {question.type === "scale" && <div className="scale-wrap"><div className="scale-labels"><span>{question.minLabel}</span><span>{question.maxLabel}</span></div><div className="scale-options">{Array.from({ length: (question.max || 5) - (question.min || 1) + 1 }, (_, index) => index + (question.min || 1)).map((score) => <button type="button" key={score} className={value === score ? "selected" : ""} onClick={() => onChange(score)}>{score}</button>)}</div></div>}
      {question.type === "matrix" && <div className="matrix-wrap"><div className="matrix-axis"><span>{question.minLabel}</span><span>{question.maxLabel}</span></div>{question.items?.map((item) => <div className="matrix-row" key={item.id}><span>{item.label}</span><div className="scale-options">{Array.from({ length: (question.max || 5) - (question.min || 1) + 1 }, (_, index) => index + (question.min || 1)).map((score) => <button type="button" key={score} aria-label={`${item.label}：${score}分`} className={matrixValue[item.id] === score ? "selected" : ""} onClick={() => onChange({ ...matrixValue, [item.id]: score })}>{score}</button>)}</div></div>)}</div>}
      {question.type === "odyssey" && <div className={`odyssey-card ${question.tone || "coral"}`}>
        <div className="odyssey-heading"><span>{question.badge}</span><small>{question.description}</small></div>
        <label>标题<input className="text-field" maxLength={120} value={odysseyValue.title || ""} placeholder={question.placeholders?.title} onChange={(event) => updateOdyssey("title", event.target.value)} /></label>
        <label>目标<textarea className="text-field" rows={3} maxLength={800} value={odysseyValue.five_year_goal || ""} placeholder={question.placeholders?.five_year_goal} onChange={(event) => updateOdyssey("five_year_goal", event.target.value)} /></label>
        <label>核心活动<textarea className="text-field" rows={3} maxLength={800} value={odysseyValue.core_activities || ""} placeholder={question.placeholders?.core_activities} onChange={(event) => updateOdyssey("core_activities", event.target.value)} /></label>
        <label>需要的能力<textarea className="text-field" rows={3} maxLength={800} value={odysseyValue.capabilities || ""} placeholder={question.placeholders?.capabilities} onChange={(event) => updateOdyssey("capabilities", event.target.value)} /></label>
        <label>可能的挑战<textarea className="text-field" rows={3} maxLength={800} value={odysseyValue.challenges || ""} placeholder={question.placeholders?.challenges} onChange={(event) => updateOdyssey("challenges", event.target.value)} /></label>
      </div>}
    </fieldset>
  );
}

function FollowUpSurvey({ initialToken }: { initialToken: string }) {
  const [token, setToken] = useState(initialToken);
  const [definition, setDefinition] = useState<SurveyDefinition | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    loadSurvey(token).then(setDefinition).catch((cause) => setError(cause instanceof Error ? cause.message : "无法加载问卷")).finally(() => setLoading(false));
  }, [token]);

  const requiredMissing = useMemo(() => definition?.questions.find((question) => question.required && (answers[question.id] === undefined || answers[question.id] === "" || (Array.isArray(answers[question.id]) && (answers[question.id] as string[]).length === 0))), [answers, definition]);

  if (!token) return <SurveyTokenGate onContinue={(value) => { setToken(value); window.location.hash = `#/survey?token=${encodeURIComponent(value)}`; }} />;
  if (loading) return <LoadingCard />;
  if (done) return <SuccessCard title="反馈已收到" message="谢谢你的更新。新的回答会进入画像更新队列，老师看到的是带证据和更新时间的新版本。" />;
  if (!definition) return <MessageCard title="暂时无法打开问卷" message={error || "链接可能已失效，请联系培养老师重新生成。"} />;

  const send = async () => {
    if (requiredMissing) { setError(`请完成“${requiredMissing.label}”。`); return; }
    setLoading(true); setError("");
    try { await submitSurvey(token, answers); setDone(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "提交失败，请稍后再试。"); }
    finally { setLoading(false); }
  };

  return <section className="form-card"><div className="section-heading"><p className="eyebrow">专属跟进问卷 · V{definition.version}</p><h1>{definition.title}</h1><p>{definition.description}</p></div>{error && <div className="error-banner">{error}</div>}<div className="questions">{definition.questions.map((question, index) => <QuestionField key={question.id} question={question} value={answers[question.id]} onChange={(value) => setAnswers((previous) => ({ ...previous, [question.id]: value }))} number={index + 1} />)}</div><div className="form-actions end"><button className="primary-button" disabled={loading} onClick={send}>{loading ? "提交中…" : "提交反馈"} <Check size={18} /></button></div></section>;
}

function LoadingCard() { return <section className="hero-card message-card"><LoaderCircle className="spin" size={32} /><h1>正在加载问卷</h1><p>很快就好。</p></section>; }
function MessageCard({ title, message }: { title: string; message: string }) { return <section className="hero-card message-card"><BookOpen size={32} /><h1>{title}</h1><p>{message}</p></section>; }
function SuccessCard({ title, message }: { title: string; message: string }) { return <section className="hero-card success-card"><div className="success-icon"><CheckCircle2 /></div><p className="eyebrow">已完成</p><h1>{title}</h1><p className="hero-copy">{message}</p><a className="secondary-button link-button" href="#/onboarding">返回首页</a></section>; }

export default App;
