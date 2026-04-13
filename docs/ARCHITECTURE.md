# 📐 Architecture & Design

Technical deep-dive into WhisperFlow's architecture, module organization, and data flow.

## 🎯 Design Principles

1. **Self-Contained**: All dependencies, models, and data stored within the project directory
2. **Dual-Platform**: Shared core logic used by both macOS menu bar app and web interface
3. **Relative Paths**: No hardcoded absolute paths — works on any machine
4. **Modular**: Reusable utilities in `src/shared/` for both platforms
5. **Configurable**: Centralized settings in `config/config.py`
6. **Performance**: Local caching, model warmup, live preview for responsiveness
7. **Privacy First**: No external API calls, no telemetry, all data stays local

## 🌉 Dual-Platform Architecture

WhisperFlow runs in two modes using **identical transcription logic**:

### macOS Menu Bar App (`src/apps/macos/`)
- **Input**: Global hotkey listener (Fn key)
- **Processing**: Shared transcription modules
- **Output**: Text injected via Cmd+V into any app
- **UI**: Native macOS menu bar + overlay

### Web App (`src/apps/web/`)
- **Input**: Browser microphone (cross-platform)
- **Processing**: Shared transcription modules
- **Output**: Text displayed in browser, user copies
- **UI**: HTML5 web interface (responsive, mobile-friendly)

### Shared Core (`src/shared/`)

Both apps use identical modules for:
- **Transcription** (`transcriber.py`) — Whisper inference
- **Formatting** (`formatter.py`) — Spoken command parsing, punctuation
- **Cleanup** (`llm_cleanup.py`) — Optional Ollama grammar fix
- **History** (`history.py`) — Log recent transcriptions
- **Dictionary** (`dictionary.py`) — Custom terminology
- **Config** (`settings.py`) — Per-user preferences
- **Text Injection** (`text_injector.py`) — macOS-specific clipboard paste

This ensures both platforms produce **identical results** for the same audio input.

## 🗂️ Module Organization

### `config/` — Configuration Management

**`config.py`** — Single source of truth for all settings

```python
- Paths: PROJECT_ROOT, CACHE_DIR, MODELS_CACHE_DIR, TEMP_UPLOADS_DIR
- Models: DEFAULT_MODEL, AVAILABLE_MODELS, MODEL_DISPLAY_ORDER
- Ollama: OLLAMA_URL, OLLAMA_MODEL
- macOS: SAMPLE_RATE, LIVE_PREVIEW_INTERVAL_SEC, FALLBACK_HOLD_HOTKEY
```

**Key insight**: Environment variables set here override system defaults, ensuring project-local cache even if `~/.cache` environment vars exist elsewhere.

### `src/shared/` — Reusable Modules

Shared utilities used by both macOS and web apps.

#### `dictionary.py` — Custom Word Dictionary

**Purpose**: User-defined terminology for domain-specific transcription

```python
load()          # Returns: list[str]
add(word)       # Add word to dictionary
remove(word)    # Remove word
as_prompt()     # Format for Whisper's initial_prompt
```

**Storage**: `data/dictionary.json`

```json
{
  "words": ["Kubernetes", "AWS", "GraphQL", ...]
}
```

**Integration**: Whisper's `initial_prompt` parameter guides model toward these terms.

#### `history.py` — Transcription History Log

**Purpose**: Keep a record of recent transcriptions for reference

```python
save(raw, cleaned, app, latency_ms)  # Record entry
load()                                # Retrieve all entries
latest()                              # Get most recent
```

**Storage**: `data/history.json` (max 5 entries)

```json
[
  {
    "timestamp": "2025-04-05T10:30:00",
    "app": "mail",
    "raw": "um schedule meeting for next thursday",
    "cleaned": "Schedule meeting for next Thursday.",
    "latency_ms": 450
  },
  ...
]
```

#### `llm_cleanup.py` — Ollama LLM Integration

**Purpose**: Optional advanced text cleanup using local LLM

```python
clean(raw_text, app_name)  # Returns: (cleaned_text, latency_ms)
warmup()                   # Pre-load model at startup
```

**Flow**:

1. Build prompt with tone context (mail → formal, slack → casual)
2. Send to local Ollama server via HTTP
3. Detect and filter meta-commentary, refusals
4. Compare word overlap to detect rewrites (fallback to raw if <70%)
5. Return cleaned text or raw fallback

**Configuration**: `config.py`

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"  # Fast, lightweight
```

**Graceful degradation**: If Ollama unavailable, returns raw text with no error.

#### `text_injector.py` — macOS Text Injection

**Purpose**: Insert transcribed text into focused app via Cmd+V

```python
inject(text, app_name)      # Returns: (success: bool, reason: str)
get_active_app()            # Get frontmost app name
class AppMonitor             # Track app in background
```

**Flow**:

1. Check if app is "pasteable" (not Finder, Settings, etc.)
2. Save current clipboard
3. Write transcribed text to clipboard
4. Simulate Cmd+V
5. Restore original clipboard

**Failure detection**: Pre-flight checks to avoid pasting in unsupported apps.

### `src/apps/web/` — Flask Web Application

#### `app.py` — Main Web Server

**Purpose**: Browser-based speech-to-text interface

**Key functions**:

```python
GET /                       # Serve HTML UI
GET /models                 # List available models
POST /transcribe            # Full transcription
POST /transcribe_partial    # Live preview
```

**Transcription flow**:

1. Receive audio from browser
2. Load model (cached in memory)
3. Run Whisper inference
4. Filter hallucinations
5. Format text (spoken commands, lists, etc.)
6. Save to history
7. Return JSON response

**Text formatting pipeline**:

```
Raw transcript
    ↓ [_filter_hallucinations]
    ↓ [format_transcript]
        ↓ [_apply_spoken_commands] - "new line" → "\n"
        ↓ [_format_ordinal_steps] - "first ... second ..." → numbered list
        ↓ [_normalize_structured_text] - spacing, caps, punctuation
        ↓ [_normalize_numbered_lists] - fix numbering gaps
    ↓ Formatted text
```

**Models**: Supports all Whisper models, downloads on demand to `cache/models/`

#### `warmup.py` — Model Pre-loading

**Purpose**: Load models into GPU/CPU at startup for fast inference

```python
load_models_async(on_complete)  # Background thread
```

Loads:
1. Primary model (base) for main transcription
2. Preview model (tiny.en) for live preview
3. Ollama model for text cleanup (if available)

This trades startup latency for responsive inference.

#### `templates/` & `static/` — Frontend

**`index.html`** — Single-page web app interface

Features:
- Model selector dropdown
- Record/stop button with live preview
- Formatted vs. raw view toggle
- Local browser storage for history

**`app.js`** — Client-side logic

```
Event: Click record → getUserMedia() → start MediaRecorder
Event: Key release → Send rolling audio buffer to /transcribe_partial
Event: Stop → Send full audio to /transcribe → Update UI
```

**`styles.css`** — Responsive CSS with dark/light theme

### `src/apps/macos/` — macOS Menu Bar Application

#### `menubar_dictation.py` — Main App Entry Point

**Purpose**: Global hotkey detection and menu bar interface

**Key components**:

```python
LIVE_PREVIEW_INTERVAL_SEC = 0.6    # Update HUD every 600ms
LIVE_PREVIEW_WINDOW_SEC = 2.0      # Show last 2 seconds of audio
PTT_STATE_POLL_SEC = 0.12          # Check Fn key every 120ms
PTT_MAX_HOLD_SEC = 300             # Auto-stop after 5 minutes
```

**Flow**:

1. Register global hotkey listener (Fn or fallback Ctrl+Option+D)
2. When key held:
   - Start audio recording at 16kHz mono
   - Show HUD overlay at bottom center
   - Update live preview every 600ms
3. When key released:
   - Stop recording
   - Run Whisper transcription
   - Optionally run LLM cleanup
   - Inject text into focused app
   - Save to history

**Audio processing**:

```python
SAMPLE_RATE = 16000  # Whisper standard
CHANNELS = 1         # Mono
VOC_MODEL = "silero_vad"  # Voice Activity Detection
```

Uses Silero VAD to trim silence before Whisper, saving latency.

**Menu items**:

```
🔴 W/R (icon status)
├─ Copy Last Processed
├─ Paste Last Processed
├─ Open macOS Permissions
└─ Test Overlay (2s)
```

#### `warmup.py` — Model Warmup (for macOS)

Pre-loads models at app startup to eliminate first-transcription latency.

### `scripts/` — Utility Scripts

#### `setup.sh` — macOS-specific Setup

Handles:
- Xcode Command Line Tools check
- Framework verification
- Permission prompts
- Model pre-download (optional)

#### `download_models.py` — Model Download Utility

Downloads Whisper models to `cache/models/`

```bash
python3 scripts/download_models.py -m base tiny.en
python3 scripts/download_models.py -m all  # All models
```

## 📊 Data Flow Diagrams

### Web App Flow

```
User (browser)
    ↓ [record audio via browser]
    ↓ POST /transcribe
Flask App
    ↓ [receive audio blob]
    ↓ [load model from cache]
    ↓ [run Whisper.transcribe()]
    ↓ [_filter_hallucinations()]
    ↓ [format_transcript()]
    ↓ [save_history()]
    ↓ [return JSON]
User (browser)
    ↓ [display formatted text]
```

### macOS App Flow

```
User Hold Fn
    ↓
HID event listener
    ↓ [pynput detects Fn press]
    ↓ [start audio recording at 16kHz]
    ↓ [show overlay HUD]
    ↓
User Release Fn
    ↓
Process Audio
    ↓ [trim silence with VAD]
    ↓ [run Whisper]
    ↓ [LLM cleanup (optional)]
    ↓ [detect active app]
    ↓ [inject text via Cmd+V]
    ↓ [save history]
```

### LLM Cleanup Optional Flow

```
Raw Transcript
    ↓ [llm_cleanup.clean()]
    ↓ [build Ollama prompt with tone]
    ↓ POST http://localhost:11434/api/generate
Ollama Server
    ↓ [load llama3.2:1b from local cache]
    ↓ [generate cleaned text]
    ↓ [return response]
    ↓ [detect meta-commentary]
    ↓ [compare word overlap]
    ↓ [fallback to raw if needed]
Cleaned Transcript
```

## 🔄 Cache Management

### Directory Structure

```
cache/
├── models/                      # Whisper model files
│   ├── tiny.en.pt              # ~40MB
│   ├── base.pt                 # ~140MB
│   └── ... (other models)
├── cache/                       # HuggingFace artifacts
│   ├── huggingface/
│   └── ... (tokenizers, configs)
```

### Initialization Flow

1. **App startup** → `config.py` loads
2. **Environment variables set**:
   ```python
   os.environ['HF_HOME'] = str(HUGGINGFACE_CACHE_DIR)
   ```
3. **First model access** → Whisper checks cache, downloads if missing
4. **Models stored locally** → Inside `cache/` directory

### Model Download Behavior

- **First access**: Auto-download to `cache/models/`
- **Subsequent access**: Load from cache (instant)
- **Size**: ~100MB (tiny) to ~1.5GB+ (large models)

## ⚙️ Performance Optimizations

### 1. Model Caching (In-Memory)

```python
MODEL_CACHE = {}  # Dict[model_name -> model_object]
MODEL_CACHE_LOCK = threading.Lock()
```

Once loaded, models stay in GPU/CPU memory. Subsequent inferences use cached model (no reload).

### 2. Model Inference Locks

```python
MODEL_INFERENCE_LOCKS = {}  # Dict[model_name -> threading.Lock]
```

Prevents concurrent inference on same model (Whisper not thread-safe). Requests queue.

### 3. Live Preview Model Selection

Uses smallest suitable model for low-latency preview:

```python
LIVE_PREVIEW_MODEL_PREFERENCE = ("tiny.en", "tiny", "base.en", "base")
```

Preview runs in background while main transcription completes.

### 4. Warmup at Startup

Pre-load models on app launch → first real transcription is instant.

### 5. Audio Processing

- **VAD (Voice Activity Detection)**: Trim silence before Whisper (faster)
- **Chunk processing**: Send audio in small chunks for responsiveness
- **Hardware acceleration**: Use MPS on Apple Silicon (`torch.backends.mps`)

## 🔐 Security & Privacy

### No External Calls

- ✅ Models cached locally
- ✅ Transcription runs locally
- ✅ Text formatting runs locally
- ✅ Only optional: Ollama (runs on localhost)
- ❌ No cloud services or APIs

### Data Storage

- Dictionary: `data/dictionary.json` (local directory)
- History: `data/history.json` (local directory)
- Temp uploads: `data/temp_uploads/` (local directory)
- Models: `cache/models/` (local directory)

All within project folder, never in system directories.

## 🧪 Testing

### Web App Testing

```bash
# Test transcription
python3 -c "from src.apps.web.app import format_transcript; print(format_transcript('um hello world'))"

# Test history
from src.shared.history import save, load
save("raw text", "formatted", "test", 100)
print(load())
```

### macOS App Testing

```bash
# Test text injection (requires manual trigger)
from src.shared.text_injector import inject
success, msg = inject("Hello World")
print(f"Injected: {success} - {msg}")
```

### Model Availability

```bash
python3 -c "import whisper; print(whisper.available_models())"
```

## 📈 Scaling Considerations

### Memory Usage

- **Each model**: 100MB-2GB depending on size
- **Audio buffer**: ~32MB for 5 minutes
- **Typical system**: 4GB RAM sufficient with small models

### Disk Usage

- **Tiny model**: ~40MB
- **Base model**: ~140MB
- **Base model**: ~140MB
- **Total best case**: ~2GB

### Latency Targets

| Operation | Target | Actual |
|-----------|--------|--------|
| Model load | First time | ~3-10s (download) |
| Model load | Cached | <1s |
| Warmup | Startup | ~5-10s |
| Transcribe (base) | 1 min audio | ~2-5s |
| LLM cleanup | Avg | ~1-3s |
| Text inject | OS call | ~50ms |

## 🔮 Future Enhancements

1. **Streaming transcription** — Real-time output as user speaks
2. **Model selection UI** — Dynamic model picker with disk/speed tradeoffs
3. **Batch processing** — Transcribe multiple files
4. **Webhook export** — Send transcripts to external services
5. **Cloud sync** — Optional backup to external storage

---

**Architecture is designed for**: stability, performance, privacy, and zero external dependencies.
