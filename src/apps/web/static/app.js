/**
 * RoastMyAudio Flow Dashboard Client Application
 * Handles timeline rendering, audio playback, retry cleanup,
 * re-transcriptions, style transforms, and live voice recording.
 */

// State
let currentAudio = null;
let currentPlayingId = null;
let activeRetranscribeId = null;
let searchTimeout = null;
let mediaRecorder = null;
let recordedChunks = [];
let recTimerInterval = null;
let recStartTime = 0;
let latestKnownRecordingId = null;
let latestKnownCount = 0;
let autoSyncInterval = null;

// Elements
const sidebar = document.getElementById("sidebar");
const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
const timelineList = document.getElementById("timelineList");
const timelineSearchInput = document.getElementById("timelineSearchInput");
const retranscribeModal = document.getElementById("retranscribeModal");
const toastContainer = document.getElementById("toastContainer");

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupSidebarToggle();
  setupSearch();
  setupLiveRecording();
  setupDictionary();
  setupSettings();
  loadStats();
  loadTimeline();
  startAutoSync();
});

// ---------------------------------------------------------------------------
// Real-time Background Auto-Sync (Live Dashboard Updates)
// ---------------------------------------------------------------------------
function startAutoSync() {
  if (autoSyncInterval) clearInterval(autoSyncInterval);
  autoSyncInterval = setInterval(async () => {
    // Only auto-sync if not currently searching or actively recording
    if (timelineSearchInput && timelineSearchInput.value.trim().length > 0) return;
    if (mediaRecorder && mediaRecorder.state === "recording") return;

    try {
      const res = await fetch("/api/history?limit=1");
      if (!res.ok) return;
      const data = await res.json();
      const recs = data.recordings || [];
      const total = data.total || 0;
      const topId = recs.length > 0 ? recs[0].id : null;

      if (topId && latestKnownRecordingId && (topId !== latestKnownRecordingId || total !== latestKnownCount)) {
        latestKnownRecordingId = topId;
        latestKnownCount = total;
        // Auto-refresh timeline & statistics in background
        await loadTimeline();
        loadStats();
      } else if (!latestKnownRecordingId && topId) {
        latestKnownRecordingId = topId;
        latestKnownCount = total;
      }
    } catch (e) {
      // Ignore background fetch interruptions
    }
  }, 1500);
}

// ---------------------------------------------------------------------------
// Toast notification helper
// ---------------------------------------------------------------------------
function showToast(message, duration = 3000) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

// ---------------------------------------------------------------------------
// Navigation / Tabs
// ---------------------------------------------------------------------------
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item, [data-tab]");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tabName = item.getAttribute("data-tab");
      if (!tabName) return;

      // Update sidebar active class
      document.querySelectorAll(".sidebar-nav .nav-item").forEach(n => n.classList.remove("active"));
      const sidebarNavMatch = document.querySelector(`.sidebar-nav .nav-item[data-tab="${tabName}"]`);
      if (sidebarNavMatch) sidebarNavMatch.classList.add("active");

      // Update active tab-view
      document.querySelectorAll(".tab-view").forEach(view => view.classList.remove("active"));
      const targetView = document.getElementById(`tab-${tabName}`);
      if (targetView) targetView.classList.add("active");

      if (tabName === "dictionary") loadDictionary();
      if (tabName === "insights") loadStats();
      if (tabName === "dictation") loadTimeline();
    });
  });

  // Hero "Start now" button
  const startStyleBtn = document.getElementById("startStyleBannerBtn");
  if (startStyleBtn) {
    startStyleBtn.addEventListener("click", () => {
      const styleTab = document.querySelector(`.nav-item[data-tab="style"]`);
      if (styleTab) styleTab.click();
    });
  }

  // Voice profile close button
  const closeVoiceProfile = document.getElementById("closeVoiceProfileBtn");
  if (closeVoiceProfile) {
    closeVoiceProfile.addEventListener("click", () => {
      const box = document.getElementById("voiceProfileBox");
      if (box) box.style.display = "none";
    });
  }

  // Create report button
  const createReportBtn = document.getElementById("createReportBtn");
  if (createReportBtn) {
    createReportBtn.addEventListener("click", () => {
      const insightsTab = document.querySelector(`.nav-item[data-tab="insights"]`);
      if (insightsTab) insightsTab.click();
    });
  }
}

function setupSidebarToggle() {
  if (!sidebarToggleBtn) return;
  sidebarToggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
  });
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const data = await res.json();

    const statTotalWords = document.getElementById("statTotalWords");
    const statWpm = document.getElementById("statWpm");
    const statStreak = document.getElementById("statStreak");
    const quotaWordsCount = document.getElementById("quotaWordsCount");
    const insightTotalWords = document.getElementById("insightTotalWords");
    const insightAvgWpm = document.getElementById("insightAvgWpm");

    if (statTotalWords) statTotalWords.textContent = data.formatted_words || "35.5K";
    if (statWpm) statWpm.textContent = data.avg_wpm || 106;
    if (statStreak) statStreak.textContent = data.streak_days || 1;
    if (quotaWordsCount) quotaWordsCount.textContent = data.words_remaining ? data.words_remaining.toLocaleString() : "1,631";
    if (insightTotalWords) insightTotalWords.textContent = (data.total_words || 35500).toLocaleString();
    if (insightAvgWpm) insightAvgWpm.textContent = `${data.avg_wpm || 106} WPM`;
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

// ---------------------------------------------------------------------------
// Timeline & History
// ---------------------------------------------------------------------------
function setupSearch() {
  if (!timelineSearchInput) return;
  timelineSearchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      loadTimeline(e.target.value.trim());
    }, 250);
  });
}

async function loadTimeline(searchQuery = "") {
  try {
    const url = searchQuery
      ? `/api/history?q=${encodeURIComponent(searchQuery)}`
      : "/api/history";
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch recordings");
    const data = await res.json();
    const recs = data.recordings || [];
    if (!searchQuery && recs.length > 0) {
      latestKnownRecordingId = recs[0].id;
      latestKnownCount = data.total || recs.length;
    }
    renderTimeline(recs);
  } catch (err) {
    timelineList.innerHTML = `<div class="empty-state">Failed to load recordings: ${err.message}</div>`;
  }
}

function renderTimeline(recordings) {
  if (!recordings || recordings.length === 0) {
    timelineList.innerHTML = `
      <div class="empty-state">
        <p>No voice recordings found.</p>
        <p style="font-size:12px; color:var(--text-light); margin-top:4px;">
          Hold Fn or click Dictate Now to create your first transcription.
        </p>
      </div>
    `;
    return;
  }

  // Group by date_group (TODAY, YESTERDAY, etc.)
  const groups = {};
  recordings.forEach(rec => {
    const groupKey = rec.date_group || "TODAY";
    if (!groups[groupKey]) groups[groupKey] = [];
    groups[groupKey].push(rec);
  });

  let html = "";
  for (const [groupName, items] of Object.entries(groups)) {
    html += `
      <div class="timeline-group">
        <div class="timeline-group-heading">${groupName}</div>
        <div class="timeline-items">
          ${items.map(rec => renderRecordingRow(rec)).join("")}
        </div>
      </div>
    `;
  }

  timelineList.innerHTML = html;
  attachTimelineEvents();
}

function renderRecordingRow(rec) {
  const isDismissed = rec.status === "dismissed";
  const displayTime = rec.display_time || "Now";
  const text = rec.formatted || rec.cleaned || rec.raw || "";
  const hasAudio = !!rec.audio_file;

  if (isDismissed) {
    return `
      <div class="timeline-row dismissed" data-id="${rec.id}">
        <div class="row-time">${displayTime}</div>
        <div class="row-content">
          <span class="dismissed-msg">This transcription was dismissed.</span>
          <span class="recover-link" data-action="recover" data-id="${rec.id}">Recover</span>
        </div>
        <div class="row-actions">
          <button class="action-btn" data-action="delete" data-id="${rec.id}" title="Delete permanently">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    `;
  }

  return `
    <div class="timeline-row" data-id="${rec.id}">
      <div class="row-time">${displayTime}</div>
      <div class="row-content">
        <div class="row-text" id="text-${rec.id}">${escapeHtml(text)}</div>
        <div class="row-meta">
          ${rec.app ? `<span class="row-meta-badge">${rec.app}</span>` : ""}
          ${rec.duration_sec ? `<span class="row-meta-badge">${rec.duration_sec}s</span>` : ""}
          ${rec.model_used ? `<span class="row-meta-badge">Whisper: ${rec.model_used}</span>` : ""}
        </div>
        ${hasAudio ? `
          <div class="audio-player-inline" id="player-${rec.id}" style="display:none;">
            <div class="waveform-scrubber" data-id="${rec.id}">
              <div class="waveform-progress" id="progress-${rec.id}"></div>
            </div>
            <span class="audio-duration-label" id="time-${rec.id}">0:00</span>
          </div>
        ` : ""}
      </div>
      <div class="row-actions">
        ${hasAudio ? `
          <button class="action-btn btn-play" data-action="play" data-id="${rec.id}" title="Play Audio">
            <svg class="play-icon" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          </button>
        ` : ""}
        <button class="action-btn btn-copy" data-action="copy" data-id="${rec.id}" title="Copy Text">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
        </button>
        <button class="action-btn btn-retry-cleanup" data-action="retry-cleanup" data-id="${rec.id}" title="Re-try LLM Cleanup">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        </button>
        ${hasAudio ? `
          <button class="action-btn btn-retranscribe" data-action="retranscribe" data-id="${rec.id}" title="Re-transcribe Audio">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          </button>
        ` : ""}
        <button class="action-btn btn-flag ${rec.flagged ? 'active' : ''}" data-action="flag" data-id="${rec.id}" title="Flag">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/></svg>
        </button>
        <div class="actions-dropdown-wrap">
          <button class="action-btn btn-more" data-action="more" data-id="${rec.id}" title="More Actions">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="2"/><circle cx="12" cy="5" r="2"/><circle cx="12" cy="19" r="2"/></svg>
          </button>
          <div class="dropdown-menu" id="dropdown-${rec.id}" style="display:none;">
            <button class="dropdown-item" data-action="transform" data-id="${rec.id}" data-transform="formal">🪄 Executive Formal</button>
            <button class="dropdown-item" data-action="transform" data-id="${rec.id}" data-transform="casual">💬 Casual Chat</button>
            <button class="dropdown-item" data-action="transform" data-id="${rec.id}" data-transform="bullets">📋 Bullet Points</button>
            <button class="dropdown-item" data-action="transform" data-id="${rec.id}" data-transform="concise">⚡ Ultra Concise</button>
            <hr style="border:none; border-top:1px solid var(--border-subtle); margin:4px 0;">
            <button class="dropdown-item" data-action="view-raw" data-id="${rec.id}">📄 View Raw Whisper</button>
            <button class="dropdown-item" data-action="dismiss" data-id="${rec.id}">🚫 Dismiss</button>
            <button class="dropdown-item danger" data-action="delete" data-id="${rec.id}">🗑️ Delete</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function attachTimelineEvents() {
  document.querySelectorAll(".timeline-row").forEach(row => {
    const recId = row.getAttribute("data-id");

    // Click handler for buttons
    row.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      e.stopPropagation();

      const action = btn.getAttribute("data-action");
      const id = btn.getAttribute("data-id") || recId;

      if (action === "play") togglePlayAudio(id);
      if (action === "copy") copyTranscript(id);
      if (action === "retry-cleanup") retryCleanup(id);
      if (action === "retranscribe") openRetranscribeModal(id);
      if (action === "flag") toggleFlag(id, btn);
      if (action === "dismiss") dismissRecording(id);
      if (action === "recover") recoverRecording(id);
      if (action === "delete") deleteRecording(id);
      if (action === "more") toggleDropdown(id);
      if (action === "transform") {
        const transformType = btn.getAttribute("data-transform");
        applyTransform(id, transformType);
      }
      if (action === "view-raw") viewRawTranscript(id);
    });
  });

  // Close dropdowns on outside click
  document.addEventListener("click", () => {
    document.querySelectorAll(".dropdown-menu").forEach(m => m.style.display = "none");
  });
}

function toggleDropdown(id) {
  const menu = document.getElementById(`dropdown-${id}`);
  if (!menu) return;
  const isShown = menu.style.display === "flex";
  document.querySelectorAll(".dropdown-menu").forEach(m => m.style.display = "none");
  menu.style.display = isShown ? "none" : "flex";
}

// ---------------------------------------------------------------------------
// Audio Playback
// ---------------------------------------------------------------------------
function togglePlayAudio(id) {
  if (currentPlayingId === id && currentAudio && !currentAudio.paused) {
    currentAudio.pause();
    updatePlayButtonState(id, false);
    return;
  }

  if (currentAudio) {
    currentAudio.pause();
    if (currentPlayingId) updatePlayButtonState(currentPlayingId, false);
  }

  currentPlayingId = id;
  const playerBar = document.getElementById(`player-${id}`);
  const progressBar = document.getElementById(`progress-${id}`);
  const timeLabel = document.getElementById(`time-${id}`);
  if (playerBar) playerBar.style.display = "flex";

  currentAudio = new Audio(`/api/audio/${id}`);
  currentAudio.play();
  updatePlayButtonState(id, true);

  currentAudio.ontimeupdate = () => {
    if (!currentAudio.duration) return;
    const pct = (currentAudio.currentTime / currentAudio.duration) * 100;
    if (progressBar) progressBar.style.width = `${pct}%`;
    if (timeLabel) timeLabel.textContent = formatDuration(currentAudio.currentTime);
  };

  currentAudio.onended = () => {
    updatePlayButtonState(id, false);
    if (progressBar) progressBar.style.width = "0%";
  };

  currentAudio.onerror = () => {
    showToast("⚠️ Could not play audio recording");
    updatePlayButtonState(id, false);
  };
}

function updatePlayButtonState(id, isPlaying) {
  const row = document.querySelector(`.timeline-row[data-id="${id}"]`);
  if (!row) return;
  const playBtn = row.querySelector(".btn-play");
  if (!playBtn) return;

  if (isPlaying) {
    playBtn.classList.add("playing");
    playBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
  } else {
    playBtn.classList.remove("playing");
    playBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>`;
  }
}

function formatDuration(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

// ---------------------------------------------------------------------------
// Actions: Copy, Retry Cleanup, Transforms, Re-transcribe
// ---------------------------------------------------------------------------
function copyTranscript(id) {
  const textEl = document.getElementById(`text-${id}`);
  if (!textEl) return;
  const text = textEl.textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast("📋 Copied to clipboard");
  }).catch(() => {
    showToast("Failed to copy");
  });
}

async function retryCleanup(id) {
  showToast("🔄 Retrying LLM cleanup...");
  try {
    const res = await fetch(`/api/retry_cleanup/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style: "clean" }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Retry failed");

    const textEl = document.getElementById(`text-${id}`);
    if (textEl) {
      textEl.textContent = data.recording.formatted || data.recording.cleaned;
      textEl.style.transition = "color 0.3s";
      textEl.style.color = "var(--accent-orange)";
      setTimeout(() => { textEl.style.color = ""; }, 1000);
    }
    showToast("✓ Cleanup updated successfully!");
  } catch (err) {
    showToast(`⚠️ Retry failed: ${err.message}`);
  }
}

async function applyTransform(id, transformType) {
  showToast(`🪄 Applying ${transformType} transform...`);
  try {
    const res = await fetch(`/api/transform/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transform: transformType }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Transform failed");

    const textEl = document.getElementById(`text-${id}`);
    if (textEl) {
      textEl.textContent = data.recording.formatted;
    }
    showToast(`✓ Transformed into ${transformType}`);
  } catch (err) {
    showToast(`⚠️ Transform failed: ${err.message}`);
  }
}

// Modal Re-transcribe
function openRetranscribeModal(id) {
  activeRetranscribeId = id;
  if (retranscribeModal) retranscribeModal.style.display = "flex";
}

document.getElementById("closeRetranscribeModal")?.addEventListener("click", () => {
  retranscribeModal.style.display = "none";
});
document.getElementById("cancelRetranscribeBtn")?.addEventListener("click", () => {
  retranscribeModal.style.display = "none";
});

document.getElementById("confirmRetranscribeBtn")?.addEventListener("click", async () => {
  if (!activeRetranscribeId) return;
  const model = document.getElementById("modalSelectModel").value;
  const language = document.getElementById("modalSelectLang").value;
  retranscribeModal.style.display = "none";

  showToast(`⚡ Re-transcribing with Whisper '${model}'...`);
  try {
    const res = await fetch(`/api/retry_transcribe/${activeRetranscribeId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: model,
        language: language === "auto" ? null : language,
        run_llm: true,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Re-transcribe failed");

    const textEl = document.getElementById(`text-${activeRetranscribeId}`);
    if (textEl) {
      textEl.textContent = data.recording.formatted;
    }
    showToast("✓ Audio re-transcribed and cleaned!");
    loadStats();
  } catch (err) {
    showToast(`⚠️ Re-transcribe failed: ${err.message}`);
  }
});

async function toggleFlag(id, btn) {
  try {
    const res = await fetch(`/api/history/${id}/flag`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      btn.classList.toggle("active");
    }
  } catch (err) {
    console.error("Flag error:", err);
  }
}

async function dismissRecording(id) {
  try {
    const res = await fetch(`/api/history/${id}/dismiss`, { method: "POST" });
    if (res.ok) {
      loadTimeline(timelineSearchInput?.value.trim());
      showToast("Transcription dismissed");
    }
  } catch (err) {
    showToast("Failed to dismiss");
  }
}

async function recoverRecording(id) {
  try {
    const res = await fetch(`/api/history/${id}/recover`, { method: "POST" });
    if (res.ok) {
      loadTimeline(timelineSearchInput?.value.trim());
      showToast("Transcription recovered");
    }
  } catch (err) {
    showToast("Failed to recover");
  }
}

async function deleteRecording(id) {
  if (!confirm("Are you sure you want to permanently delete this recording and its audio?")) return;
  try {
    const res = await fetch(`/api/history/${id}`, { method: "DELETE" });
    if (res.ok) {
      loadTimeline(timelineSearchInput?.value.trim());
      loadStats();
      showToast("Recording deleted");
    }
  } catch (err) {
    showToast("Failed to delete");
  }
}

async function viewRawTranscript(id) {
  try {
    const res = await fetch(`/api/history`);
    const data = await res.json();
    const rec = (data.recordings || []).find(r => r.id === id);
    if (rec) {
      alert(`Raw Whisper Output:\n\n${rec.raw}\n\nCleaned:\n${rec.cleaned}\n\nFormatted:\n${rec.formatted}`);
    }
  } catch (err) {
    console.error("View raw error:", err);
  }
}

// ---------------------------------------------------------------------------
// Live In-Browser Web Recording (MediaRecorder)
// ---------------------------------------------------------------------------
function setupLiveRecording() {
  const webRecordBtn = document.getElementById("webRecordBtn");
  const webRecordLabel = document.getElementById("webRecordLabel");
  const webRecTimer = document.getElementById("webRecTimer");

  if (!webRecordBtn) return;

  webRecordBtn.addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      // Stop recording
      mediaRecorder.stop();
      webRecordBtn.classList.remove("recording");
      webRecordLabel.textContent = "Processing...";
      clearInterval(recTimerInterval);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(recordedChunks, { type: "audio/webm" });
        stream.getTracks().forEach(track => track.stop());

        // Send to backend
        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");
        formData.append("app", "Flow Web");

        try {
          const res = await fetch("/transcribe", { method: "POST", body: formData });
          const data = await res.json();
          if (res.ok && data.text) {
            showToast("✓ Dictation saved and transcribed!");
            loadTimeline();
            loadStats();
          } else {
            showToast(`⚠️ Transcription error: ${data.error || "No speech recognized"}`);
          }
        } catch (err) {
          showToast(`⚠️ Network error: ${err.message}`);
        } finally {
          webRecordLabel.textContent = "Dictate Now";
          webRecTimer.style.display = "none";
        }
      };

      mediaRecorder.start();
      webRecordBtn.classList.add("recording");
      webRecordLabel.textContent = "Recording...";
      webRecTimer.style.display = "inline";
      recStartTime = Date.now();
      recTimerInterval = setInterval(() => {
        const elapsedSec = Math.floor((Date.now() - recStartTime) / 1000);
        webRecTimer.textContent = formatDuration(elapsedSec);
      }, 500);

    } catch (err) {
      showToast(`⚠️ Microphone access denied: ${err.message}`);
    }
  });
}

// ---------------------------------------------------------------------------
// Dictionary
// ---------------------------------------------------------------------------
function setupDictionary() {
  const addBtn = document.getElementById("addDictWordBtn");
  const input = document.getElementById("newDictWordInput");

  if (!addBtn || !input) return;

  addBtn.addEventListener("click", async () => {
    const word = input.value.trim();
    if (!word) return;
    try {
      const res = await fetch("/api/dictionary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word }),
      });
      if (res.ok) {
        input.value = "";
        loadDictionary();
        showToast(`✓ Added "${word}" to dictionary`);
      }
    } catch (err) {
      showToast("Failed to add word");
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addBtn.click();
  });
}

async function loadDictionary() {
  const list = document.getElementById("dictTagsList");
  if (!list) return;
  try {
    const res = await fetch("/api/dictionary");
    const data = await res.json();
    const words = data.words || [];
    if (words.length === 0) {
      list.innerHTML = `<div class="empty-state">No custom words added yet.</div>`;
      return;
    }
    list.innerHTML = words.map(w => `
      <div class="dict-tag">
        <span>${escapeHtml(w)}</span>
        <span class="dict-tag-remove" onclick="removeDictWord('${escapeHtml(w)}')">✕</span>
      </div>
    `).join("");
  } catch (err) {
    list.innerHTML = "Failed to load dictionary";
  }
}

window.removeDictWord = async function(word) {
  try {
    const res = await fetch(`/api/dictionary/${encodeURIComponent(word)}`, { method: "DELETE" });
    if (res.ok) {
      loadDictionary();
      showToast(`Removed "${word}"`);
    }
  } catch (err) {
    showToast("Failed to remove word");
  }
};

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
function setupSettings() {
  const whisperSelect = document.getElementById("settingWhisperModel");
  const llmSelect = document.getElementById("settingLlmModel");

  whisperSelect?.addEventListener("change", async (e) => {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: e.target.value }),
    });
    showToast(`✓ Whisper model set to ${e.target.value}`);
  });

  llmSelect?.addEventListener("change", async (e) => {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ llm_model: e.target.value }),
    });
    showToast(`✓ Local LLM engine set to ${e.target.value}`);
  });
}

function escapeHtml(text) {
  if (!text) return "";
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
