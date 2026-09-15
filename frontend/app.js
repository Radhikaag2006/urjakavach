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
let chatAttachment = null;    // for the chat input's attach button
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
  document.getElementById("activityPanel").classList.toggle("open");
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
  const file = evt.target.files[0];
  if (!file) return;
  chatAttachment = file;
  const prev = document.getElementById("attachPreview");
  prev.classList.remove("panel-hidden");
  prev.innerHTML =
    '<span>&#128206; ' + escapeHtml(file.name) + '</span>' +
    '<button onclick="clearChatAttachment()">&times;</button>';
}

function clearChatAttachment() {
  chatAttachment = null;
  document.getElementById("chatFileInput").value = "";
  const prev = document.getElementById("attachPreview");
  prev.classList.add("panel-hidden");
  prev.innerHTML = "";
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;

  addMessageBubble("user", escapeHtml(message));
  input.value = "";
  autoResize(input);

  const thinking = addMessageBubble("assistant", '<span class="thinking">thinking&hellip;</span>');

  try {
    const form = new FormData();
    form.append("message", message);
    if (currentSessionId) form.append("session_id", currentSessionId);
    if (chatAttachment) form.append("file", chatAttachment);

    const res = await fetch(API + "/api/chat", { method: "POST", body: form, headers: getAuthHeaders() });
    const rawText = await res.text();
    if (!res.ok) throw new Error("Server returned an error: " + rawText.slice(0, 300));

    const data = JSON.parse(rawText);
    currentSessionId = data.session_id;

    const sourceTag = data.source === "model"
      ? '<span class="tag tag-ok">local model</span>'
      : '<span class="tag">stub mode</span>';
    const groundedTag = data.grounded
      ? '<span class="tag tag-ok">grounded</span>' : "";

    thinking.querySelector(".msg-body").innerHTML =
      '<div class="msg-text">' + escapeHtml(data.reply) + "</div>" +
      '<div class="msg-tags">' + sourceTag + groundedTag + "</div>";

    clearChatAttachment();
    await refreshLogs();
    await loadHistory();
    document.getElementById("chatTitle").textContent =
      message.length > 50 ? message.slice(0, 50) + "…" : message;
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
function startNewChat() {
  currentSessionId = null;
  chatAttachment = null;
  document.getElementById("chatTitle").textContent = "New chat";
  document.getElementById("chatMessages").innerHTML =
    '<div class="empty-state" id="emptyState"><h2>UrjaKavach</h2>' +
    "<p>Sovereign on-premise AI workbench for MRPL. Ask a question, upload a " +
    "document or image, or run a demo flow from the sidebar. Nothing leaves " +
    "this machine.</p></div>";
  clearChatAttachment();
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
      addMessageBubble(
        m.role === "user" ? "user" : "assistant",
        '<div class="msg-text">' + escapeHtml(m.content) + "</div>"
      );
    });

    document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
    await loadHistory();
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

    res = await fetch(API + "/api/tasks/document", { method: "POST", body: form });
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

