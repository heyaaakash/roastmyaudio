/* RoastMyAudio — a local voice workspace. No external client dependencies. */
"use strict";
const $ = (id) => document.getElementById(id);
const icons = {
  wave: '<path d="M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4"/>',
  mic: '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',
  book: '<path d="M4 19V5a2 2 0 0 1 2-2h14v18H6a2 2 0 0 1 0-4h14M8 7h8M8 11h6"/>',
  edit: '<path d="M12 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-7M16 3l5 5-10 10-5 1 1-5z"/>',
  sliders:
    '<path d="M4 6h5m4 0h7M4 12h10m4 0h2M4 18h2m4 0h10"/><circle cx="11" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  shield: '<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7zM8 12l3 3 5-6"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01"/>',
  moon: '<path d="M20 14A9 9 0 0 1 10 4a9 9 0 1 0 10 10Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  type: '<path d="M4 7V4h16v3M12 4v16m-4 0h8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4H4v12h4"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  sparkle:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  play: '<path d="m8 4 12 8-12 8z"/>',
  save: '<path d="M6 3h12v18l-6-4-6 4z"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  undo: '<path d="M4 4v6h6M4 10a8 8 0 1 1 0 7"/>',
};
function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.wave}</svg>`;
}
function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
function escapeHTML(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
const state = {
  view: "dictation",
  filter: "all",
  recordings: [],
  settings: {
    model: "base",
    language: "en",
    llm_enabled: true,
    llm_model: "qwen2.5-0.5b",
  },
  demo: false,
  phase: "idle",
  activeId: null,
  refresh: 0,
  loaded: false,
  desktop: Boolean(window.roastmyaudioDesktop?.command),
  desktopState: null,
};
let recorder,
  stream,
  audioContext,
  analyser,
  animationFrame,
  timer,
  recordingStart,
  discarded = false;
let pendingAudio = null;
let settingsDirty = false;
const storage = {
  get(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
      return true;
    } catch {
      return false;
    }
  },
};
async function api(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  const data = await response.json();
  if (!response.ok || data.success === false)
    throw new Error(
      data.error || `Request failed (${response.status}). Try again.`,
    );
  return data;
}
function post(path, data = {}) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
function toast(message, undo) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  if (undo) {
    const button = document.createElement("button");
    button.textContent = "Undo";
    button.onclick = () => {
      undo();
      el.remove();
    };
    el.append(button);
  }
  $("toasts").append(el);
  setTimeout(() => el.remove(), undo ? 8000 : 4500);
}
async function copy(text) {
  if (!text.trim()) return toast("There’s nothing to copy yet.");
  try {
    if (window.roastmyaudioDesktop) await window.roastmyaudioDesktop.copy(text);
    else await navigator.clipboard.writeText(text);
    toast("Copied. Take your thought anywhere.");
  } catch {
    toast(
      "Clipboard access is unavailable. Select the text and copy it manually.",
    );
  }
}
function navigate(view, updateHash = true) {
  if (!["dictation", "dictionary", "scratchpad", "settings"].includes(view))
    view = "dictation";
  state.view = view;
  document.querySelectorAll(".view").forEach((el) => {
    el.hidden = el.id !== `view-${view}`;
    el.classList.toggle("active", !el.hidden);
  });
  document.querySelectorAll(".nav-item[data-view]").forEach((el) => {
    const active = el.dataset.view === view;
    el.classList.toggle("active", active);
    if (active) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  $("pageName").textContent = view[0].toUpperCase() + view.slice(1);
  $("sidebar").classList.remove("open");
  $("menuBtn").setAttribute("aria-expanded", "false");
  if (updateHash) history.replaceState(null, "", `#${view}`);
  if (view === "dictionary") loadDictionary();
  if (view === "settings" && !settingsDirty) loadSettings();
}
function setTheme(theme, persist = true) {
  document.documentElement.dataset.theme = theme;
  storage.set("rma-theme", theme);
  if (persist && workspaceLoaded)
    post("/api/workspace", { theme }).catch(() =>
      toast("Appearance couldn’t save."),
    );
  $("themeBtn").innerHTML = icon(theme === "dark" ? "sun" : "moon");
  $("themeBtn").setAttribute(
    "aria-label",
    `Switch to ${theme === "dark" ? "light" : "dark"} appearance`,
  );
}
function setConnection(ok) {
  $("connectionStatus").classList.toggle("offline", !ok);
  $("connectionStatus").innerHTML =
    `<i></i>${ok ? "Local workspace" : "Server unavailable"}`;
}
function updateStats(data) {
  $("statWords").textContent = Number(data.total_words ?? 0).toLocaleString();
  $("statRecordings").textContent = data.total_recordings ?? 0;
  $("statMinutes").textContent = data.total_minutes ?? 0;
}
async function refresh() {
  if (state.demo || state.phase !== "idle" || (document.hidden && state.loaded))
    return;
  const generation = ++state.refresh;
  try {
    const [historyData, stats] = await Promise.all([
      api("/api/history?limit=100"),
      api("/api/stats"),
    ]);
    if (generation !== state.refresh || state.demo) return;
    const changed =
      JSON.stringify(state.recordings) !==
      JSON.stringify(historyData.recordings);
    state.recordings = historyData.recordings;
    state.loaded = true;
    if (changed || $("timeline").getAttribute("aria-busy") === "true")
      renderTimeline();
    updateStats(stats);
    setConnection(true);
  } catch {
    setConnection(false);
    if ($("timeline").getAttribute("aria-busy") === "true") {
      $("timeline").innerHTML =
        '<div class="empty-state"><h3>We couldn’t open your workspace.</h3><p>Check that the local server is running, then try again.</p><button class="text-button" id="reloadBtn">Try again →</button></div>';
      $("reloadBtn").onclick = refresh;
    }
  }
  $("timeline").setAttribute("aria-busy", "false");
}
function emptyState(filtered) {
  return `<div class="empty-state"><div class="empty-icon">${icon(filtered ? "search" : "wave")}</div><h3>${filtered ? "No thoughts here just yet." : "Your next good thought belongs here."}</h3><p>${filtered ? "Try another search or switch back to All thoughts." : "A note to yourself. A message to someone else.<br>Start dictating and make a little room in your head."}</p><button class="text-button" id="emptyAction">${filtered ? "Clear filters →" : "Explore a sample workspace →"}</button></div>`;
}
function actionButton(action, id, title, name, active = false) {
  return `<button class="icon-button${active ? " saved" : ""}" data-action="${action}" data-id="${escapeHTML(id)}" aria-label="${title}" title="${title}"${action === "save" ? ` aria-pressed="${active}"` : ""}>${icon(name)}</button>`;
}
function renderTimeline() {
  const query = $("searchInput").value.trim().toLowerCase();
  const recordings = state.recordings.filter((rec) => {
    const visible =
      state.filter === "dismissed"
        ? rec.status === "dismissed"
        : rec.status !== "dismissed";
    const saved = state.filter !== "saved" || rec.flagged;
    const matching = [rec.raw, rec.cleaned, rec.formatted, rec.app].some(
      (text) =>
        String(text || "")
          .toLowerCase()
          .includes(query),
    );
    return visible && saved && (!query || matching);
  });
  $("historyCount").textContent = recordings.length;
  $("exportBtn").disabled = !recordings.length;
  if (!recordings.length) {
    const filtered = !!query || state.filter !== "all";
    $("timeline").innerHTML = emptyState(filtered);
    $("emptyAction").onclick = filtered
      ? () => {
          $("searchInput").value = "";
          selectFilter("all");
        }
      : showDemo;
    return;
  }
  let group = "";
  let html = "";
  for (const rec of recordings) {
    const date = rec.date_group || "EARLIER";
    if (date !== group) {
      group = date;
      html += `<div class="date-label">${escapeHTML(date)}</div>`;
    }
    const dismissed = rec.status === "dismissed";
    const text = rec.formatted || rec.cleaned || rec.raw || "";
    const preview = text || (rec.status === "failed" ? "Recording interrupted. Open to retry saved audio." : rec.status === "processing" ? "Transcribing this recording…" : "");
    html += `<article class="thought${dismissed ? " dismissed" : ""}" data-recording="${escapeHTML(rec.id)}"><div class="thought-icon">${icon("wave")}</div><div class="thought-body"><div class="thought-meta"><strong>${escapeHTML(rec.app || "Dictation")}</strong><span>·</span><span>${escapeHTML(rec.display_time || "")}</span><span>·</span><span>${text.trim() ? text.trim().split(/\s+/).length : 0} words</span>${rec.duration_sec ? `<span>·</span><span>${Math.round(rec.duration_sec)} sec</span>` : ""}${state.demo ? "<span>· Sample</span>" : ""}</div><p>${dismissed ? "This thought has been dismissed. Recover it whenever you’re ready." : escapeHTML(preview)}</p><div class="audio-slot"></div></div><div class="thought-actions">${dismissed ? actionButton("recover", rec.id, "Recover recording", "undo") : `${rec.audio_file ? actionButton("play", rec.id, "Play saved audio", "play") : ""}${actionButton("copy", rec.id, "Copy transcript", "copy")}${actionButton("save", rec.id, "Save thought", "save", !!rec.flagged)}${actionButton("draft", rec.id, "Move to scratchpad", "edit")}${actionButton("details", rec.id, "Recording details and rewrites", "more")}${actionButton("dismiss", rec.id, "Dismiss recording", "close")}`}${dismissed ? actionButton("delete", rec.id, "Delete recording permanently", "trash") : ""}</div></article>`;
  }
  $("timeline").innerHTML = html;
}
function selectFilter(filter) {
  state.filter = filter;
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    const active = btn.dataset.filter === filter;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
  renderTimeline();
}
function showDemo() {
  state.demo = true;
  state.refresh++;
  $("demoBanner").hidden = false;
  const samples = [
    [
      "A little idea",
      "The best products make a small, everyday moment feel a little better. That’s the kind of thing I want to build.",
      "10:42 am",
      22,
      true,
    ],
    [
      "A message to the team",
      "Hey team, let’s keep the first version simple. One useful workflow, a clear first step, and no dead ends. We can build from there.",
      "10:28 am",
      18,
      false,
    ],
    [
      "A note for later",
      "Less friction between having a thought and doing something with it. That’s the whole idea.",
      "9:16 am",
      11,
      false,
    ],
  ];
  state.recordings = samples.map(
    ([app, raw, display_time, duration_sec, flagged], i) => ({
      id: `sample_${i}`,
      app,
      raw,
      formatted: raw,
      display_time,
      duration_sec,
      flagged,
      status: "completed",
      date_group: "SAMPLE THOUGHTS",
      audio_file: null,
    }),
  );
  updateStats({
    total_words: state.recordings.reduce(
      (n, r) => n + r.raw.split(" ").length,
      0,
    ),
    total_recordings: 3,
    total_minutes: 0.9,
  });
  selectFilter("all");
  renderTimeline();
}
async function loadDictionary() {
  try {
    const data = await api("/api/dictionary");
    $("dictionaryCount").textContent = data.words.length;
    $("dictionaryList").innerHTML = data.words.length
      ? data.words
          .map(
            (word) =>
              `<div class="word-tag"><span>${escapeHTML(word)}</span><button class="icon-button" data-word="${escapeHTML(word)}" aria-label="Remove ${escapeHTML(word)}">${icon("close")}</button></div>`,
          )
          .join("")
      : '<p class="view-description">An empty dictionary, full of possibility. Add your first word above.</p>';
  } catch {
    $("dictionaryList").textContent =
      "Couldn’t load your vocabulary. Check the local server and try again.";
  }
}
async function loadSettings() {
  try {
    state.settings = await api("/api/settings");
    const s = state.settings;
    if (settingsDirty) return;
    if (
      !$("modelSetting").querySelector(`option[value="${CSS.escape(s.model)}"]`)
    )
      $("modelSetting").add(new Option(s.model, s.model));
    $("modelSetting").value = s.model;
    $("languageSetting").value = s.language || "en";
    $("cleanupSetting").checked = s.llm_enabled;
    $("llmSetting").value = s.llm_model;
    for (const [id, key] of [
      ["hotkeySetting", "hotkey"],
      ["modeSetting", "dictation_mode"],
    ])
      $(id).value = s[key] || (key === "hotkey" ? "fn" : "push_to_talk");
    $("contextSetting").checked = Boolean(s.context_awareness);
    $("feedbackSetting").checked = Boolean(s.haptics_enabled);
    $("commandsSetting").checked = Boolean(s.voice_commands);
    $("deviceSetting").value = s.device_id == null ? "" : String(s.device_id);
    $("quickModelLabel").textContent = `Whisper · ${s.model}`;
  } catch {
    toast("Preferences couldn’t load. Check the local server.");
  }
}
let draftSaveSequence = 0;
let draftSaveQueue = Promise.resolve();
let workspaceLoaded = false;
async function updateDraft() {
  const text = $("scratchpad").value;
  const sequence = ++draftSaveSequence;
  $("draftWordCount").textContent =
    `${text.trim() ? text.trim().split(/\s+/).length : 0} words`;
  $("draftStatus").textContent = "Saving…";
  storage.set("rma-draft", text); // Local recovery copy; durable store is authoritative.
  try {
    if (state.desktop) await window.roastmyaudioDesktop.saveDraft(text);
    else {
      draftSaveQueue = draftSaveQueue
        .catch(() => {})
        .then(() => post("/api/workspace", { draft: text }));
      await draftSaveQueue;
    }
    if (sequence === draftSaveSequence)
      $("draftStatus").textContent = "Saved on this computer";
  } catch {
    if (sequence === draftSaveSequence)
      $("draftStatus").textContent =
        "Couldn't save — copy your draft before quitting";
  }
}
async function loadWorkspace() {
  try {
    let workspace = await api("/api/workspace");
    const legacy = storage.get("rma-draft");
    if (!workspace.draft && legacy)
      workspace = await post("/api/workspace", {
        draft: legacy,
        only_if_empty: true,
      });
    $("scratchpad").value = workspace.draft || "";
    setTheme(workspace.theme || "light", false);
    workspaceLoaded = true;
    $("draftWordCount").textContent =
      `${workspace.draft?.trim() ? workspace.draft.trim().split(/\s+/).length : 0} words`;
    $("draftStatus").textContent = "Saved on this computer";
    if (state.desktop && !workspace.onboarding_complete)
      openDialog("setupDialog");
  } catch {
    toast("Workspace storage unavailable. Keep a copy of your draft.");
  }
}
function appendDraft(text) {
  $("scratchpad").value = [$("scratchpad").value.trim(), text]
    .filter(Boolean)
    .join("\n\n");
  updateDraft();
  navigate("scratchpad");
  $("scratchpad").focus();
}
function openDialog(id) {
  $(id).showModal();
}
function confirmAction(title, description, label, callback) {
  $("confirmHeading").textContent = title;
  $("confirmText").textContent = description;
  $("confirmAction").textContent = label;
  $("confirmAction").onclick = async () => {
    $("confirmDialog").close();
    try {
      await callback();
    } catch (err) {
      toast(err.message);
    }
  };
  openDialog("confirmDialog");
}
async function handleThoughtAction(button) {
  const { action, id } = button.dataset;
  const rec = state.recordings.find((r) => r.id === id);
  if (!rec) return;
  const text = rec.formatted || rec.cleaned || rec.raw || (rec.status === "failed" ? "Recording interrupted. Open to retry saved audio." : rec.status === "processing" ? "Transcribing this recording…" : "");
  if (action === "copy") return copy(text);
  if (action === "draft") return appendDraft(text);
  if (state.demo)
    return toast(
      "This is a read-only sample. Return to your workspace to use recording actions.",
    );
  button.disabled = true;
  try {
    if (action === "play") {
      const row = button.closest(".thought");
      const slot = row.querySelector(".audio-slot");
      if (slot.firstChild) {
        slot.replaceChildren();
        return;
      }
      document.querySelectorAll("audio").forEach((audio) => audio.pause());
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = `/api/audio/${encodeURIComponent(id)}`;
      slot.append(audio);
      await audio.play();
    }
    if (action === "save") {
      const data = await post(`/api/history/${encodeURIComponent(id)}/flag`);
      Object.assign(rec, data.recording);
      renderTimeline();
      toast(
        rec.flagged
          ? "Saved for a second look."
          : "Removed from saved thoughts.",
      );
    }
    if (action === "dismiss" || action === "recover") {
      await post(`/api/history/${encodeURIComponent(id)}/${action}`);
      rec.status = action === "dismiss" ? "dismissed" : "completed";
      renderTimeline();
      refresh();
      if (action === "dismiss")
        toast("Thought dismissed. You can recover it.", async () => {
          try {
            await post(`/api/history/${encodeURIComponent(id)}/recover`);
            await refresh();
          } catch (err) {
            toast(err.message);
          }
        });
      else toast("Your thought is back.");
    }
    if (action === "delete")
      confirmAction(
        "Delete this thought?",
        "This permanently removes the transcript and its saved audio. It cannot be undone.",
        "Delete recording",
        async () => {
          await api(`/api/history/${encodeURIComponent(id)}`, {
            method: "DELETE",
          });
          await refresh();
          toast("Recording deleted.");
        },
      );
    if (action === "details") {
      state.activeId = id;
      $("rawTranscript").textContent = rec.raw || text;
      $("retryBtn").disabled = !rec.audio_file;
      $("retryHint").textContent = rec.audio_file
        ? "Uses the saved audio and your language preference."
        : "This older recording has no saved audio to re-transcribe.";
      openDialog("recordingDialog");
    }
  } catch (err) {
    toast(action === "play" ? "Couldn’t play the saved audio." : err.message);
  } finally {
    button.disabled = false;
  }
}
function duration(seconds) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}
function setPhase(phase) {
  state.phase = phase;
  const listening = phase === "recording",
    working = phase === "processing",
    preparing = phase === "requesting";
  $("recordBtn").disabled = working || preparing;
  $("recordLabel").textContent = listening
    ? "Finish dictating"
    : working
      ? "Turning voice into words…"
      : preparing
        ? "Opening microphone…"
        : "Start dictating";
  $("recordBtn").querySelector("[data-icon]").innerHTML = icon(
    listening ? "check" : "mic",
  );
  $("recordingCard").classList.toggle("listening", listening);
  $("recordingLive").hidden = !listening && !working;
  $("recordState").textContent = working
    ? "Transcribing locally…"
    : "Listening";
  $("cancelRecordBtn").hidden = working;
  $("recordHeading").innerHTML = listening
    ? "Go on.<br>We’re listening."
    : working
      ? "A thought,<br>taking shape."
      : "Let your thoughts<br>do the talking.";
  $("recordDescription").innerHTML = working
    ? "The first model download can take a while.<br>Your recording stays on this computer."
    : listening
      ? "Pause, ramble, find your words.<br>Click finish when you’re ready."
      : "Speak naturally. We’ll turn it into text<br>you can take anywhere.";
  $("artLabel").textContent = listening
    ? "Your next thought is taking shape."
    : "A little room to think out loud.";
}
function releaseMic() {
  clearInterval(timer);
  cancelAnimationFrame(animationFrame);
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  if (audioContext) audioContext.close().catch(() => {});
  audioContext = null;
  document.querySelectorAll("#waveform i").forEach((el) => {
    el.style.height = el.dataset.height;
  });
}
function animateWave() {
  if (!analyser || state.phase !== "recording") return;
  const values = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(values);
  document.querySelectorAll("#waveform i").forEach((bar, i) => {
    const value = values[i * 3];
    bar.style.height = `${6 + (value / 255) * 44}px`;
  });
  animationFrame = requestAnimationFrame(animateWave);
}
async function toggleRecord() {
  if (state.desktop) {
    try {
      const phase = state.desktopState?.phase;
      const result = await window.roastmyaudioDesktop.command(
        phase === "recording" ? "stop" : "start",
        {
          strict: $("quickStyle").value === "verbatim",
          practice: $("setupDialog").open,
        },
      );
      applyDesktopState(result);
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  if (state.phase === "recording") {
    recorder.stop();
    return;
  }
  if (state.phase !== "idle") return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
    return toast(
      "Microphone recording needs a supported browser on localhost or HTTPS.",
    );
  if (state.demo) {
    state.demo = false;
    $("demoBanner").hidden = true;
    await refresh();
  }
  if (pendingAudio) {
    toast("Retry or discard the previous recording before starting another.");
    return;
  }
  setPhase("requesting");
  discarded = false;
  try {
    if (!settingsDirty) await loadSettings();
    if (discarded) {
      setPhase("idle");
      return;
    }
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (discarded) {
      releaseMic();
      setPhase("idle");
      return;
    }
    const type = [
      "audio/webm;codecs=opus",
      "audio/mp4",
      "audio/ogg;codecs=opus",
    ].find((t) => MediaRecorder.isTypeSupported(t));
    recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
    const chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data);
    };
    recorder.onerror = () => {
      discarded = true;
      if (recorder.state !== "inactive") recorder.stop();
      releaseMic();
      setPhase("idle");
      toast("Recording was interrupted. Please try again.");
    };
    recorder.onstop = async () => {
      const seconds = (Date.now() - recordingStart) / 1000;
      releaseMic();
      if (discarded) {
        setPhase("idle");
        toast("Recording discarded.");
        return;
      }
      const blob = new Blob(chunks, { type: recorder.mimeType });
      if (!blob.size || seconds < 0.5) {
        setPhase("idle");
        toast("That was a little short. Try speaking for a moment longer.");
        return;
      }
      pendingAudio = { blob, seconds };
      await uploadRecording();
    };
    recorder.start();
    recordingStart = Date.now();
    setPhase("recording");
    $("recordTimer").textContent = "0:00";
    timer = setInterval(() => {
      const seconds = (Date.now() - recordingStart) / 1000;
      $("recordTimer").textContent = duration(seconds);
      if (seconds >= 300 && recorder.state === "recording") {
        recorder.stop();
        toast("Five-minute limit reached. Finishing your recording.");
      }
    }, 250);
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 128;
      audioContext.createMediaStreamSource(stream).connect(analyser);
      animateWave();
    } catch {
      /* Recording also works without the visualizer. */
    }
  } catch (err) {
    releaseMic();
    setPhase("idle");
    toast(
      err.name === "NotAllowedError"
        ? "Microphone permission was declined. Allow it in your browser’s site settings, then try again."
        : err.name === "NotFoundError"
          ? "No microphone found. Connect one and try again."
          : "Couldn’t open your microphone. Check permissions and whether another app is using it.",
    );
  }
}
async function uploadRecording() {
  if (!pendingAudio) return;
  setPhase("processing");
  const { blob, seconds } = pendingAudio;
  const form = new FormData();
  const extension = blob.type.includes("mp4")
    ? "m4a"
    : blob.type.includes("ogg")
      ? "ogg"
      : "webm";
  form.append("audio", blob, `recording.${extension}`);
  form.append("duration_sec", String(seconds));
  form.append("model", state.settings.model);
  form.append("language", state.settings.language);
  form.append("strict_mode", String($("quickStyle").value === "verbatim"));
  form.append("app", "Web dictation");
  try {
    const data = await api("/transcribe", { method: "POST", body: form });
    pendingAudio = null;
    $("resultText").textContent =
      data.text ||
      "No speech was detected. Try a quieter room or check your microphone.";
    $("sessionResult").hidden = false;
    $("copyResultBtn").disabled = !data.text;
    $("draftResultBtn").disabled = !data.text;
    setPhase("idle");
    await refresh();
    if (data.text) toast("Thought captured.");
    else toast("No speech detected. Try again when you’re ready.");
  } catch (err) {
    setPhase("idle");
    $("sessionResult").hidden = false;
    $("resultText").textContent =
      `${err.message} Your audio is still held in this tab. Retry to process it again, or discard it.`;
    $("copyResultBtn").disabled = true;
    $("draftResultBtn").disabled = true;
    const retry = document.createElement("button");
    retry.className = "button secondary";
    retry.textContent = "Retry this recording";
    retry.id = "retryUpload";
    retry.onclick = uploadRecording;
    const discard = document.createElement("button");
    discard.className = "text-button";
    discard.textContent = "Discard audio";
    discard.id = "discardUpload";
    discard.onclick = () => {
      pendingAudio = null;
      $("sessionResult").hidden = true;
      retry.remove();
      discard.remove();
    };
    $("retryUpload")?.remove();
    $("discardUpload")?.remove();
    $("sessionResult").append(retry, discard);
    toast(
      "Couldn’t transcribe. Your recording is available to retry in this tab.",
    );
  }
  if (!pendingAudio) {
    $("retryUpload")?.remove();
    $("discardUpload")?.remove();
  }
}
async function exportHistory() {
  const query = $("searchInput").value.trim().toLowerCase();
  const records = state.recordings.filter(
    (r) =>
      (state.filter === "dismissed"
        ? r.status === "dismissed"
        : r.status !== "dismissed") &&
      (state.filter !== "saved" || r.flagged) &&
      (!query ||
        [r.raw, r.cleaned, r.formatted, r.app].some((t) =>
          String(t || "")
            .toLowerCase()
            .includes(query),
        )),
  );
  const text = records
    .map(
      (r) =>
        `${r.timestamp || r.date_group} · ${r.app}\n${r.formatted || r.cleaned || r.raw}`,
    )
    .join("\n\n---\n\n");
  const exportedText = `${state.demo ? "FICTIONAL SAMPLE WORKSPACE\n\n" : ""}${text}`;
  if (window.roastmyaudioDesktop) {
    try {
      await window.roastmyaudioDesktop.exportText(exportedText);
      toast("Export saved.");
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const url = URL.createObjectURL(
    new Blob([exportedText], {
      type: "text/plain;charset=utf-8",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `roastmyaudio-${state.demo ? "sample" : "thoughts"}.txt`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
hydrateIcons();
$("waveform").innerHTML = [
  10, 18, 28, 38, 23, 45, 32, 50, 35, 24, 38, 26, 17, 10,
]
  .map((h) => `<i style="--h:${h}px" data-height="${h}px"></i>`)
  .join("");
setTheme(
  storage.get("rma-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"),
);
$("scratchpad").value = "";
navigate(location.hash.slice(1), false);
document
  .querySelectorAll("[data-view]")
  .forEach((btn) =>
    btn.addEventListener("click", () => navigate(btn.dataset.view)),
  );
window.addEventListener("hashchange", () =>
  navigate(location.hash.slice(1), false),
);
$("themeBtn").onclick = () =>
  setTheme(
    document.documentElement.dataset.theme === "dark" ? "light" : "dark",
  );
$("menuBtn").onclick = () => {
  const open = $("sidebar").classList.toggle("open");
  $("menuBtn").setAttribute("aria-expanded", String(open));
};
document.addEventListener("click", (e) => {
  if (!e.target.closest(".sidebar") && !e.target.closest("#menuBtn")) {
    $("sidebar").classList.remove("open");
    $("menuBtn").setAttribute("aria-expanded", "false");
  }
});
$("helpBtn").onclick = () => openDialog("helpDialog");
$("privacyBtn").onclick = () => openDialog("privacyDialog");
document
  .querySelectorAll("[data-close-dialog]")
  .forEach((btn) => (btn.onclick = () => btn.closest("dialog").close()));
document.querySelectorAll("dialog").forEach((dialog) =>
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (
        e.clientX < rect.left ||
        e.clientX > rect.right ||
        e.clientY < rect.top ||
        e.clientY > rect.bottom
      )
        dialog.close();
    }
  }),
);
$("confirmCancel").onclick = () => $("confirmDialog").close();
document
  .querySelectorAll("[data-filter]")
  .forEach((btn) => (btn.onclick = () => selectFilter(btn.dataset.filter)));
$("searchInput").oninput = renderTimeline;
$("timeline").onclick = (e) => {
  const button = e.target.closest("[data-action]");
  if (button) handleThoughtAction(button);
};
$("exitDemoBtn").onclick = async () => {
  state.demo = false;
  state.recordings = [];
  $("demoBanner").hidden = true;
  selectFilter("all");
  $("timeline").setAttribute("aria-busy", "true");
  await refresh();
};
$("dictionaryForm").onsubmit = async (e) => {
  e.preventDefault();
  const word = $("newWord").value.trim();
  if (!word) return;
  const btn = e.submitter;
  btn.disabled = true;
  try {
    await post("/api/dictionary", { word });
    $("newWord").value = "";
    await loadDictionary();
    toast("Added to your vocabulary.");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
};
$("dictionaryList").onclick = async (e) => {
  const btn = e.target.closest("[data-word]");
  if (!btn) return;
  btn.disabled = true;
  try {
    await api(`/api/dictionary/${encodeURIComponent(btn.dataset.word)}`, {
      method: "DELETE",
    });
    await loadDictionary();
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
};
$("settingsForm").addEventListener("input", () => {
  settingsDirty = true;
});
$("settingsForm").onsubmit = async (e) => {
  e.preventDefault();
  const btn = e.submitter;
  btn.disabled = true;
  $("settingsStatus").textContent = "Saving…";
  try {
    await post("/api/settings", {
      model: $("modelSetting").value,
      language: $("languageSetting").value,
      llm_enabled: $("cleanupSetting").checked,
      llm_model: $("llmSetting").value,
      ...(state.desktop
        ? {
            hotkey: $("hotkeySetting").value,
            dictation_mode: $("modeSetting").value,
            context_awareness: $("contextSetting").checked,
            voice_commands: $("commandsSetting").checked,
            haptics_enabled: $("feedbackSetting").checked,
            device_id:
              $("deviceSetting").value === ""
                ? null
                : Number($("deviceSetting").value),
          }
        : {}),
    });
    settingsDirty = false;
    await loadSettings();
    $("settingsStatus").textContent = "Saved. Ready for your next thought.";
    toast("Preferences saved.");
  } catch (err) {
    $("settingsStatus").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
};
$("scratchpad").oninput = updateDraft;
$("copyDraftBtn").onclick = () => copy($("scratchpad").value);
$("clearDraftBtn").onclick = () => {
  if (!$("scratchpad").value) return;
  confirmAction(
    "Clear your draft?",
    "This clears your saved scratchpad on this computer. Your recording history is kept.",
    "Clear draft",
    () => {
      $("scratchpad").value = "";
      updateDraft();
    },
  );
};
$("copyResultBtn").onclick = () => copy($("resultText").textContent);
$("draftResultBtn").onclick = () => appendDraft($("resultText").textContent);
$("recordBtn").onclick = toggleRecord;
$("cancelRecordBtn").onclick = () => {
  if (state.desktop) {
    window.roastmyaudioDesktop
      .command("cancel")
      .then(applyDesktopState)
      .catch((error) => toast(error.message));
    return;
  }
  discarded = true;
  if (recorder?.state === "recording") recorder.stop();
};
$("exportBtn").onclick = exportHistory;
async function rewrite(retry) {
  const button = $(retry ? "retryBtn" : "transformBtn");
  button.disabled = true;
  try {
    const id = encodeURIComponent(state.activeId);
    const data = retry
      ? await post(`/api/retry_transcribe/${id}`, {
          model: $("retryModel").value,
          language: state.settings.language,
          run_llm: state.settings.llm_enabled,
          llm_model: state.settings.llm_model,
        })
      : await post(`/api/transform/${id}`, {
          transform: $("transformSelect").value,
          model: state.settings.llm_model,
        });
    if (data.recording.cleanup_applied === false && !retry)
      toast("Cleanup model unavailable. Your original words were kept.");
    else toast("Updated. Review your words before sharing.");
    $("recordingDialog").close();
    await refresh();
  } catch (err) {
    toast(err.message);
  } finally {
    button.disabled = false;
  }
}
$("transformBtn").onclick = () => rewrite(false);
$("retryBtn").onclick = () => rewrite(true);
document.addEventListener("keydown", (e) => {
  const editing = e.target.matches("input,textarea,select,[contenteditable]");
  const modal = document.querySelector("dialog[open]");
  if (e.altKey && e.code === "KeyD" && !e.repeat && !modal) {
    e.preventDefault();
    navigate("dictation");
    toggleRecord();
    return;
  }
  if (editing || modal || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "/") {
    e.preventDefault();
    navigate("dictation");
    $("searchInput").focus();
  }
  if (e.key === "?") {
    e.preventDefault();
    openDialog("helpDialog");
  }
});
window.addEventListener("beforeunload", (e) => {
  if (state.phase !== "idle" || pendingAudio) {
    e.preventDefault();
    e.returnValue = "";
  }
});
window.addEventListener("focus", () => {
  if (!settingsDirty && state.phase === "idle") loadSettings();
});
window.addEventListener("rma-workspace-closing", () => {
  if (state.desktop && state.desktopState?.phase === "recording")
    window.roastmyaudioDesktop
      .command("stop")
      .then(applyDesktopState)
      .catch((error) => toast(error.message));
  if (state.phase === "requesting") discarded = true;
  if (recorder?.state === "recording") recorder.stop();
});
window.addEventListener("rma-workspace-shutdown", () => {
  discarded = true;
  if (recorder?.state === "recording") recorder.stop();
  releaseMic();
});
loadSettings();
loadDictionary();
loadWorkspace();
loadPersonalization();
refresh();
if (state.desktop)
  window.roastmyaudioDesktop
    .command("state")
    .then(applyDesktopState)
    .catch((error) => toast(error.message));
setInterval(refresh, 5000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});

let lastDesktopResult = "";
let practiceComplete = false;
function applyDesktopState(snapshot) {
  if (!snapshot?.phase) return;
  state.desktopState = snapshot;
  if (snapshot.settings) state.settings = snapshot.settings;
  const phase =
    snapshot.phase === "preparing"
      ? "processing"
      : snapshot.phase === "error"
        ? "idle"
        : snapshot.phase;
  setPhase(phase);
  $("recordTimer").textContent = duration(snapshot.seconds || 0);
  $("recordState").textContent = snapshot.message;
  $("setupProgress").textContent = snapshot.error || snapshot.message;
  $("prepareModelBtn").disabled = [
    "recording",
    "processing",
    "preparing",
  ].includes(snapshot.phase);
  $("practiceBtn").disabled =
    ["processing", "preparing"].includes(snapshot.phase) ||
    snapshot.permissions?.microphone !== "granted";
  $("practiceBtn").textContent =
    snapshot.phase === "recording"
      ? "Finish practice"
      : "Try a practice dictation";
  for (const key of ["microphone", "accessibility", "input_monitoring"]) {
    const value = snapshot.permissions?.[key];
    const enabled = value === true || value === "granted";
    document.querySelector(`[data-permission-status="${key}"]`).textContent =
      enabled
        ? "Allowed"
        : value === "denied"
          ? "Declined — enable in System Settings"
          : "Not enabled";
    document.querySelector(`[data-permission="${key}"]`).disabled = enabled;
  }
  $("loginSetting").disabled = !snapshot.login?.available;
  $("loginSetting").checked = Boolean(snapshot.login?.enabled);
  $("loginHint").textContent = snapshot.login?.requires_approval
    ? "Approve RoastMyAudio in System Settings → General → Login Items."
    : snapshot.login?.message ||
      "Start quietly in the menu bar when you sign in.";
  document.querySelectorAll("#waveform i").forEach((bar, i) => {
    if (phase === "recording")
      bar.style.height = `${6 + (snapshot.level || 0) * (20 + (i % 4) * 8)}px`;
  });
  if (
    snapshot.text &&
    `${snapshot.recording_id}:${snapshot.text}` !== lastDesktopResult
  ) {
    lastDesktopResult = `${snapshot.recording_id}:${snapshot.text}`;
    $("resultText").textContent = snapshot.text;
    $("sessionResult").hidden = false;
    $("copyResultBtn").disabled = $("draftResultBtn").disabled = false;
    if ($("setupDialog").open && snapshot.practice) {
      practiceComplete = true;
      $("practiceResult").textContent = snapshot.text;
      $("finishSetupBtn").disabled = false;
    }
    refresh();
  }
  if (snapshot.error) {
    $("sessionResult").hidden = false;
    $("resultText").textContent = snapshot.error;
    $("copyResultBtn").disabled = $("draftResultBtn").disabled = true;
  }
  $("retryNativeBtn").hidden = !snapshot.can_retry;
  $("discardNativeBtn").hidden = !snapshot.can_retry;
}
window.addEventListener("rma-session", (event) =>
  applyDesktopState(event.detail),
);
window.addEventListener("rma-insertion", (event) =>
  toast(event.detail.message),
);
$("retryNativeBtn").onclick = () =>
  window.roastmyaudioDesktop
    .command("retry")
    .then(applyDesktopState)
    .catch((error) => toast(error.message));
$("discardNativeBtn").onclick = () =>
  window.roastmyaudioDesktop
    .command("cancel")
    .then(applyDesktopState)
    .catch((error) => toast(error.message));
document.querySelectorAll("[data-permission]").forEach(
  (button) =>
    (button.onclick = async () => {
      try {
        await window.roastmyaudioDesktop.command("permission", {
          kind: button.dataset.permission,
        });
      } catch (error) {
        toast(error.message);
      }
    }),
);
$("prepareModelBtn").onclick = () =>
  window.roastmyaudioDesktop
    .command("prepare")
    .then(applyDesktopState)
    .catch((error) => toast(error.message));
$("practiceBtn").onclick = toggleRecord;
$("finishSetupBtn").onclick = async () => {
  if (!practiceComplete) return;
  try {
    await window.roastmyaudioDesktop.command("onboarding");
    $("setupDialog").close();
  } catch (error) {
    toast(error.message);
  }
};
$("skipSetupBtn").onclick = () => $("setupDialog").close();
$("reopenSetupBtn").onclick = () => openDialog("setupDialog");
$("diagnosticsBtn").onclick = () =>
  window.roastmyaudioDesktop
    .command("diagnostics")
    .then((result) => {
      if (result.saved)
        toast("Diagnostics exported without transcripts or clipboard content.");
    })
    .catch((error) => toast(error.message));
$("updatesBtn").onclick = () =>
  window.roastmyaudioDesktop
    .command("updates")
    .catch((error) => toast(error.message));
$("loginSetting").onchange = () =>
  window.roastmyaudioDesktop
    .command("login", { enabled: $("loginSetting").checked })
    .catch((error) => toast(error.message));
$("refreshDevicesBtn").onclick = async () => {
  try {
    const devices = await window.roastmyaudioDesktop.command("devices");
    $("deviceSetting").replaceChildren(
      new Option("System default", ""),
      ...devices.map((device) => new Option(device.name, String(device.id))),
    );
    $("deviceSetting").value =
      state.settings.device_id == null ? "" : String(state.settings.device_id);
  } catch (error) {
    toast(error.message);
  }
};
document
  .querySelectorAll(".desktop-only")
  .forEach((element) => (element.hidden = !state.desktop));
if (state.desktop) $("refreshDevicesBtn").click();
let library = { corrections: [], snippets: [], app_styles: [] };
async function loadPersonalization() {
  try {
    library = await api("/api/personalization");
    renderPersonalization();
  } catch {
    $("libraryStatus").textContent = "Personalization couldn't load.";
  }
}
function renderPersonalization() {
  $("libraryList").replaceChildren();
  for (const [group, rows] of Object.entries(library))
    rows.forEach((row, index) => {
      const item = document.createElement("div");
      item.className = "library-entry";
      const label = document.createElement("span");
      label.textContent = `${group === "corrections" ? "Correction" : group === "snippets" ? "Snippet" : "App style"}: ${Object.values(row).join(" → ")}`;
      const remove = document.createElement("button");
      remove.className = "text-button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${Object.values(row)[0]}`);
      remove.onclick = async () => {
        const updated = structuredClone(library);
        updated[group].splice(index, 1);
        try {
          library = await post("/api/personalization", updated);
          renderPersonalization();
        } catch (error) {
          toast(error.message);
        }
      };
      item.append(label, remove);
      $("libraryList").append(item);
    });
}
$("libraryForm").onsubmit = async (event) => {
  event.preventDefault();
  const group = $("libraryType").value,
    first = $("libraryTrigger").value.trim(),
    second = $("libraryText").value.trim();
  const fields =
    group === "corrections"
      ? ["heard", "write"]
      : group === "snippets"
        ? ["trigger", "text"]
        : ["app", "style"];
  const updated = structuredClone(library);
  updated[group].push({ [fields[0]]: first, [fields[1]]: second });
  try {
    library = await post("/api/personalization", updated);
    renderPersonalization();
    $("libraryTrigger").value = $("libraryText").value = "";
    $("libraryStatus").textContent = "Saved. Applies to your next dictation.";
  } catch (error) {
    $("libraryStatus").textContent = error.message;
  }
};
