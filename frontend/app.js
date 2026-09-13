/*
 * UrjaKavach frontend logic.
 * Owner: Track C. Pure vanilla JS, no build step, no dependencies —
 * so it also works with zero network access, which is the point.
 */

const API = "http://localhost:8000";
let uploadedFile = null;

/* ---------------------------------------------------------------- */
/* Scenario switching                                                */
/* ---------------------------------------------------------------- */
function selectScenario(name) {
  document.getElementById("tab-doc").classList.toggle("active", name === "doc");
  document.getElementById("tab-code").classList.toggle("active", name === "code");
  document.getElementById("panel-doc").classList.toggle("panel-hidden", name !== "doc");
  document.getElementById("panel-code").classList.toggle("panel-hidden", name !== "code");
  document.getElementById("docInputSection").classList.toggle("panel-hidden", name !== "doc");
  document.getElementById("codeInputSection").classList.toggle("panel-hidden", name !== "code");

  document.querySelectorAll(".tree-item").forEach(el => el.classList.remove("selected"));
  document.querySelector('.tree-item[data-panel="' + name + '"]').classList.add("selected");
}

/* ---------------------------------------------------------------- */
/* File upload                                                       */
/* ---------------------------------------------------------------- */
function toggleSample() {
  const useSample = document.getElementById("useSampleToggle").checked;
  const dz = document.getElementById("dropZone");
  dz.style.opacity = useSample ? 0.5 : 1;
  dz.style.pointerEvents = useSample ? "none" : "auto";
}

function onFileChosen(evt) {
  const file = evt.target.files[0];
  if (!file) return;

  uploadedFile = file;
  document.getElementById("useSampleToggle").checked = false;
  toggleSample();

  const dz = document.getElementById("dropZone");
  dz.classList.add("has-file");
  dz.textContent = file.name;

  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById("filePreview");
    img.src = e.target.result;
    img.classList.remove("panel-hidden");
  };
  reader.readAsDataURL(file);
}

/* ---------------------------------------------------------------- */
/* Activity log                                                      */
/* ---------------------------------------------------------------- */
function stageClass(stage) {
  if (stage === "plan") return "t-plan";
  if (stage === "route") return "t-route";
  if (stage.indexOf("tool") === 0) return "t-tool";
  if (stage === "iterate_check") return "t-iterate";
  if (stage === "done") return "t-done";
  return "";
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function refreshLogs() {
  try {
    const res = await fetch(API + "/api/logs");
    const data = await res.json();
    const panel = document.getElementById("logPanel");

    if (!data.logs || !data.logs.length) {
      panel.innerHTML = '<div class="term-line term-empty">$ waiting for a flow to run…</div>';
      return;
    }

    panel.innerHTML = data.logs.map(l =>
      '<div class="term-line"><span class="term-prompt">[' + l.ts + ']</span> ' +
      '<span class="' + stageClass(l.stage) + '">' + escapeHtml(l.stage.toUpperCase()) + '</span> — ' +
      escapeHtml(l.detail) + '</div>'
    ).join("");
    panel.scrollTop = panel.scrollHeight;
  } catch (e) {
    console.error("log refresh failed", e);
  }
}

/* ---------------------------------------------------------------- */
/* Error display — never fail silently during a demo                 */
/* ---------------------------------------------------------------- */
function showError(targetId, err, res, rawText) {
  let extra = "";
  if (res) extra += "<div>HTTP status: " + res.status + " " + res.statusText + "</div>";
  if (rawText) extra += "<pre>" + escapeHtml(rawText.slice(0, 2000)) + "</pre>";

  document.getElementById(targetId).innerHTML =
    '<div class="error-box"><strong>Something went wrong</strong>' +
    "<div>" + escapeHtml(err && err.message ? err.message : String(err)) + "</div>" +
    extra + "</div>";
}

/* ---------------------------------------------------------------- */
/* Scenario 1 — document flow                                        */
/* ---------------------------------------------------------------- */
async function runDocFlow() {
  const btn = document.getElementById("runDoc");
  const pill = document.getElementById("pill-doc");

  btn.disabled = true;
  btn.textContent = "Running…";
  pill.textContent = "running";
  pill.className = "status-pill";
  document.getElementById("docResult").innerHTML = "";
  document.getElementById("statusFlow").textContent = "running document_analysis.flow…";

  let res, rawText;
  try {
    const form = new FormData();
    const useSample = document.getElementById("useSampleToggle").checked;
    form.append("use_sample", useSample ? "true" : "false");
    if (!useSample && uploadedFile) form.append("file", uploadedFile);

    res = await fetch(API + "/api/tasks/document", { method: "POST", body: form });
    rawText = await res.text();
    if (!res.ok) throw new Error("Server returned an error");

    const data = JSON.parse(rawText);
    await refreshLogs();

    const groundedTag = data.grounded
      ? '<span class="tag tag-ok">grounded on plant docs</span>'
      : '<span class="tag">no KB grounding</span>';
    const sourceTag = data.source === "model"
      ? '<span class="tag tag-ok">local model</span>'
      : '<span class="tag">stub mode</span>';

    document.getElementById("docResult").innerHTML =
      '<div class="result-box">' +
        '<div class="result-heading">Key Findings ' + sourceTag + groundedTag + "</div>" +
        '<ul class="findings">' +
          data.findings.map(f => "<li>" + escapeHtml(f) + "</li>").join("") +
        "</ul>" +
        '<a class="download-link" href="' + API + "/api/outputs/" + data.output_file +
          '" target="_blank">Download ' + escapeHtml(data.output_file) + "</a>" +
      "</div>";

    pill.textContent = "done";
    pill.className = "status-pill ok";
    document.getElementById("statusFlow").textContent =
      "document_analysis.flow — task " + data.task_id + " complete";
  } catch (err) {
    console.error(err);
    showError("docResult", err, res, rawText);
    pill.textContent = "error";
    pill.className = "status-pill";
    document.getElementById("statusFlow").textContent = "document_analysis.flow — error";
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Document Flow";
  }
}

/* ---------------------------------------------------------------- */
/* Scenario 2 — code flow                                            */
/* ---------------------------------------------------------------- */
async function runCodeFlow() {
  const btn = document.getElementById("runCode");
  const pill = document.getElementById("pill-code");

  btn.disabled = true;
  btn.textContent = "Running…";
  pill.textContent = "running";
  pill.className = "status-pill";
  document.getElementById("codeResult").innerHTML = "";
  document.getElementById("statusFlow").textContent = "running code_generation.flow…";

  let res, rawText;
  try {
    const form = new FormData();
    form.append("prompt", document.getElementById("codePrompt").value);

    res = await fetch(API + "/api/tasks/code", { method: "POST", body: form });
    rawText = await res.text();
    if (!res.ok) throw new Error("Server returned an error");

    const data = JSON.parse(rawText);
    await refreshLogs();

    const okBadge = data.result.ok
      ? '<span class="badge-ok">VERIFIED OK</span>'
      : '<span class="badge-fail">FAILED</span>';
    const sourceTag = data.source === "model"
      ? '<span class="tag tag-ok">local model</span>'
      : '<span class="tag">stub mode</span>';

    document.getElementById("codeResult").innerHTML =
      '<div class="result-box">' +
        '<div class="result-heading">Generated Code ' + sourceTag + "</div>" +
        '<div class="code-block">' +
          '<div class="cb-header"><span>generated.py</span><span>code model</span></div>' +
          "<pre>" + escapeHtml(data.code) + "</pre>" +
        "</div>" +
        '<div class="result-heading">Sandbox Output — ' + okBadge + "</div>" +
        '<div class="code-block">' +
          '<div class="cb-header"><span>stdout</span><span>isolated subprocess, timeout-guarded</span></div>' +
          "<pre>" + escapeHtml(data.result.stdout || data.result.stderr || "(no output)") + "</pre>" +
        "</div>" +
      "</div>";

    pill.textContent = "done";
    pill.className = "status-pill ok";
    document.getElementById("statusFlow").textContent =
      "code_generation.flow — task " + data.task_id + " complete";
  } catch (err) {
    console.error(err);
    showError("codeResult", err, res, rawText);
    pill.textContent = "error";
    pill.className = "status-pill";
    document.getElementById("statusFlow").textContent = "code_generation.flow — error";
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Code Flow";
  }
}

/* ---------------------------------------------------------------- */
/* Health check on load                                              */
/* ---------------------------------------------------------------- */
(async function () {
  try {
    const res = await fetch(API + "/api/health");
    const data = await res.json();

    document.getElementById("healthLine").textContent = "connected — " + data.mode;

    const modeLabel = data.use_real_model ? "real local models" : "stub mode";
    document.getElementById("modelLine").textContent =
      modeLabel + ": " + data.reasoning_model + " / " + data.code_model;

    const kb = data.knowledge_base_status || {};
    document.getElementById("kbLine").textContent =
      kb.available ? "knowledge base: loaded" : "knowledge base: not built";
  } catch (e) {
    document.getElementById("healthLine").textContent =
      "backend not reachable at localhost:8000 — start it with uvicorn";
  }
})();
