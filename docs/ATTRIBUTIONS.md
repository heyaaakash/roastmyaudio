# Attribution and rights

The repository retains its existing [MIT license](../LICENSE). Aakash must confirm publication rights for the complete history before release. No new claim about authorship of prior commits is made.

| Component | Purpose | Upstream |
| --- | --- | --- |
| faster-whisper | Local speech inference | https://github.com/SYSTRAN/faster-whisper |
| Whisper | Underlying speech models | https://github.com/openai/whisper |
| CTranslate2 | Inference backend | https://github.com/OpenNMT/CTranslate2 |
| PyAV / FFmpeg | Audio decoding | https://github.com/PyAV-Org/PyAV |
| Flask / Werkzeug / Jinja | Web server and templates | https://palletsprojects.com/ |
| NumPy / SciPy / sounddevice | Audio/data handling | https://numpy.org/ · https://scipy.org/ · https://python-sounddevice.readthedocs.io/ |
| PyObjC / rumps / pynput | Optional native macOS integration | https://pyobjc.readthedocs.io/ · https://github.com/jaredks/rumps · https://github.com/moses-palmer/pynput |
| ONNX Runtime / tokenizers / Hugging Face Hub | Speech preprocessing and model downloads | https://github.com/microsoft/onnxruntime · https://github.com/huggingface/tokenizers · https://github.com/huggingface/huggingface_hub |
| PyInstaller | Local Mac runtime bundling | https://pyinstaller.org/en/stable/license.html |
| llama-cpp-python | Optional local cleanup | https://github.com/abetlen/llama-cpp-python |
| Qwen / SmolLM2 | Optional downloaded GGUF models | https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF · https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF |

Dependencies/models carry their own licenses and conditions; review the exact resolved versions and model files for a chosen distribution. The source archive does not bundle third-party libraries or weights. The local ad-hoc bundle contains third-party libraries. Public binary redistribution remains gated on an exact dependency/native-library license audit and complete notices, including Python, libffi, OpenMP, PortAudio, and FFmpeg components selected by the wheels. PyInstaller provides a bundling exception; dependency license obligations still apply (see its linked license documentation). No model weights are bundled.

The waveform icon, interface SVGs, and CSS orb are repository-native artwork created for this interface. System fonts are used; no downloaded font assets. Screenshots depict the actual UI with fictional examples. Wispr Flow is a presentation-quality reference, with no copied logos, artwork, screenshots, or affiliation. Third-party names remain their owners’ marks.
