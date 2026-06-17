"""
sensors/voice.py — Voice command recognition using Vosk.

Part of Process 3 (Core 2). Listens for keywords and writes
voice_command to shared memory.

Library: Vosk (offline, ~40MB model, runs on Pi 4 CPU).
Install: pip install vosk sounddevice
Model:   https://alphacephei.com/vosk/models → vosk-model-small-en-us-0.15
"""

from multiprocessing import Value
from contracts import VoiceCommand


# Keywords to detect
KEYWORDS = {
    "start": VoiceCommand.START,
    "stop": VoiceCommand.STOP,
    "pause": VoiceCommand.PAUSE,
    "continue": VoiceCommand.CONTINUE,
}


def voice_listener(voice_command: Value, system_running: Value) -> None:
    """
    Listens for voice commands and updates shared memory.
    Gracefully falls back to a dummy loop if packages, microphone, or model are missing.
    """
    import time

    try:
        import vosk
        import sounddevice as sd
        import json
        import os

        # Locate the model (look in models/vosk/)
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "vosk", "vosk-model-small-en-us-0.15")
        if not os.path.exists(model_path):
            # Try path from current working directory as fallback
            model_path = "models/vosk/vosk-model-small-en-us-0.15"

        if not os.path.exists(model_path):
            print(f"⚠️ [Voice] Model not found at '{model_path}'. Voice commands will be inactive.")
            print("    To resolve, download the model from https://alphacephei.com/vosk/models")
            print("    and extract it to: BIP-Heidelberg-Team-C/models/vosk/vosk-model-small-en-us-0.15")
            raise FileNotFoundError("Vosk model directory missing")

        model = vosk.Model(model_path)
        recognizer = vosk.KaldiRecognizer(model, 16000)
        
        print("🎙️ [Voice] Speech recognition initialized successfully. Listening for: START, STOP, PAUSE, CONTINUE...")

        # Setup sounddevice input stream
        with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16", channels=1) as stream:
            while system_running.value:
                data, overflow = stream.read(4000)
                if overflow:
                    pass
                
                # Run speech recognition on raw bytes
                if recognizer.AcceptWaveform(bytes(data)):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").lower()
                    
                    for keyword, cmd in KEYWORDS.items():
                        if keyword in text:
                            print(f"🎙️ [Voice] Recognized command: {keyword.upper()}")
                            voice_command.value = cmd
                            break
                            
    except Exception as e:
        print(f"⚠️ [Voice] Voice listener disabled: {e}")
        # Keep process alive and responsive to kill switch
        while system_running.value:
            time.sleep(0.5)
