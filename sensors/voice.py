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

    Uses Vosk for offline speech recognition.
    """
    # TODO: Implement voice recognition:
    #   1. import vosk, sounddevice, json
    #   2. Load Vosk model: vosk.Model("models/vosk/vosk-model-small-en-us-0.15")
    #   3. Create recognizer: vosk.KaldiRecognizer(model, 16000)
    #   4. Open RawInputStream(samplerate=16000, blocksize=4000,
    #                          dtype="int16", channels=1)
    #   5. Loop while system_running.value:
    #      - data = stream.read(4000)[0]
    #      - if recognizer.AcceptWaveform(bytes(data)):
    #          result = json.loads(recognizer.Result())
    #          text = result.get("text", "").lower()
    #          for keyword, cmd in KEYWORDS.items():
    #              if keyword in text:
    #                  voice_command.value = cmd
    #                  break
    raise NotImplementedError
