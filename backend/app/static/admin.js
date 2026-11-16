document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-dialog-open]");
  if (opener) document.getElementById(opener.dataset.dialogOpen)?.showModal();
  if (event.target.closest("[data-dialog-close]")) event.target.closest("dialog")?.close();
  const assign = event.target.closest("[data-assign-survey]");
  if (assign) {
    const form = document.getElementById("assign-form");
    form.action = `/surveys/${assign.dataset.assignSurvey}/assign`;
    document.getElementById("assign-dialog")?.showModal();
  }
  const copyButton = event.target.closest("[data-copy-text], [data-copy-target]");
  if (copyButton) {
    const target = copyButton.dataset.copyTarget && document.getElementById(copyButton.dataset.copyTarget);
    const value = copyButton.dataset.copyText || target?.value || target?.textContent || "";
    const copy = navigator.clipboard?.writeText
      ? navigator.clipboard.writeText(value)
      : new Promise((resolve, reject) => {
          const helper = document.createElement("textarea");
          helper.value = value;
          helper.style.position = "fixed";
          helper.style.opacity = "0";
          document.body.appendChild(helper);
          helper.select();
          const ok = document.execCommand("copy");
          helper.remove();
          ok ? resolve() : reject(new Error("copy failed"));
        });
    copy.then(() => {
      const previous = copyButton.textContent;
      copyButton.textContent = "已复制";
      window.setTimeout(() => { copyButton.textContent = previous; }, 1600);
    }).catch(() => { copyButton.textContent = "请手动选择复制"; });
  }
});

const builder = document.getElementById("survey-builder");
const questionBuilder = document.getElementById("question-builder");
let questionIndex = 0;

function addQuestion() {
  questionIndex += 1;
  const wrapper = document.createElement("div");
  wrapper.className = "builder-question";
  wrapper.innerHTML = `<div class="builder-grid">
    <input data-field="label" placeholder="问题内容" required>
    <select data-field="type"><option value="single">单选题</option><option value="multiple">多选题</option><option value="short_text">短填空</option><option value="long_text">长填空</option><option value="scale">1–5 量表</option></select>
    <label><input data-field="required" type="checkbox"> 必填</label>
  </div><input class="builder-options" data-field="options" placeholder="选择题选项，用 | 分隔"><button class="button small danger" type="button" data-remove>删除</button>`;
  wrapper.querySelector("[data-remove]").addEventListener("click", () => wrapper.remove());
  questionBuilder.appendChild(wrapper);
}

document.getElementById("add-question")?.addEventListener("click", addQuestion);
if (builder) {
  addQuestion();
  builder.addEventListener("submit", (event) => {
    const questions = [...questionBuilder.querySelectorAll(".builder-question")].map((row, index) => {
      const type = row.querySelector('[data-field="type"]').value;
      const optionsText = row.querySelector('[data-field="options"]').value;
      const question = {
        id: `q_${Date.now()}_${index + 1}`,
        type,
        label: row.querySelector('[data-field="label"]').value.trim(),
        required: row.querySelector('[data-field="required"]').checked,
      };
      if (["single", "multiple"].includes(type)) {
        question.options = optionsText.split("|").map((label) => label.trim()).filter(Boolean).map((label) => ({ value: label, label }));
        if (question.options.length < 2) { event.preventDefault(); alert("每个选择题至少需要两个选项，并用 | 分隔。"); }
      }
      if (type === "scale") Object.assign(question, { min: 1, max: 5, minLabel: "较低", maxLabel: "较高" });
      if (type.includes("text")) question.maxLength = type === "short_text" ? 300 : 2000;
      return question;
    });
    if (!questions.length || questions.some((q) => !q.label)) { event.preventDefault(); alert("请至少添加一个完整问题。"); return; }
    document.getElementById("schema-json").value = JSON.stringify({ questions });
  });
}

const advisorChat = document.getElementById("advisor-chat");
const advisorChatForm = document.getElementById("advisor-chat-form");
const advisorChatQuestion = document.getElementById("advisor-chat-question");
const advisorChatTranscript = document.getElementById("chat-transcript");
const advisorChatSend = document.getElementById("advisor-chat-send");
const advisorChatAttachment = document.getElementById("chat-attachment-state");
const advisorChatHistory = [];

function appendChatMessage(role, text, options = {}) {
  const message = document.createElement("article");
  message.className = `chat-message ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "assistant" ? "✦" : "你";
  const body = document.createElement("div");
  const author = document.createElement("b");
  author.textContent = role === "assistant" ? "科道助手" : "导师";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  body.append(author, paragraph);

  if (options.students?.length) {
    const matches = document.createElement("div");
    matches.className = "chat-student-list";
    const title = document.createElement("strong");
    title.textContent = `相关学生 · ${options.students.length} 人`;
    matches.appendChild(title);
    options.students.forEach((student) => {
      const card = document.createElement("a");
      card.className = "chat-student-card";
      card.href = `/students/${encodeURIComponent(student.student_ref)}`;
      const name = document.createElement("b");
      name.textContent = student.name || "未填写姓名";
      const meta = document.createElement("span");
      meta.textContent = [student.year_level, student.major, student.email].filter(Boolean).join(" · ");
      const reason = document.createElement("small");
      reason.textContent = student.reason;
      card.append(name, meta, reason);
      matches.appendChild(card);
    });
    body.appendChild(matches);
  }

  if (options.limitations?.length) {
    const note = document.createElement("p");
    note.className = "chat-limitations";
    note.textContent = `数据提示：${options.limitations.join("；")}`;
    body.appendChild(note);
  }

  if (options.suggestions?.length) {
    const suggestions = document.createElement("div");
    suggestions.className = "chat-followups";
    options.suggestions.forEach((suggestion) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.chatPrompt = suggestion;
      button.textContent = suggestion;
      suggestions.appendChild(button);
    });
    body.appendChild(suggestions);
  }

  message.append(avatar, body);
  advisorChatTranscript.appendChild(message);
  advisorChatTranscript.scrollTop = advisorChatTranscript.scrollHeight;
  return message;
}

function chatErrorMessage(response, fallback) {
  if (!response) return fallback;
  return response.json().then((data) => data.detail || fallback).catch(() => fallback);
}

async function sendAdvisorChat(question) {
  if (!advisorChat || !question.trim() || advisorChatSend.disabled) return;
  const cleanQuestion = question.trim();
  appendChatMessage("user", cleanQuestion);
  advisorChatQuestion.value = "";
  advisorChatSend.disabled = true;
  advisorChatSend.classList.add("loading");
  const pending = appendChatMessage("assistant", "正在读取最新学生画像并整理回答…");
  pending.classList.add("pending");
  try {
    const response = await fetch("/api/advisor-chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": advisorChat.dataset.csrfToken,
      },
      body: JSON.stringify({ question: cleanQuestion, history: advisorChatHistory.slice(-8) }),
    });
    if (!response.ok) throw new Error(await chatErrorMessage(response, "暂时无法回答，请稍后重试。"));
    const data = await response.json();
    pending.remove();
    appendChatMessage("assistant", data.answer, {
      students: data.students,
      suggestions: data.follow_up_suggestions,
      limitations: data.limitations,
    });
    advisorChatHistory.push({ role: "user", content: cleanQuestion }, { role: "assistant", content: data.answer });
    while (advisorChatHistory.length > 8) advisorChatHistory.shift();
    const generated = new Date(data.context.generated_at).toLocaleString("zh-CN", { hour12: false, month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    advisorChatAttachment.innerHTML = "";
    const dot = document.createElement("span");
    advisorChatAttachment.append(dot, document.createTextNode(` 已附加 ${data.context.modeled_count}/${data.context.student_count} 份画像 · ${generated}`));
  } catch (error) {
    pending.remove();
    appendChatMessage("assistant", error.message || "暂时无法回答，请稍后重试。");
  } finally {
    advisorChatSend.disabled = false;
    advisorChatSend.classList.remove("loading");
    advisorChatQuestion.focus();
  }
}

advisorChatForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  sendAdvisorChat(advisorChatQuestion.value);
});

advisorChatQuestion?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    advisorChatForm.requestSubmit();
  }
});

document.addEventListener("click", (event) => {
  const prompt = event.target.closest("[data-chat-prompt]");
  if (!prompt || !advisorChatQuestion) return;
  advisorChatQuestion.value = prompt.dataset.chatPrompt;
  advisorChatQuestion.focus();
});
