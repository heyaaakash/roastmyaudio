# Whisper Web MVP

A minimal one-page web app for speech-to-text using Whisper.

## Features
- Single record button
- Browser microphone recording
- Dropdown to choose from locally installed Whisper models
- Audio saved to a temporary folder outside the project
- Whisper transcription returned on the page

## Run

```bash
cd /Users/isd0605/Documents/Github/openai-whsiper
/Users/isd0605/Documents/Github/openai-whsiper/.venv/bin/python web_mvp/app.py
```

Then open http://127.0.0.1:5000 in your browser and allow microphone access.

## Temp Storage
Uploaded recordings are written to:

- `/Users/isd0605/Documents/Github/openai-whsiper/web_mvp/temp_uploads`

They are now stored inside the `web_mvp` folder.

## Product Documentation
- Post-conversion layer brief for PM: `web_mvp/docs/post_conversion_layer.md`
