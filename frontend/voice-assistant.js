/*
 * MRPL Voice Assistant — self-contained widget.
 * Owns its own recording/animation state; talks to the rest of the app
 * through two small, explicit seams already exposed by app.js:
 *   - window.pendingVoiceLanguage : set before calling sendChatMessage()
 *     so the backend replies in the detected language.
 *   - "uk:chat-reply" / "uk:chat-reply-error" document events : fired by
 *     sendChatMessage() once the (existing, unmodified) chat flow
 *     finishes, so this widget knows when to leave the "processing"
 *     state and start speaking the reply.
 *
 * No other file needs to change to add or remove this widget.
 */
(function () {
  "use strict";

  const overlay = document.getElementById("mrplVaOverlay");
  const statusEl = document.getElementById("mrplVaStatus");
  const glowEl = document.getElementById("mrplVaGlow");
  const micBtn = document.getElementById("vaMicBtn");

  if (!overlay || !statusEl || !glowEl) {
    console.warn("MRPL voice assistant: overlay markup missing, widget disabled.");
    return;
  }

  let state = "idle"; // idle | listening | processing
  let stream = null;
  let recorder = null;
  let chunks = [];
  let audioCtx = null;
  let analyser = null;
  let levelRafId = null;
  let awaitingReply = false;

  function setState(next) {
    state = next;
    overlay.classList.toggle("panel-hidden", next === "idle");
    overlay.setAttribute("aria-hidden", next === "idle" ? "true" : "false");
    overlay.classList.toggle("state-listening", next === "listening");
    overlay.classList.toggle("state-processing", next === "processing");
    if (next === "listening") statusEl.textContent = "MRPL is listening…";
    if (next === "processing") statusEl.textContent = "Thinking…";
  }

  function stopLevelMeter() {
    if (levelRafId) {
      cancelAnimationFrame(levelRafId);
      levelRafId = null;
    }
    glowEl.style.setProperty("--mrpl-va-level", "0");
  }

  function stopStream() {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    if (audioCtx) {
      audioCtx.close().catch(() => {});
      audioCtx = null;
      analyser = null;
    }
  }

  function startLevelMeter() {
    const data = new Uint8Array(analyser.frequencyBinCount);
    const loop = () => {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) {
        const centered = (data[i] - 128) / 128;
        sumSquares += centered * centered;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      const level = Math.min(1, rms * 4); // amplify quiet mics into a visible range
      glowEl.style.setProperty("--mrpl-va-level", level.toFixed(3));
      levelRafId = requestAnimationFrame(loop);
    };
    loop();
  }

  async function start() {
    if (state !== "idle") return;

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      alert("Microphone access is required for voice input.");
      return;
    }

    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    audioCtx.createMediaStreamSource(stream).connect(analyser);

    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = onRecordingStopped;

    recorder.start();
    setState("listening");
    startLevelMeter();
  }

  function stop() {
    if (state !== "listening") return;
    stopLevelMeter();
    if (recorder && recorder.state !== "inactive") {
      recorder.stop(); // onRecordingStopped continues the flow
    }
  }

  function cancel() {
    if (state === "idle") return;
    stopLevelMeter();
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null; // discard - don't transcribe
      recorder.stop();
    }
    stopStream();
    awaitingReply = false;
    setState("idle");
  }

  function toggle() {
    if (state === "idle") start();
    else if (state === "listening") stop();
    // no-op while "processing" - let it finish
  }

  async function onRecordingStopped() {
    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    stopStream();

    if (blob.size === 0) {
      setState("idle");
      return;
    }

    setState("processing");

    try {
      const form = new FormData();
      form.append("audio", blob, "voice.webm");
      const headers = window.getAuthHeaders ? window.getAuthHeaders() : {};
      const res = await fetch((window.API || "") + "/api/transcribe", {
        method: "POST",
        body: form,
        headers,
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const errBody = await res.json();
          if (errBody && errBody.detail) detail = errBody.detail;
        } catch (_) {
          // response wasn't JSON - keep the HTTP status as the detail
        }
        throw new Error(detail);
      }
      const data = await res.json();

      if (!data.text || !data.text.trim()) {
        setState("idle");
        return;
      }

      const chatInput = document.getElementById("chatInput");
      if (!chatInput || typeof window.sendChatMessage !== "function") {
        setState("idle");
        return;
      }

      chatInput.value = data.text;
      if (typeof window.autoResize === "function") window.autoResize(chatInput);

      window.pendingVoiceLanguage = data.detected_language || "en";
      awaitingReply = true;
      window.sendChatMessage(); // same send path typed messages use; stays in "processing" until it replies
    } catch (err) {
      console.error(err);
      setState("idle");
      alert("Voice transcription failed: " + err.message);
    }
  }

  async function speak(text, language) {
    if (!text || !language) return;
    try {
      const headers = Object.assign(
        { "Content-Type": "application/json" },
        window.getAuthHeaders ? window.getAuthHeaders() : {}
      );
      const res = await fetch((window.API || "") + "/api/synthesize", {
        method: "POST",
        headers,
        body: JSON.stringify({ text, language }),
      });
      if (!res.ok) throw new Error("Synthesis failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      if (micBtn) micBtn.classList.add("mrpl-va-speaking");
      audio.onended = audio.onerror = () => {
        URL.revokeObjectURL(url);
        if (micBtn) micBtn.classList.remove("mrpl-va-speaking");
      };
      await audio.play();
    } catch (err) {
      console.error("MRPL voice assistant: speech synthesis failed", err);
    }
  }

  document.addEventListener("uk:chat-reply", (e) => {
    if (!awaitingReply) return;
    awaitingReply = false;
    setState("idle");
    const { reply, detectedLanguage } = e.detail || {};
    if (detectedLanguage) speak(reply, detectedLanguage);
  });

  document.addEventListener("uk:chat-reply-error", () => {
    if (!awaitingReply) return;
    awaitingReply = false;
    setState("idle");
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state !== "idle") cancel();
  });

  window.mrplVoiceAssistant = { start, stop, cancel, toggle };
})();
