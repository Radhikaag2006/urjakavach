/*
 * UrjaKavach frontend logic — Claude-style layout.
 * Owner: Track C. Pure vanilla JS, no build step, no dependencies.
 */

const API = "http://localhost:8000";

let authToken = localStorage.getItem('uk_auth_token') || null;

function showAuthError(msg) {
  document.getElementById('authError').textContent = msg;
}

let authMode = 'login';

function toggleAuthMode() {
  authMode = authMode === 'login' ? 'register' : 'login';
  document.getElementById('loginForm').classList.toggle('panel-hidden', authMode !== 'login');
  document.getElementById('registerForm').classList.toggle('panel-hidden', authMode !== 'register');
  document.getElementById('authError').textContent = '';
}


let currentUserProfile = {};

async function fetchMe() {
  try {
    const res = await fetch(API + '/api/auth/me', { headers: getAuthHeaders() });
    if (res.ok) {
      currentUserProfile = await res.json();
      document.getElementById('userName').textContent = currentUserProfile.name;
      document.getElementById('userAvatar').textContent = currentUserProfile.name.charAt(0).toUpperCase();
    }
  } catch (e) {}
}

function openProfileModal() {
  document.getElementById('editName').value = currentUserProfile.name || '';
  document.getElementById('editProfession').value = currentUserProfile.profession || '';
  document.getElementById('editCountry').value = currentUserProfile.country || '';
  openModal('profileModal');
}

async function handleUpdateProfile() {
  const payload = {
    name: document.getElementById('editName').value,
    profession: document.getElementById('editProfession').value,
    country: document.getElementById('editCountry').value
  };
  try {
    const res = await fetch(API + '/api/auth/me', {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('profileModal');
      await fetchMe();
    } else {
      alert('Failed to update profile');
    }
  } catch(e) {
    alert('Connection failed');
  }
}

async function handleLogin() {
  const identifier = document.getElementById('loginId').value;
  const password = document.getElementById('loginPassword').value;
  if (!identifier || !password) return showAuthError('Please enter details');
  
  const form = new FormData();
  form.append('identifier', identifier);
  form.append('password', password);
  
  try {
    const res = await fetch(API + '/api/auth/login', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      authToken = data.token;
      localStorage.setItem('uk_auth_token', authToken);
      document.getElementById('authScreen').classList.add('panel-hidden');
      document.getElementById('mainApp').classList.remove('panel-hidden');
      await fetchMe();
      loadHistory();
    } else {
      showAuthError(data.detail || 'Login failed');
    }
  } catch (e) {
    showAuthError('Connection failed');
  }
}

function handleLogout() {
  authToken = null;
  localStorage.removeItem('uk_auth_token');
  window.location.reload();
}

async function handleRegister() {
  const name = document.getElementById('regName').value;
  const profession = document.getElementById('regProfession').value;
  const identifier = document.getElementById('regId').value;
  const github = document.getElementById('regGithub').value;
  const country = document.getElementById('regCountry').value;
  const empCode = document.getElementById('regEmpCode').value;
  const password = document.getElementById('regPassword').value;
  
  if (!identifier || !password || !name || !empCode) return showAuthError('Please fill required fields');
  
  const form = new FormData();
  form.append('identifier', identifier);
  form.append('password', password);
  form.append('name', name);
  form.append('profession', profession);
  form.append('country', country);
  form.append('emp_code', empCode);
  form.append('github_id', github);
  
  try {
    const res = await fetch(API + '/api/auth/register', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      // auto login
      document.getElementById('loginId').value = identifier;
      document.getElementById('loginPassword').value = password;
      handleLogin();
    } else {
      showAuthError(data.detail || 'Registration failed');
    }
  } catch (e) {
    showAuthError('Connection failed');
  }
}

function getAuthHeaders() {
  return authToken ? { 'Authorization': 'Bearer ' + authToken } : {};
}

document.addEventListener("DOMContentLoaded", () => {
  if (authToken) {
    document.getElementById('authScreen').classList.add('panel-hidden');
    document.getElementById('mainApp').classList.remove('panel-hidden');
    fetchMe();
  }
});
let uploadedFile = null;      // for the document-flow modal
let chatAttachments = [];     // for the chat input's attach button (supports multiple)
let currentSessionId = null;

/* ---------------------------------------------------------------- */
/* Theme                                                             */
/* ---------------------------------------------------------------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("themeIcon").textContent =
    theme === "dark" ? "\u263D" : "\u2600";
  document.getElementById("themeLabel").textContent =
    theme === "dark" ? "Dark mode" : "Light mode";
  try { localStorage.setItem("uk_theme", theme); } catch (e) {}
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  applyTheme(current === "dark" ? "light" : "dark");
}

(function initTheme() {
  let saved = "dark";
  try { saved = localStorage.getItem("uk_theme") || "dark"; } catch (e) {}
  applyTheme(saved);
})();

/* ---------------------------------------------------------------- */
/* Modals                                                            */
/* ---------------------------------------------------------------- */
function openModal(id) { document.getElementById(id).classList.remove("panel-hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("panel-hidden"); }

/* ---------------------------------------------------------------- */
/* Activity panel                                                    */
/* ---------------------------------------------------------------- */
function toggleActivityPanel() {
  const panel = document.getElementById("activityPanel");
  panel.classList.toggle("open");
  if (panel.classList.contains("open")) refreshLogs();
}

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
/* Chat message rendering                                            */
/* ---------------------------------------------------------------- */
function hideEmptyState() {
  const el = document.getElementById("emptyState");
  if (el) el.remove();
}

function addMessageBubble(role, html) {
  hideEmptyState();
  const wrap = document.createElement("div");
  wrap.className = "msg msg-" + role;
  wrap.innerHTML =
    '<div class="msg-avatar">' + (role === "user" ? "R" : "U") + "</div>" +
    '<div class="msg-body">' + html + "</div>";
  const container = document.getElementById("chatMessages");
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
  return wrap;
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

function onChatInputKeydown(evt) {
  if (evt.key === "Enter" && !evt.shiftKey) {
    evt.preventDefault();
    sendChatMessage();
  }
}

/* ---------------------------------------------------------------- */
/* Chat send/receive                                                 */
/* ---------------------------------------------------------------- */
function onChatFileChosen(evt) {
  const files = Array.from(evt.target.files || []);
  if (!files.length) return;
  for (const f of files) {
    if (!chatAttachments.some(existing => existing.name === f.name && existing.size === f.size)) {
      chatAttachments.push(f);
    }
  }
  renderAttachPreview();
  document.getElementById("chatFileInput").value = "";
}

function removeChatAttachment(idx) {
  chatAttachments.splice(idx, 1);
  renderAttachPreview();
}

function clearChatAttachments() {
  chatAttachments = [];
  document.getElementById("chatFileInput").value = "";
  renderAttachPreview();
}

// Backward compatibility alias
function clearChatAttachment() {
  clearChatAttachments();
}

function getFileIcon(filename) {
  const ext = (filename || "").split('.').pop().toLowerCase();
  if (["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "svg"].includes(ext)) return "&#128444;";
  if (["py", "cpp", "c", "h", "hpp", "java", "js", "ts", "sh", "sql", "html", "css"].includes(ext)) return "&#128187;";
  if (["csv", "tsv", "xlsx", "xls"].includes(ext)) return "&#128202;";
  if (["pdf", "docx", "doc", "txt", "md", "json", "xml", "log"].includes(ext)) return "&#128196;";
  return "&#128206;";
}

const snippetStore = {};

function copySnippet(id, btn) {
  const code = snippetStore[id] || "";
  if (!code) return;
  navigator.clipboard.writeText(code).then(() => {
    const old = btn.textContent;
    btn.textContent = "✓ Copied!";
    btn.classList.add("btn-copied");
    setTimeout(() => {
      btn.textContent = old;
      btn.classList.remove("btn-copied");
    }, 2000);
  });
}

function downloadSnippet(id, filename) {
  const code = snippetStore[id] || "";
  if (!code) return;
  const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename || "solution.py";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function runSnippetInSandbox(id, terminalId) {
  const code = snippetStore[id] || "";
  const terminal = document.getElementById(terminalId);
  if (!terminal || !code) return;

  terminal.classList.remove("panel-hidden");
  terminal.innerHTML = '<div class="cmd-line">$ python -u task.py</div><div style="color:var(--text-dim);">&#9684; Executing code in isolated sandbox...</div>';

  try {
    const form = new FormData();
    form.append("code", code);
    const res = await fetch(API + "/api/sandbox/execute", {
      method: "POST",
      body: form,
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Sandbox execution request failed");
    const data = await res.json();
    const isOk = data.ok;
    const output = data.stdout || (data.stderr ? "Stderr:\n" + data.stderr : "(No stdout returned)");
    terminal.innerHTML = `
      <div class="cmd-line">$ python -u task.py <span style="float:right;font-size:10.5px;color:${isOk ? '#4ade80' : '#f87171'}">${isOk ? '✓ Exit 0' : '✗ Failed'}</span></div>
      <div>${escapeHtml(output)}</div>
    `;
  } catch (err) {
    terminal.innerHTML = `<div class="cmd-line">$ python -u task.py</div><div style="color:#f87171;">Error: ${escapeHtml(err.message)}</div>`;
  }
}

function copyMessageText(msgId, btn) {
  const text = snippetStore[msgId] || "";
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const old = btn.textContent;
    btn.textContent = "✓ Copied Text!";
    btn.classList.add("btn-copied");
    setTimeout(() => {
      btn.textContent = old;
      btn.classList.remove("btn-copied");
    }, 2000);
  });
}

function exportMessageMarkdown(msgId) {
  const text = snippetStore[msgId] || "";
  if (!text) return;
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `UrjaKavach_Deliverable_${Date.now().toString().slice(-4)}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function formatDeliverableMarkdown(text, msgId) {
  if (!text) return "";
  snippetStore[msgId] = text;

  // Extract and format code blocks ```lang ... ```
  let codeIdx = 0;
  const withCode = text.replace(/```(\w+)?\s*\n([\s\S]*?)```/g, (match, lang, code) => {
    const sId = `${msgId}_code_${codeIdx++}`;
    snippetStore[sId] = code.trim();
    const language = (lang || "python").toLowerCase();
    const isPy = ["python", "py"].includes(language);
    const terminalId = `term_${sId}`;

    return `
      <div class="chat-sandbox-box">
        <div class="chat-sandbox-header">
          <div class="chat-sandbox-title">&#9889; ${escapeHtml((lang || 'CODE').toUpperCase())} DELIVERABLE</div>
          <div style="display:flex;gap:6px;align-items:center;">
            <button class="deliverable-btn" onclick="copySnippet('${sId}', this)">&#128203; Copy</button>
            <button class="deliverable-btn" onclick="downloadSnippet('${sId}', 'solution.${isPy ? 'py' : 'txt'}')">&#128190; .${isPy ? 'py' : 'txt'}</button>
            ${isPy ? `<button class="deliverable-btn deliverable-btn-primary" onclick="runSnippetInSandbox('${sId}', '${terminalId}')">&#9654; Run in Sandbox</button>` : ''}
          </div>
        </div>
        <pre class="chat-sandbox-code"><code>${escapeHtml(code.trim())}</code></pre>
        <div id="${terminalId}" class="chat-sandbox-terminal panel-hidden"></div>
      </div>
    `;
  });

  // Markdown headers, bold, italics, lists, inline code
  let html = withCode
    .replace(/^### (.*$)/gim, '<h4>$1</h4>')
    .replace(/^## (.*$)/gim, '<h3>$1</h3>')
    .replace(/^# (.*$)/gim, '<h2>$1</h2>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\s*[-*•]\s+(.*$)/gim, '<li>$1</li>')
    .replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

  html = html.replace(/((?:<li>.*<\/li>\s*)+)/g, '<ul>$1</ul>');

  const parts = html.split(/(<div class="chat-sandbox-box">[\s\S]*?<\/div>\s*<\/div>)/g);
  return parts.map((part, i) => {
    if (i % 2 === 1) return part;
    return part.split(/\n\n+/).map(p => p.trim() ? `<p>${p.replace(/\n/g, '<br>')}</p>` : '').join('');
  }).join('');
}

function renderDeliverablesHtml(codeResult, docResult, msgId, findings) {
  let html = "";

  // 1. Text Deliverable: Extracted Highlights from Documents
  if (findings && findings.length > 0) {
    html += `
      <div class="deliverable-highlights">
        <div class="deliverable-highlights-title">&#128269; Key Extracted Highlights &amp; Findings</div>
        <ul>${findings.map(f => `<li>${escapeHtml(f)}</li>`).join("")}</ul>
      </div>
    `;
  }

  // 2. Code Deliverable: Autonomous Code Generation & Execution
  if (codeResult && (codeResult.code || codeResult.stdout)) {
    const sId = `${msgId}_auto_code`;
    snippetStore[sId] = codeResult.code || "";
    const isOk = codeResult.ok;
    const statusPill = isOk
      ? '<span class="tag tag-ok">&#10003; Sandbox Verified (exit 0)</span>'
      : '<span class="tag" style="color:var(--red,#f87171);">&#10007; Sandbox Failed</span>';
    const sourceTag = codeResult.source === "model" ? '<span class="tag">Qwen2.5-Coder</span>' : '<span class="tag">code-stub</span>';
    const terminalId = `term_${sId}`;

    html += `
      <div class="chat-sandbox-box">
        <div class="chat-sandbox-header">
          <div class="chat-sandbox-title">&#9889; Autonomous Code Deliverable</div>
          <div style="display:flex;gap:6px;align-items:center;">
            ${sourceTag} ${statusPill}
            <button class="deliverable-btn" onclick="copySnippet('${sId}', this)">&#128203; Copy</button>
            <button class="deliverable-btn" onclick="downloadSnippet('${sId}', 'solution.py')">&#128190; .py</button>
            <button class="deliverable-btn deliverable-btn-primary" onclick="runSnippetInSandbox('${sId}', '${terminalId}')">&#9654; Re-run</button>
          </div>
        </div>
        ${codeResult.code ? `<pre class="chat-sandbox-code"><code>${escapeHtml(codeResult.code)}</code></pre>` : ""}
        <div id="${terminalId}" class="chat-sandbox-terminal">
          <div class="cmd-line">$ python -u task.py</div>
          <div>${escapeHtml(codeResult.stdout || (codeResult.stderr ? "Stderr: " + codeResult.stderr : "(No stdout captured)"))}</div>
        </div>
      </div>
    `;
  }

  // 3. Document / Presentation / Spreadsheet Deliverable
  if (docResult && (docResult.output_file || docResult.download_url)) {
    const docName = docResult.output_file || "Deliverable";
    const dlUrl = docResult.download_url || `/api/download/${docName}`;
    const fileType = (docResult.file_type || (docName.split('.').pop()) || 'doc').toLowerCase();
    let typeLabel = "Generated on-premise deliverable ready for sign-off";
    let icon = "&#128196;";
    let btnText = "Download";

    if (fileType === "pptx") {
      typeLabel = "PowerPoint Presentation Slide Deck ready for briefing";
      icon = "&#128202;";
      btnText = "Download .pptx";
    } else if (fileType === "xlsx") {
      typeLabel = "Structured Excel Spreadsheet with styled tables";
      icon = "&#128200;";
      btnText = "Download .xlsx";
    } else if (fileType === "csv") {
      typeLabel = "Raw Tabular Dataset for data science & analytics";
      icon = "&#128203;";
      btnText = "Download .csv";
    } else {
      typeLabel = "Official Word Document (.docx) formatted for formal review";
      icon = "&#128196;";
      btnText = "Download .docx";
    }

    html += `
      <div class="chat-deliverable-card">
        <div class="chat-deliverable-info">
          <span class="chat-deliverable-icon">${icon}</span>
          <div>
            <div><strong>${escapeHtml(docName)}</strong></div>
            <div style="font-size:11px;color:var(--text-dim);">${escapeHtml(typeLabel)}</div>
          </div>
        </div>
        <a class="chat-deliverable-btn" href="${escapeHtml(dlUrl)}" download="${escapeHtml(docName)}">
          &#11015; ${escapeHtml(btnText)}
        </a>
      </div>
    `;
  }
  return html;
}

function renderAttachPreview() {
  const prev = document.getElementById("attachPreview");
  if (!chatAttachments.length) {
    prev.classList.add("panel-hidden");
    prev.innerHTML = "";
    return;
  }
  prev.classList.remove("panel-hidden");
  prev.innerHTML = chatAttachments.map((file, idx) =>
    `<div class="attach-chip" title="${escapeHtml(file.name)}">` +
      `<span>${getFileIcon(file.name)} ${escapeHtml(file.name)}</span>` +
      `<button type="button" onclick="removeChatAttachment(${idx})" title="Remove attachment">&times;</button>` +
    `</div>`
  ).join("");
}

function renderDeliverableActionsToolbar(msgId) {
  return `
    <div class="deliverable-actions">
      <button class="deliverable-btn" onclick="copyMessageText('${msgId}', this)" title="Copy deliverable text to clipboard">
        &#128203; Copy Deliverable Text
      </button>
      <button class="deliverable-btn" onclick="exportMessageMarkdown('${msgId}')" title="Export deliverable as markdown (.md) file">
        &#128229; Export .md
      </button>
    </div>
  `;
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message && !chatAttachments.length) return;

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;

  const filesToSend = [...chatAttachments];
  let userBubbleHtml = "";
  if (filesToSend.length > 0) {
    userBubbleHtml += '<div class="msg-attachments">' +
      filesToSend.map(f => '<div class="msg-attachment">' + getFileIcon(f.name) + ' ' + escapeHtml(f.name) + '</div>').join("") +
      '</div>';
  }
  if (message) {
    userBubbleHtml += '<div class="msg-text">' + escapeHtml(message) + '</div>';
  } else {
    userBubbleHtml += '<div class="msg-text" style="color:var(--text-dim);font-style:italic;">Analyze attached document(s)</div>';
  }

  addMessageBubble("user", userBubbleHtml);
  input.value = "";
  autoResize(input);
  clearChatAttachments();

  const thinking = addMessageBubble("assistant", '<span class="thinking">thinking&hellip;</span>');

  try {
    const form = new FormData();
    form.append("message", message || "Please analyze and summarize the attached document(s).");
    if (currentSessionId) form.append("session_id", currentSessionId);
    if (activeAgent && activeAgent.id) form.append("agent_id", activeAgent.id);
    for (const f of filesToSend) {
      form.append("files", f);
    }

    const res = await fetch(API + "/api/chat", { method: "POST", body: form, headers: getAuthHeaders() });
    const rawText = await res.text();
    if (!res.ok) throw new Error("Server returned an error: " + rawText.slice(0, 300));

    const data = JSON.parse(rawText);
    currentSessionId = data.session_id;

    const agentTag = (data.agent && data.agent.name)
      ? '<span class="tag" style="background:rgba(78,201,176,0.18);color:#4ec9b0;border-color:rgba(78,201,176,0.4);">🤖 ' + escapeHtml(data.agent.name) + '</span>'
      : '';
    const sourceTag = data.source === "model"
      ? '<span class="tag tag-ok">local model</span>'
      : '<span class="tag">stub mode</span>';
    const groundedTag = data.grounded
      ? '<span class="tag tag-ok">grounded</span>' : "";

    const msgId = data.message_id || `msg_${Date.now()}`;
    const formattedText = formatDeliverableMarkdown(data.reply, msgId);
    const deliverablesHtml = renderDeliverablesHtml(data.code_result, data.doc_result, msgId, data.findings);
    const actionsToolbar = renderDeliverableActionsToolbar(msgId);

    thinking.querySelector(".msg-body").innerHTML =
      '<div class="msg-text">' + formattedText + "</div>" +
      deliverablesHtml +
      actionsToolbar +
      '<div class="msg-tags">' + agentTag + sourceTag + groundedTag + "</div>";

    await refreshLogs();
    await loadHistory();
    const titleText = message || (filesToSend.length > 0 ? filesToSend[0].name : "Chat");
    document.getElementById("chatTitle").textContent =
      titleText.length > 50 ? titleText.slice(0, 50) + "…" : titleText;
  } catch (err) {
    console.error(err);
    thinking.querySelector(".msg-body").innerHTML =
      '<div class="msg-error">Something went wrong: ' + escapeHtml(err.message) + "</div>";
  } finally {
    sendBtn.disabled = false;
  }
}

/* ---------------------------------------------------------------- */
/* Session history                                                   */
/* ---------------------------------------------------------------- */
function quickPrompt(text) {
  const input = document.getElementById("chatInput");
  input.value = text;
  input.focus();
  autoResize(input);
}

function startNewChat() {
  currentSessionId = null;
  clearChatAttachments();
  document.getElementById("chatTitle").textContent = "New chat";
  document.getElementById("chatMessages").innerHTML =
    '<div class="empty-state" id="emptyState">' +
    '<h2>UrjaKavach Sovereign AI</h2>' +
    '<p>Unified on-premise workbench. Chat, attach any document or code, or execute scripts in an isolated sandbox.</p>' +
    '<div class="prompt-chips">' +
    '<button class="chip" onclick="quickPrompt(\'Summarize the attached document and extract key highlights.\')">&#128196; Summarize document</button>' +
    '<button class="chip" onclick="quickPrompt(\'Write a python script to calculate the moving average of pipeline pressure readings.\')">&#9889; Write &amp; run Python script</button>' +
    '<button class="chip" onclick="quickPrompt(\'Please generate a PowerPoint presentation (.pptx) summarizing the key findings.\')">&#128202; Generate PowerPoint (.pptx)</button>' +
    '<button class="chip" onclick="quickPrompt(\'Please structure these findings into an Excel spreadsheet (.xlsx) with status columns.\')">&#128200; Export Excel sheet (.xlsx)</button>' +
    '<button class="chip" onclick="quickPrompt(\'Export this data table as a CSV dataset (.csv).\')">&#128203; Export CSV (.csv)</button>' +
    '<button class="chip" onclick="quickPrompt(\'Please draft an official approval note (.docx) from the attached inspection data.\')">&#128221; Draft approval note (.docx)</button>' +
    '</div></div>';
  document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
}

function bucketLabel(createdAtSeconds) {
  const now = new Date();
  const d = new Date(createdAtSeconds * 1000);
  const startOfDay = dt => new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
  const dayDiff = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);

  if (dayDiff <= 0) return "Today";
  if (dayDiff === 1) return "Yesterday";
  if (dayDiff <= 7) return "Last 7 days";
  return "Older";
}

function relativeTime(createdAtSeconds) {
  const diffMs = Date.now() - createdAtSeconds * 1000;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + "m ago";
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + "h ago";
  return Math.floor(hrs / 24) + "d ago";
}

async function loadHistory() {
  try {
    const res = await fetch(API + "/api/chat/sessions", { headers: getAuthHeaders() });
    const data = await res.json();
    const list = document.getElementById("historyList");

    if (!data.sessions || !data.sessions.length) {
      list.innerHTML = '<div class="history-empty">No chats yet</div>';
      return;
    }

    const order = ["Today", "Yesterday", "Last 7 days", "Older"];
    const groups = {};
    data.sessions.forEach(s => {
      const label = bucketLabel(s.created_at);
      (groups[label] = groups[label] || []).push(s);
    });

    let html = "";
    order.forEach(label => {
      const items = groups[label];
      if (!items || !items.length) return;
      html += '<div class="history-group-label">' + label + "</div>";
      html += items.map(s =>
        '<div class="history-item' + (s.id === currentSessionId ? " active" : "") +
        '" onclick="openSession(\'' + s.id + '\')">' +
          '<span class="hi-title">' + escapeHtml(s.title) + "</span>" +
          '<span class="hi-time">' + relativeTime(s.created_at) + "</span>" +
        "</div>"
      ).join("");
    });

    list.innerHTML = html;
  } catch (e) {
    console.error("history load failed", e);
  }
}

async function openSession(sessionId) {
  try {
    const res = await fetch(API + "/api/chat/sessions/" + sessionId, { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();

    currentSessionId = sessionId;
    document.getElementById("chatTitle").textContent = data.title || "Chat";

    const container = document.getElementById("chatMessages");
    container.innerHTML = "";
    data.messages.forEach(m => {
      let bubbleHtml = "";
      const docList = (m.documents && m.documents.length) ? m.documents : (m.document && m.document.filename ? [m.document] : []);
      if (docList.length > 0) {
        bubbleHtml += '<div class="msg-attachments">' +
          docList.map(d => '<div class="msg-attachment">' + getFileIcon(d.filename) + ' ' + escapeHtml(d.filename) + '</div>').join("") +
          '</div>';
      }
      const msgId = m.message_id || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`;
      const isAssistant = m.role === "assistant";
      let contentHtml = "";
      if (isAssistant) {
        contentHtml = formatDeliverableMarkdown(m.content || "", msgId);
      } else {
        contentHtml = escapeHtml(m.prompt || m.content || "");
      }
      const deliverablesHtml = renderDeliverablesHtml(m.code_result, m.doc_result, msgId, m.findings);
      const actionsToolbar = isAssistant ? renderDeliverableActionsToolbar(msgId) : "";

      bubbleHtml += '<div class="msg-text">' + contentHtml + '</div>' + deliverablesHtml + actionsToolbar;
      if (isAssistant && (m.source || m.grounded)) {
        const sourceTag = m.source === "model"
          ? '<span class="tag tag-ok">local model</span>'
          : '<span class="tag">stub mode</span>';
        const groundedTag = m.grounded ? '<span class="tag tag-ok">grounded</span>' : '';
        bubbleHtml += '<div class="msg-tags">' + sourceTag + groundedTag + '</div>';
      }
      addMessageBubble(isAssistant ? "assistant" : "user", bubbleHtml);
    });

    document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
    await loadHistory();
    await refreshLogs();
  } catch (e) {
    console.error("open session failed", e);
  }
}

/* ---------------------------------------------------------------- */
/* Document flow (modal)                                             */
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

async function runDocFlow() {
  const btn = document.getElementById("runDoc");
  btn.disabled = true;
  btn.textContent = "Running…";

  let res, rawText;
  try {
    const form = new FormData();
    const useSample = document.getElementById("useSampleToggle").checked;
    form.append("use_sample", useSample ? "true" : "false");
    if (currentSessionId) form.append("session_id", currentSessionId);
    if (!useSample && uploadedFile) form.append("file", uploadedFile);

    res = await fetch(API + "/api/tasks/document", { method: "POST", body: form, headers: getAuthHeaders() });
    rawText = await res.text();
    if (!res.ok) throw new Error("Server returned an error");
    const data = JSON.parse(rawText);
    currentSessionId = data.session_id;
    await refreshLogs();

    const groundedTag = data.grounded
      ? '<span class="tag tag-ok">grounded on plant docs</span>'
      : '<span class="tag">no KB grounding</span>';
    const sourceTag = data.source === "model"
      ? '<span class="tag tag-ok">local model</span>'
      : '<span class="tag">stub mode</span>';

    closeModal("docModal");
    addMessageBubble("user", "Run Document Flow");
    addMessageBubble("assistant",
      '<div class="result-heading">Key Findings ' + sourceTag + groundedTag + "</div>" +
      '<ul class="findings">' + data.findings.map(f => "<li>" + escapeHtml(f) + "</li>").join("") + "</ul>" +
      '<a class="download-link" href="' + API + "/api/outputs/" + data.output_file +
        '" target="_blank">Download ' + escapeHtml(data.output_file) + "</a>"
    );
  } catch (err) {
    console.error(err);
    closeModal("docModal");
    addMessageBubble("assistant", '<div class="msg-error">' + escapeHtml(err.message) + "</div>");
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Document Flow";
  }
}

/* ---------------------------------------------------------------- */
/* Code flow (modal)                                                 */
/* ---------------------------------------------------------------- */
async function runCodeFlow() {
  const btn = document.getElementById("runCode");
  btn.disabled = true;
  btn.textContent = "Running…";

  const prompt = document.getElementById("codePrompt").value;
  let res, rawText;
  try {
    const form = new FormData();
    form.append("prompt", prompt);

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

    closeModal("codeModal");
    addMessageBubble("user", escapeHtml(prompt));
    addMessageBubble("assistant",
      '<div class="result-heading">Generated Code ' + sourceTag + "</div>" +
      '<div class="code-block"><div class="cb-header"><span>generated.py</span><span>code model</span></div>' +
        "<pre>" + escapeHtml(data.code) + "</pre></div>" +
      '<div class="result-heading">Sandbox Output — ' + okBadge + "</div>" +
      '<div class="code-block"><div class="cb-header"><span>stdout</span><span>isolated subprocess</span></div>' +
        "<pre>" + escapeHtml(data.result.stdout || data.result.stderr || "(no output)") + "</pre></div>"
    );
  } catch (err) {
    console.error(err);
    closeModal("codeModal");
    addMessageBubble("assistant", '<div class="msg-error">' + escapeHtml(err.message) + "</div>");
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Code Flow";
  }
}

/* ---------------------------------------------------------------- */
/* Health check + history on load                                    */
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
    document.getElementById("healthLine").textContent = "backend not reachable";
  }
})();

loadHistory();

/* ---------------------------------------------------------------- */
/* Agent Hub & Onboarder Logic                                      */
/* ---------------------------------------------------------------- */
let activeAgent = null;
let allAgentsList = [];
let allUseCasesList = [];
let allRegisteredTools = [];
let selectedUseCaseFilter = null;
let agentSearchTimeout = null;

async function initAgentHub() {
  try {
    const [agentsRes, toolsRes] = await Promise.all([
      fetch(API + "/api/agents", { headers: getAuthHeaders() }),
      fetch(API + "/api/tools", { headers: getAuthHeaders() })
    ]);

    if (agentsRes.ok) {
      const aData = await agentsRes.json();
      allAgentsList = aData.agents || [];
      allUseCasesList = aData.use_cases || [];
    }

    if (toolsRes.ok) {
      const tData = await toolsRes.json();
      allRegisteredTools = tData.tools || [];
      renderToolsChecklist(allRegisteredTools);
    }

    // Default to general engineering agent if available, or first agent
    if (!activeAgent && allAgentsList.length > 0) {
      const defaultAgent = allAgentsList.find(a => a.id === "agent_general") || allAgentsList[0];
      selectAgent(defaultAgent.id, false);
    }

    renderUseCaseChips();
    renderAgentGrid(allAgentsList);
  } catch (err) {
    console.warn("Failed to initialize Agent Hub:", err);
  }
}

function switchAgentTab(tabName) {
  const isDiscover = tabName === 'discover';
  document.getElementById('tabDiscover').classList.toggle('panel-hidden', !isDiscover);
  document.getElementById('tabOnboard').classList.toggle('panel-hidden', isDiscover);
  document.getElementById('tabDiscoverBtn').classList.toggle('active', isDiscover);
  document.getElementById('tabOnboardBtn').classList.toggle('active', !isDiscover);
}

function renderUseCaseChips() {
  const container = document.getElementById("useCaseChipsRow");
  if (!container) return;

  let html = '<button class="use-case-chip ' + (!selectedUseCaseFilter ? 'active' : '') + '" onclick="filterByUseCase(null)">All Use Cases</button>';
  for (const uc of allUseCasesList) {
    const isAct = selectedUseCaseFilter === uc.use_case_id;
    html += `<button class="use-case-chip ${isAct ? 'active' : ''}" onclick="filterByUseCase('${escapeHtml(uc.use_case_id)}')">${escapeHtml(uc.title)} (${uc.agent_count})</button>`;
  }
  container.innerHTML = html;
}

function renderAgentGrid(agents, searchResults = null) {
  const grid = document.getElementById("agentsGrid");
  if (!grid) return;

  if (!agents || agents.length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--text-dim);">' +
      'No specialized agents found for this use case. <br><button class="btn-primary" style="margin-top:10px;" onclick="switchAgentTab(\'onboard\')">➕ Onboard New Agent</button>' +
      '</div>';
    return;
  }

  let html = "";
  for (const ag of agents) {
    const isCurrent = activeAgent && activeAgent.id === ag.id;
    const badgeClass = ag.is_builtin ? "agent-badge builtin" : "agent-badge";
    const badgeLabel = ag.is_builtin ? "Standard PSU" : "Custom Onboarded";
    
    // Tools list
    const toolBadges = (ag.tool_ids || []).map(t => `<span class="agent-tool-tag">${escapeHtml(t.replace('_', ' '))}</span>`).join("");
    
    // Use case tags
    const ucTags = (ag.use_case_ids || []).slice(0, 3).map(u => `<span class="agent-tag">${escapeHtml(u.replace('_', ' '))}</span>`).join("");

    // Score if search result
    let scoreHtml = "";
    if (searchResults && searchResults[ag.id]) {
      const matchData = searchResults[ag.id];
      scoreHtml = `<span class="agent-match-score">★ Match ${matchData.score}</span>`;
    }

    html += `
      <div class="agent-card">
        <div>
          <div class="agent-card-header">
            <div>
              <div class="agent-card-title">${escapeHtml(ag.name)}</div>
              <div class="agent-card-dept">${escapeHtml(ag.department || 'Engineering')}</div>
            </div>
            <span class="${badgeClass}">${badgeLabel}</span>
          </div>
          <div class="agent-card-desc">${escapeHtml(ag.description)}</div>
          <div class="agent-card-tags">
            ${ucTags}
            ${toolBadges}
          </div>
        </div>
        <div class="agent-card-footer">
          ${scoreHtml || '<span style="font-size:11px;color:var(--text-dim);">' + (ag.model_type || 'reasoning') + ' model</span>'}
          <button class="btn-launch-agent ${isCurrent ? 'active-agent-btn' : ''}" onclick="selectAgent('${ag.id}', true)">
            ${isCurrent ? '✓ Active Agent' : 'Launch Agent ⚡'}
          </button>
        </div>
      </div>
    `;
  }
  grid.innerHTML = html;
}

function debounceAgentSearch() {
  clearTimeout(agentSearchTimeout);
  agentSearchTimeout = setTimeout(() => {
    searchAgentsAction();
  }, 300);
}

async function searchAgentsAction() {
  const query = (document.getElementById("agentSearchInput").value || "").trim();
  if (!query) {
    filterByUseCase(selectedUseCaseFilter);
    return;
  }

  try {
    const res = await fetch(API + `/api/agents/search?q=${encodeURIComponent(query)}&limit=6`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error("Search failed");
    const data = await res.json();
    const results = data.results || [];
    
    const matchedAgents = [];
    const searchScoreMap = {};
    for (const r of results) {
      if (r.agent) {
        matchedAgents.push(r.agent);
        searchScoreMap[r.agent.id] = r;
      }
    }
    renderAgentGrid(matchedAgents, searchScoreMap);
  } catch (err) {
    console.error("Semantic search error:", err);
  }
}

function filterByUseCase(useCaseId) {
  selectedUseCaseFilter = useCaseId;
  renderUseCaseChips();

  if (!useCaseId) {
    renderAgentGrid(allAgentsList);
    return;
  }

  const filtered = allAgentsList.filter(ag => (ag.use_case_ids || []).includes(useCaseId));
  renderAgentGrid(filtered);
}

function selectAgent(agentId, closeModalAfter = true) {
  const ag = allAgentsList.find(a => a.id === agentId);
  if (!ag) return;

  activeAgent = ag;
  const pillName = document.getElementById("activeAgentName");
  if (pillName) pillName.textContent = ag.name;

  // Update prompt chips if empty state is visible
  const emptyState = document.getElementById("emptyState");
  if (emptyState && ag.starter_prompts && ag.starter_prompts.length > 0) {
    const chipsContainer = emptyState.querySelector(".prompt-chips");
    if (chipsContainer) {
      chipsContainer.innerHTML = ag.starter_prompts.map(p => 
        `<button class="chip" onclick="quickPrompt('${escapeHtml(p)}')">⚡ ${escapeHtml(p)}</button>`
      ).join("");
    }
  }

  // Update button states in grid
  renderAgentGrid(allAgentsList);

  if (closeModalAfter) {
    closeModal("agentHubModal");
  }
}

function renderToolsChecklist(tools, suggestedToolIds = []) {
  const container = document.getElementById("toolsChecklist");
  if (!container) return;

  let html = "";
  for (const t of tools) {
    const isSuggested = suggestedToolIds.includes(t.id);
    const isChecked = isSuggested || t.is_default;
    html += `
      <label class="tool-check-item">
        <input type="checkbox" name="onboard_tool" value="${t.id}" ${isChecked ? 'checked' : ''} />
        <div>
          <div class="tool-check-label">
            ${escapeHtml(t.name)}
            ${isSuggested ? '<span class="tool-suggested-tag">Suggested</span>' : ''}
          </div>
          <div class="tool-check-desc">${escapeHtml(t.description)}</div>
        </div>
      </label>
    `;
  }
  container.innerHTML = html;
}

let suggestToolsTimeout = null;
function onNewAgentInfoChange() {
  clearTimeout(suggestToolsTimeout);
  suggestToolsTimeout = setTimeout(async () => {
    const name = document.getElementById("newAgentName").value || "";
    const desc = document.getElementById("newAgentDesc").value || "";
    const intent = `${name} ${desc}`;
    if (intent.trim().length > 5) {
      try {
        const res = await fetch(API + `/api/tools/suggest?intent=${encodeURIComponent(intent)}`, {
          headers: getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          renderToolsChecklist(allRegisteredTools, data.suggested_tools || []);
        }
      } catch (e) {}
    }
  }, 400);
}

function onSkillFileChosen(event) {
  const file = event.target.files[0];
  if (!file) return;

  document.getElementById("skillFileNameHint").textContent = `Loaded: ${file.name} (${Math.round(file.size/1024)} KB)`;
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("newAgentSkill").value = e.target.result;
  };
  reader.readAsText(file);
}

async function draftSkillWithAi() {
  const name = (document.getElementById("newAgentName").value || "").trim();
  const desc = (document.getElementById("newAgentDesc").value || "").trim();
  const ucs = (document.getElementById("newAgentUseCases").value || "").trim();
  const prompt = (document.getElementById("newAgentPrompt").value || "").trim();

  if (!name) {
    alert("Please provide at least an Agent Role Name before drafting with AI.");
    document.getElementById("newAgentName").focus();
    return;
  }

  const draftBtn = document.getElementById("btnAiDraftSkill");
  const origText = draftBtn.textContent;
  draftBtn.disabled = true;
  draftBtn.textContent = "⏳ Drafting SKILL.md with Meta-Agent...";

  const useCaseList = ucs.split(",").map(s => s.trim()).filter(Boolean);

  try {
    const res = await fetch(API + "/api/agents/draft-skill", {
      method: "POST",
      headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({
        role_name: name,
        description: desc || name,
        use_cases: useCaseList,
        guidelines: prompt,
      })
    });

    if (!res.ok) throw new Error("Failed to draft skill");
    const data = await res.json();
    document.getElementById("newAgentSkill").value = data.skill_content || "";
    document.getElementById("skillFileNameHint").textContent = "✨ Drafted by AI Meta-Agent (Llama-3.2-3B)";
  } catch (err) {
    alert("Skill drafting error: " + err.message);
  } finally {
    draftBtn.disabled = false;
    draftBtn.textContent = origText;
  }
}

async function handleOnboardSubmit(event) {
  event.preventDefault();

  const name = document.getElementById("newAgentName").value.trim();
  const dept = document.getElementById("newAgentDept").value.trim();
  const desc = document.getElementById("newAgentDesc").value.trim();
  const ucs = document.getElementById("newAgentUseCases").value.trim();
  const prompt = document.getElementById("newAgentPrompt").value.trim();
  const skill = document.getElementById("newAgentSkill").value.trim();
  const model = document.getElementById("newAgentModel").value;

  const checkedBoxes = document.querySelectorAll('input[name="onboard_tool"]:checked');
  const toolIds = Array.from(checkedBoxes).map(cb => cb.value);

  const useCaseList = ucs.split(",").map(s => s.trim().toLowerCase().replace(/\s+/g, "_")).filter(Boolean);

  const payload = {
    name,
    department: dept || "Custom Operations",
    description: desc,
    use_case_ids: useCaseList,
    system_prompt: prompt,
    skill_content: skill,
    tool_ids: toolIds,
    model_type: model,
    starter_prompts: [
      `Analyze latest data using ${name}.`,
      `Generate a technical deliverable for ${useCaseList[0] || 'engineering'}.`
    ]
  };

  const submitBtn = document.getElementById("btnSubmitOnboard");
  submitBtn.disabled = true;
  submitBtn.textContent = "⏳ Onboarding Agent...";

  try {
    const res = await fetch(API + "/api/agents/onboard", {
      method: "POST",
      headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Failed to onboard agent");
    }

    const data = await res.json();
    const onboardedAgent = data.agent;

    // Refresh agent store lists
    await initAgentHub();

    // Launch newly created agent
    selectAgent(onboardedAgent.id, true);

    // Reset form and switch back to discover tab
    document.getElementById("onboardAgentForm").reset();
    switchAgentTab("discover");
    alert(`🎉 Successfully onboarded '${onboardedAgent.name}'! It is now active in your chat session.`);
  } catch (err) {
    alert("Onboarding failed: " + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Onboard & Launch Agent";
  }
}

// Initialize Agent Hub on load
initAgentHub();


