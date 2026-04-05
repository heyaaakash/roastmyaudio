const recordBtn = document.getElementById("recordBtn");
const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");
const livePreviewEl = document.getElementById("livePreview");
const modelSelectEl = document.getElementById("modelSelect");
const strictModeCheckbox = document.getElementById("strictModeCheckbox");
const historyListEl = document.getElementById("historyList");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");
const formattedViewBtn = document.getElementById("formattedViewBtn");
const rawViewBtn = document.getElementById("rawViewBtn");

const HISTORY_STORAGE_KEY = "whisper_web_mvp_history";
const MAX_HISTORY_ITEMS = 100;
const PREVIEW_WINDOW_MS = 2000;
const PREVIEW_MIN_CHUNK_MS = 450;
const PREVIEW_REQUEST_GAP_MS = 600;

let mediaRecorder = null;
let audioChunks = [];
let rollingChunks = [];
let stream = null;
let currentView = "formatted";
let lastTranscript = {
  formatted: "",
  raw: "",
};
let transcriptHistory = [];
let isRecording = false;
let previewInFlight = false;
let previewLastSentAt = 0;

function setLivePreview(text, muted = false) {
  livePreviewEl.textContent = text;
  livePreviewEl.classList.toggle("muted", muted);
}

function setStatus(message) {
  statusEl.textContent = message;
}

async function loadInstalledModels() {
  try {
    const response = await fetch("/models");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to fetch models");
    }

    const models = Array.isArray(data.models) ? data.models : [];
    modelSelectEl.innerHTML = "";

    if (models.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No installed models";
      modelSelectEl.appendChild(option);
      modelSelectEl.disabled = true;
      recordBtn.disabled = true;
      setStatus("No installed Whisper models found in local cache");
      return;
    }

    models.forEach((modelName) => {
      const option = document.createElement("option");
      option.value = modelName;
      option.textContent = modelName;
      modelSelectEl.appendChild(option);
    });

    const defaultModel = data.default_model || models[0];
    modelSelectEl.value = models.includes(defaultModel) ? defaultModel : models[0];
  } catch (error) {
    setStatus(`Model load failed: ${error.message}`);
  }
}

function renderTranscript() {
  transcriptEl.value = currentView === "raw" ? lastTranscript.raw : lastTranscript.formatted;
}

function saveHistory() {
  localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(transcriptHistory));
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    transcriptHistory = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(transcriptHistory)) {
      transcriptHistory = [];
    }
  } catch {
    transcriptHistory = [];
  }
}

function formatTimestamp(isoString) {
  const date = isoString ? new Date(isoString) : new Date();
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString();
}

function renderHistory() {
  historyListEl.innerHTML = "";

  if (transcriptHistory.length === 0) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "No transcriptions yet.";
    historyListEl.appendChild(empty);
    return;
  }

  transcriptHistory.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "history-item";

    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.textContent = `${formatTimestamp(entry.timestamp)}${entry.model ? ` | ${entry.model}` : ""}`;

    const text = document.createElement("div");
    text.className = "history-text";
    text.textContent = currentView === "raw" ? entry.raw || "" : entry.formatted || "";

    item.appendChild(meta);
    item.appendChild(text);
    historyListEl.appendChild(item);
  });
}

function addHistoryEntry(entry) {
  transcriptHistory.unshift(entry);
  if (transcriptHistory.length > MAX_HISTORY_ITEMS) {
    transcriptHistory = transcriptHistory.slice(0, MAX_HISTORY_ITEMS);
  }
  saveHistory();
  renderHistory();
}

function setView(view) {
  currentView = view;
  formattedViewBtn.classList.toggle("active", view === "formatted");
  rawViewBtn.classList.toggle("active", view === "raw");
  renderTranscript();
  renderHistory();
}

async function startRecording() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    rollingChunks = [];
    isRecording = true;
    previewInFlight = false;
    previewLastSentAt = 0;
    setLivePreview("Listening...", true);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
        rollingChunks.push({ blob: event.data, ts: performance.now() });
        maybeSendPreview();
      }
    };

    mediaRecorder.onstop = async () => {
      isRecording = false;
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      await transcribeAudio(audioBlob);
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };

    mediaRecorder.start(300);
    recordBtn.textContent = "Stop Recording";
    recordBtn.classList.add("recording");
    setStatus("Recording with live preview...");
  } catch (error) {
    setStatus(`Mic access failed: ${error.message}`);
  }
}

function stopRecording() {
  if (!mediaRecorder) return;
  mediaRecorder.stop();
  recordBtn.textContent = "Start Recording";
  recordBtn.classList.remove("recording");
  setStatus("Uploading and transcribing...");
  setLivePreview("Finalizing transcript...", true);
}

function buildPreviewBlob() {
  const now = performance.now();
  rollingChunks = rollingChunks.filter((chunk) => now - chunk.ts <= PREVIEW_WINDOW_MS);
  if (rollingChunks.length === 0) return null;

  const oldest = rollingChunks[0];
  if (!oldest) return null;
  if (now - oldest.ts < PREVIEW_MIN_CHUNK_MS) return null;

  const blobs = rollingChunks.map((chunk) => chunk.blob);
  return new Blob(blobs, { type: "audio/webm" });
}

async function maybeSendPreview() {
  if (!isRecording || previewInFlight) return;

  const now = performance.now();
  if (now - previewLastSentAt < PREVIEW_REQUEST_GAP_MS) return;

  const previewBlob = buildPreviewBlob();
  if (!previewBlob) return;

  previewInFlight = true;
  previewLastSentAt = now;

  const formData = new FormData();
  formData.append("audio", previewBlob, "preview.webm");
  formData.append("model", modelSelectEl.value || "");

  try {
    const response = await fetch("/transcribe_partial", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Live preview failed");
    }

    const previewText = (data.preview_text || "").trim();
    if (previewText) {
      setLivePreview(previewText);
    }
  } catch {
    // Keep recording responsive even if preview requests fail.
  } finally {
    previewInFlight = false;
  }
}

async function transcribeAudio(audioBlob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  formData.append("model", modelSelectEl.value || "");
  formData.append("strict_mode", strictModeCheckbox.checked ? "true" : "false");

  try {
    const response = await fetch("/transcribe", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Unknown server error");
    }

    lastTranscript = {
      formatted: data.text || "",
      raw: data.raw_text || data.text || "",
    };
    renderTranscript();

    addHistoryEntry({
      timestamp: data.transcribed_at_utc || new Date().toISOString(),
      model: data.model_used || modelSelectEl.value || "",
      formatted: data.text || "",
      raw: data.raw_text || data.text || "",
    });

    const formatterMs = Number.isFinite(data.formatter_ms) ? ` (format ${data.formatter_ms} ms)` : "";
    const modelUsed = data.model_used ? ` using ${data.model_used}` : "";
    setStatus(`Done${modelUsed}${formatterMs}`);
    setLivePreview("Waiting for speech...", true);
  } catch (error) {
    setStatus(`Transcription failed: ${error.message}`);
    setLivePreview("Live preview unavailable.", true);
  }
}

recordBtn.addEventListener("click", () => {
  if (!mediaRecorder || mediaRecorder.state === "inactive") {
    startRecording();
  } else {
    stopRecording();
  }
});

formattedViewBtn.addEventListener("click", () => setView("formatted"));
rawViewBtn.addEventListener("click", () => setView("raw"));

clearHistoryBtn.addEventListener("click", () => {
  transcriptHistory = [];
  saveHistory();
  renderHistory();
});

loadHistory();
renderHistory();
setLivePreview("Waiting for speech...", true);

loadInstalledModels();
