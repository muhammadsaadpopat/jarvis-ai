# voice_engine_natural.py
"""Natural Voice Engine using pyttsx3.

Provides a robust, thread-safe, queue-based Text-to-Speech (TTS) interface
suitable for multi-threaded applications like Streamlit and sounddevice recording.
"""

import pyttsx3
import queue
import threading
import time
from logger import logger
from config import Config

_speech_queue = queue.Queue()
_is_speaking = False
_engine = None

def _tts_worker():
    global _engine, _is_speaking
    try:
        _engine = pyttsx3.init()
    except Exception as e:
        logger.error(f"Failed to initialize pyttsx3: {e}")
        return
        
    while True:
        try:
            task = _speech_queue.get(timeout=0.1)
            if task is None:
                break
            action, data = task
            if action == "speak":
                text, rate, gender = data
                _is_speaking = True
                
                # Apply rate
                if rate is not None:
                    _engine.setProperty('rate', rate)
                else:
                    try:
                        voice_rate = int(Config.get("voice_rate", 185))
                        if voice_rate < 20: # Map SAPI -10 to 10 scale to pyttsx3
                            voice_rate = 185 + (voice_rate * 10)
                        _engine.setProperty('rate', voice_rate)
                    except Exception:
                        _engine.setProperty('rate', 185)
                        
                # Apply gender/voice
                voices = _engine.getProperty('voices')
                chosen_voice = None
                for voice in voices:
                    desc = voice.name.lower()
                    if gender == "female" and "zira" in desc:
                        chosen_voice = voice.id
                        break
                    elif gender == "male" and "david" in desc:
                        chosen_voice = voice.id
                        break
                if not chosen_voice and voices:
                    chosen_voice = voices[0].id
                if chosen_voice:
                    _engine.setProperty('voice', chosen_voice)
                
                _engine.say(text)
                _engine.runAndWait()
                _is_speaking = False
            elif action == "stop":
                _engine.stop()
                _is_speaking = False
            _speech_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error in TTS worker: {e}")
            _is_speaking = False

# Start the worker thread automatically
_worker_thread = threading.Thread(target=_tts_worker, daemon=True)
_worker_thread.start()

def speak(text: str, rate=None, gender=None) -> None:
    """Thread-safe call to speak a line of text."""
    if gender is None:
        gender = Config.get("voice_gender", "male")
    if rate is None:
        try:
            cfg_rate = Config.get("voice_rate", 185)
            rate = int(cfg_rate)
            if rate < 20:
                rate = 185 + (rate * 10)
        except Exception:
            rate = 185
    _speech_queue.put(("speak", (text, rate, gender)))

def is_speaking() -> bool:
    """Check if the speech worker is currently speaking."""
    return _is_speaking

def stop_speaking() -> None:
    """Stop any active speech."""
    # Clear the queue
    while not _speech_queue.empty():
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except queue.Empty:
            break
    _speech_queue.put(("stop", None))

def set_voice_character(gender="male"):
    """Set standard voice gender."""
    Config.set("voice_gender", gender)
