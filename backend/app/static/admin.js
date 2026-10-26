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
