import streamlit as st
import threading
import time
import psutil
import os
from dotenv import load_dotenv
load_dotenv()
import voice_engine
import speech_recognition as sr
import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import queue

# Active Session Monitoring (Auto-shutdown instantly when the browser tab/websocket is closed)
from streamlit.runtime import runtime
def monitor_sessions():
    time.sleep(5)  # Give time for initial tab load
    while True:
        try:
            sessions = runtime.get_instance()._session_info_by_id
            active_websocket = False
            for s_info in sessions.values():
                if hasattr(s_info, "session") and getattr(s_info.session, "_websocket_connection", None) is not None:
                    active_websocket = True
                    break
            
            # If the session list is populated, but there are no active websocket connections, the tab has been closed!
            if len(sessions) > 0 and not active_websocket:
                print("[SYSTEM] Active browser tab disconnected. Auto-shutting down JARVIS Voice Engine backend...")
                os._exit(0)
            elif len(sessions) == 0:
                print("[SYSTEM] Edge/Browser tab closed. Auto-shutting down JARVIS Voice Engine backend...")
                os._exit(0)
        except Exception:
            pass
        time.sleep(1)  # Active checking every 1 second



if "session_monitor_started" not in st.session_state:
    st.session_state.session_monitor_started = True
    threading.Thread(target=monitor_sessions, daemon=True).start()

# Parse query parameter for widget mode
params = st.query_params
is_widget = params.get("widget", "false").lower() == "true"

# Page Config
st.set_page_config(
    page_title="J.A.R.V.I.S. OS",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Sleek Cyberpunk/Iron Man CSS Theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    
    /* Main container styling - Ultra Clean Dark Theme */
    .stApp {
        background-color: #040508;
        background-image: radial-gradient(circle at 50% 0%, #170720 0%, #03050c 60%, #000 100%);
        color: #f8f9fa;
        font-family: 'Outfit', -apple-system, sans-serif;
    }
    
    /* Sleek Premium Header */
    .header-box {
        text-align: center;
        padding: 40px 20px;
        background: rgba(15, 10, 25, 0.4);
        border: 1px solid rgba(255, 0, 60, 0.15);
        border-radius: 24px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        margin-bottom: 35px;
        position: relative;
    }
    
    .header-title {
        color: #fff;
        font-size: 3.5em;
        font-weight: 800;
        letter-spacing: 4px;
        margin: 0;
        text-transform: uppercase;
        background: linear-gradient(135deg, #ffffff 0%, #ff003c 50%, #bd00ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .header-subtitle {
        color: #8ab4f8;
        font-size: 1.1em;
        font-weight: 400;
        margin-top: 12px;
        letter-spacing: 3px;
        text-transform: uppercase;
        opacity: 0.8;
    }
    
    /* Clean Telemetry Cards */
    .telemetry-card {
        background: linear-gradient(180deg, rgba(20, 10, 30, 0.6) 0%, rgba(10, 5, 20, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(12px);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease;
    }
    .telemetry-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 40px rgba(255, 0, 60, 0.1);
        border: 1px solid rgba(255, 0, 60, 0.2);
    }
    .telemetry-val {
        font-size: 2.5em;
        color: #ffffff;
        font-weight: 700;
        margin-top: 12px;
        text-shadow: 0 0 20px rgba(255, 0, 60, 0.3);
    }
    .telemetry-label {
        color: #94a3b8;
        font-size: 0.9em;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }

    /* Accent Cards */
    .threat-card {
        background: linear-gradient(180deg, rgba(42, 15, 20, 0.6) 0%, rgba(30, 10, 15, 0.8) 100%);
    }
    .threat-card .telemetry-val { color: #ff4d4d; text-shadow: 0 0 20px rgba(255, 77, 77, 0.3); }
    .threat-card:hover { border-color: rgba(255, 77, 77, 0.3); box-shadow: 0 20px 40px rgba(255, 77, 77, 0.1); }

    .neural-card {
        background: linear-gradient(180deg, rgba(15, 28, 42, 0.6) 0%, rgba(10, 20, 30, 0.8) 100%);
    }
    .neural-card .telemetry-val { color: #0052ff; text-shadow: 0 0 20px rgba(0, 82, 255, 0.3); }
    .neural-card:hover { border-color: rgba(0, 82, 255, 0.3); box-shadow: 0 20px 40px rgba(0, 82, 255, 0.1); }
    
    /* Central Visualizer - Arc Reactor Styled */
    .visualizer-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 220px;
        background: rgba(10, 10, 20, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 30px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        margin: 15px 0;
        position: relative;
        backdrop-filter: blur(16px);
    }
    
    /* Standby: Elegant Arc Reactor */
    .orb-standby {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(230,0,60,0.15) 0%, rgba(0,82,255,0.4) 60%, rgba(189,0,255,0.85) 100%);
        box-shadow: 0 0 45px rgba(189, 0, 255, 0.5), inset 0 0 20px rgba(0, 82, 255, 0.6);
        position: relative;
        animation: spinReactor 6s linear infinite;
    }
    .orb-standby::before {
        content: '';
        position: absolute;
        top: 8px; left: 8px; right: 8px; bottom: 8px;
        border-radius: 50%;
        border: 3px dashed #ff003c;
        animation: spinCounter 4s linear infinite;
    }
    .orb-standby::after {
        content: '';
        position: absolute;
        top: 22px; left: 22px; right: 22px; bottom: 22px;
        border-radius: 50%;
        background: radial-gradient(circle, #ffffff 0%, #0052ff 60%, transparent 100%);
        box-shadow: 0 0 25px rgba(0, 82, 255, 0.9);
    }
    
    /* Listening: Smooth Waveform */
    .wave-bars {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .bar {
        width: 6px;
        border-radius: 6px;
        background: #ff003c;
        animation: smoothBounce 1s infinite ease-in-out;
    }
    .bar:nth-child(1) { animation-delay: 0.1s; height: 30px; background: #ff003c; }
    .bar:nth-child(2) { animation-delay: 0.2s; height: 50px; background: #bd00ff; }
    .bar:nth-child(3) { animation-delay: 0.3s; height: 70px; background: #0052ff; }
    .bar:nth-child(4) { animation-delay: 0.4s; height: 45px; background: #ff003c; }
    .bar:nth-child(5) { animation-delay: 0.5s; height: 25px; background: #bd00ff; }
    
    /* Thinking: Elegant Spinner */
    .thinking-ring {
        width: 90px;
        height: 90px;
        border: 2.5px solid rgba(255, 255, 255, 0.05);
        border-top: 2.5px solid #ff003c;
        border-bottom: 2.5px solid #bd00ff;
        border-radius: 50%;
        animation: spin 1s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite;
        box-shadow: 0 0 20px rgba(255, 0, 60, 0.3);
    }
    
    /* Speaking: Soft Pulse */
    .speaking-outer {
        position: absolute;
        width: 140px;
        height: 140px;
        border: 2.5px dashed rgba(255, 0, 60, 0.4);
        border-radius: 50%;
        animation: speakPulseOuter 1.5s infinite linear;
        pointer-events: none;
    }
    .orb-speaking {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 75px;
        height: 75px;
        border-radius: 50%;
        background: radial-gradient(circle, #ff003c 0%, #bd00ff 100%);
        box-shadow: 0 0 35px rgba(255, 0, 60, 0.6);
        animation: speakPulseSmooth 0.6s infinite alternate ease-in-out;
        z-index: 2;
    }
    
    /* Authorizing: Alert Pulse */
    .orb-authorizing {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: #ff4d4d;
        box-shadow: 0 0 40px rgba(255, 77, 77, 0.6);
        animation: authorizePulseSmooth 1s infinite alternate ease-in-out;
    }

    /* Status Panel */
    .status-panel {
        background: rgba(20, 15, 30, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        margin-top: 24px;
        backdrop-filter: blur(12px);
    }
    .status-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.3em;
        color: #f8f9fa;
        font-weight: 400;
        letter-spacing: 1px;
    }

    /* Modern Terminal Console Panel */
    .terminal-container {
        background: #08060c;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        margin-top: 30px;
        overflow: hidden;
        font-family: 'JetBrains Mono', monospace;
    }
    .terminal-header {
        background: #110c18;
        padding: 14px 20px;
        display: flex;
        align-items: center;
        gap: 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .terminal-title {
        color: #94a3b8;
        font-size: 0.85em;
        font-weight: 700;
        letter-spacing: 1px;
        margin-left: 10px;
        text-transform: uppercase;
    }
    .terminal-body {
        padding: 24px;
        font-size: 0.9em;
        line-height: 1.6;
        color: #cbd5e1;
        max-height: 250px;
        overflow-y: auto;
    }
    .terminal-line {
        margin-bottom: 10px;
        padding-left: 14px;
        border-left: 2px solid #ff003c;
    }

    /* Keyframes */
    @keyframes smoothBounce {
        0%, 100% { transform: scaleY(0.5); }
        50% { transform: scaleY(1.2); }
    }
    @keyframes spin {
        100% { transform: rotate(360deg); }
    }
    @keyframes spinReactor {
        100% { transform: rotate(360deg); }
    }
    @keyframes spinCounter {
        100% { transform: rotate(-360deg); }
    }
    @keyframes speakPulseSmooth {
        0% { transform: scale(0.95); box-shadow: 0 0 20px rgba(255, 0, 60, 0.4); }
        100% { transform: scale(1.1); box-shadow: 0 0 50px rgba(255, 0, 60, 0.8); }
    }
    @keyframes speakPulseOuter {
        0% { transform: scale(0.7) rotate(0deg); opacity: 0.8; }
        100% { transform: scale(1.4) rotate(360deg); opacity: 0; }
    }
    @keyframes authorizePulseSmooth {
        0% { transform: scale(0.95); box-shadow: 0 0 30px rgba(255, 77, 77, 0.4); }
        100% { transform: scale(1.1); box-shadow: 0 0 60px rgba(255, 77, 77, 0.8); }
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="header-box">
    <div class="header-title">J.A.R.V.I.S. SYSTEM</div>
    <div class="header-subtitle">COGNITIVE DESKTOP AUTOMATION SHELL • V2.0</div>
</div>
""", unsafe_allow_html=True)

# Status Panel
st.markdown("<hr style='border-color: #ff003c;'>", unsafe_allow_html=True)

# Voice PIN Recording Helper
def record_voice_pin(filename="pin_temp.wav", max_duration=6.0, silence_duration=1.2):
    fs = 44100
    q = queue.Queue()
    def callback(indata, frames, time_info, status):
        q.put(indata.copy())
    try:
        stream = sd.InputStream(samplerate=fs, channels=1, dtype='int16', callback=callback)
    except Exception:
        return
    audio_data = []
    speech_started = False
    silence_samples = 0
    silence_limit = int(silence_duration * fs / 1024)
    with stream:
        start_time = time.time()
        while time.time() - start_time < max_duration:
            try:
                block = q.get(timeout=0.1)
                audio_data.append(block)
                amplitude = np.max(np.abs(block))
                if amplitude > 2500:
                    speech_started = True
                    silence_samples = 0
                else:
                    if speech_started:
                        silence_samples += 1
                        if silence_samples >= silence_limit:
                            break
            except queue.Empty:
                pass
    if audio_data:
        full_audio = np.concatenate(audio_data, axis=0)
        wav.write(filename, fs, full_audio)
    else:
        wav.write(filename, fs, np.zeros((1024, 1), dtype='int16'))

def recognize_pin_from_audio(filename="pin_temp.wav"):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(filename) as source:
            audio = r.record(source)
        spoken = r.recognize_google(audio, language="en-IN").lower()
        print(f"[PIN DEBUG] Heard: {spoken}")
        # Accept both digit form and word form
        spoken_clean = spoken.replace(" ", "").replace("-", "")
        word_map = {
            "zero": "0", "one": "1", "two": "2", "three": "3",
            "four": "4", "five": "5", "six": "6", "seven": "7",
            "eight": "8", "nine": "9"
        }
        converted = spoken_clean
        for word, digit in word_map.items():
            converted = converted.replace(word, digit)
        return spoken, converted
    except Exception as e:
        print(f"[PIN ERROR] {e}")
        return "", ""

# Lock Screen Authentication Deck
if "unlocked" not in st.session_state:
    st.session_state.unlocked = True if is_widget else False
if "pin_listening" not in st.session_state:
    st.session_state.pin_listening = False
if "pin_status" not in st.session_state:
    st.session_state.pin_status = ""

if not st.session_state.unlocked:
    st.markdown("<h3 style='text-align:center; color:#ff1744;'>VOCAL SECURITY AUTHENTICATION REQUIRED</h3>", unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        st.markdown("""
        <div class="telemetry-card" style="border: 2px solid #ff1744; box-shadow: 0 0 25px rgba(255, 23, 68, 0.4); padding: 30px; text-align:center;">
            <div style="color: #ff1744; font-size: 1.3em; font-weight: bold; letter-spacing: 2px; margin-bottom: 10px;">
                🎙️ SAY YOUR ACCESS PIN
            </div>
            <div style="color: #8ab4f8; font-size: 0.95em; margin-bottom: 5px;">
                Active Voice Recognition Enabled
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)

        status_placeholder = st.empty()
        status_placeholder.info("🎙️ Listening... Say your Access PIN now.")

        # Automatic vocal authentication recording
        record_voice_pin("pin_temp.wav")
        spoken_raw, spoken_digits = recognize_pin_from_audio("pin_temp.wav")
        correct_pin = os.getenv("ACCESS_PIN", "0909")
        
        # Build word version of correct pin for comparison
        digit_to_word = {"0":"zero","1":"one","2":"two","3":"three","4":"four","5":"five","6":"six","7":"seven","8":"eight","9":"nine"}
        correct_pin_words = "".join(digit_to_word[d] for d in correct_pin)
        spoken_raw_clean = spoken_raw.replace(" ", "")

        if spoken_digits:
            if spoken_digits == correct_pin or spoken_raw_clean == correct_pin_words:
                status_placeholder.success("✅ Vocal Signature Verified! Initiating System...")
                voice_engine.speak("Access Granted.")
                time.sleep(1.5)
                st.session_state.unlocked = True
                st.rerun()
            else:
                voice_engine.speak("You said wrong.")
                status_placeholder.error("❌ Access Denied! Vocal Signature Invalid. Try again.")
                time.sleep(1.5)
                st.rerun()
        elif spoken_raw:
            voice_engine.speak("No, you said wrong.")
            status_placeholder.error("❌ Access Denied! Vocal Signature Invalid. Try again.")
            time.sleep(1.5)
            st.rerun()
        else:
            status_placeholder.warning("⚠️ Could not hear clearly. Please try again.")
            time.sleep(1.0)
            st.rerun()

else:
    # Read live status first so columns can use it dynamically!
    status_file = "status.txt"
    if not os.path.exists(status_file):
        with open(status_file, "w", encoding="utf-8") as f:
            f.write("AWAITING VOCAL DIRECTIVE (Say: Jarvis / Daddy's Home / Wake up)")

    with open(status_file, "r", encoding="utf-8") as f:
        current_status = f.read()

    if is_widget:
        def render_visualizer(status_lower: str) -> str:
            """Return appropriate visualizer HTML based on the lower‑cased status string."""
            if "listening" in status_lower:
                return (
                    '<div class="visualizer-container" style="height: 140px; margin: 5px 0; border: none; background: transparent; box-shadow: none;">'
                    '<div class="wave-bars">'
                    '<div class="bar"></div>'
                    '<div class="bar"></div>'
                    '<div class="bar"></div>'
                    '<div class="bar"></div>'
                    '<div class="bar"></div>'
                    '</div>'
                    '</div>'
                )
            elif "thinking" in status_lower or "reasoning" in status_lower:
                return (
                    '<div class="visualizer-container" style="height: 140px; margin: 5px 0; border: none; background: transparent; box-shadow: none;">'
                    '<div class="thinking-ring" style="width: 70px; height: 70px;"></div>'
                    '</div>'
                )
            elif "jarvis:" in status_lower or "speaking" in status_lower:
                return (
                    '<div class="visualizer-container" style="height: 140px; margin: 5px 0; border: none; background: transparent; box-shadow: none;">'
                    '<div class="speaking-outer"></div>'
                    '<div class="orb-speaking" style="width: 60px; height: 60px;"></div>'
                    '</div>'
                )
            elif "authorizing" in status_lower or "awaiting" in status_lower or "security" in status_lower:
                return (
                    '<div class="visualizer-container" style="height: 140px; margin: 5px 0; border: none; background: transparent; box-shadow: none;">'
                    '<div class="orb-authorizing"></div>'
                    '</div>'
                )
            else:
                return (
                    '<div class="visualizer-container" style="height: 140px; margin: 5px 0; border: none; background: transparent; box-shadow: none;">'
                    '<div class="orb-standby" style="width: 80px; height: 80px;"></div>'
                    '</div>'
                )

        # Replace original visualizer_html assignment
        status_lower = current_status.lower()
        visualizer_html = render_visualizer(status_lower)

        st.markdown("""
            <style>
            .stApp {
                background-color: #030407 !important;
                background-image: none !important;
                overflow: hidden !important;
            }
            [data-testid="stHeader"] {
                display: none !important;
            }
            [data-testid="stSidebar"] {
                display: none !important;
            }
            .widget-root {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                padding: 10px;
                border: 1px solid rgba(255, 0, 60, 0.25);
                border-radius: 16px;
                background: rgba(10, 5, 20, 0.85);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 20px rgba(255, 0, 60, 0.15);
                margin: 5px;
            }
            </style>
        """, unsafe_allow_html=True)

        thoughts_content = ""
        if os.path.exists("thoughts.txt"):
            try:
                with open("thoughts.txt", "r", encoding="utf-8") as tf:
                    thoughts_content = tf.read().strip()
            except:
                pass

        st.markdown(f"""<div class="widget-root">
<div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8em; color: #ff003c; letter-spacing: 2px; font-weight: bold; text-transform: uppercase;">
J.A.R.V.I.S. WIDGET
</div>
{visualizer_html}
<div style="font-family: 'Outfit', sans-serif; font-size: 1.05em; color: #ffffff; font-weight: bold; min-height: 40px; margin-top: 5px;">
{current_status}
</div>
</div>""", unsafe_allow_html=True)

        if thoughts_content:
            st.markdown(f"""<div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75em; color: #bd00ff; text-align: center; max-height: 80px; overflow-y: auto; padding: 6px; border-top: 1px dashed rgba(255, 0, 60, 0.25); margin: 5px 10px 0 10px;">
{thoughts_content}
</div>""", unsafe_allow_html=True)

        def start_voice_engine():
            try:
                voice_engine.listen_loop()
            except Exception as e:
                print(f"Voice Engine Error: {e}")

        if os.getenv("START_VOICE_ENGINE", "true").lower() == "true":
            if "voice_thread_started" not in st.session_state:
                st.session_state.voice_thread_started = True
                t = threading.Thread(target=start_voice_engine, daemon=True)
                t.start()

        time.sleep(1)
        st.rerun()

    # Dynamic Cognitive Process Stream logs
    from datetime import datetime
    import json
    
    if "terminal_logs" not in st.session_state:
        st.session_state.terminal_logs = [
            "[SYS] Core Kernel Activated. Neural bindings Online.",
            "[AUDIO] sounddevice Stream initialized at 44100Hz.",
            "[COGNITION] Groq LLM model dynamically loaded.",
            "[PRIVACY] verify_privacy_gate fully armed. Double-gate active.",
            "[INTERCEPT] Local YouTube & Google search routers online."
        ]

    if current_status:
        clean_status = current_status.strip()
        log_line = f"[{datetime.now().strftime('%H:%M:%S')}] {clean_status}"
        if clean_status != "STANDBY" and (not st.session_state.terminal_logs or clean_status not in st.session_state.terminal_logs[-1]):
            st.session_state.terminal_logs.append(log_line)
            if len(st.session_state.terminal_logs) > 6:
                st.session_state.terminal_logs.pop(0)

    # Sidebar Settings config (gives a highly premium $1000 SaaS dashboard feel!)
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 10px; margin-bottom: 20px; border-bottom: 1px solid rgba(0,229,255,0.2);'>
            <h3 style='color: #00e5ff; margin: 0; font-weight: 700; letter-spacing: 2px;'>CORE CONFIG</h3>
            <span style='color: #8ab4f8; font-size: 0.8em;'>J.A.R.V.I.S. CONTROLLER</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Load and persist config
        config_path = "config.json"
        cfg_data = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as cf:
                    cfg_data = json.load(cf)
            except Exception:
                pass

        current_model = cfg_data.get("selected_model", "llama-3.3-70b-versatile")
        current_threshold = cfg_data.get("mic_threshold", 0.38)
        current_rate = cfg_data.get("voice_rate", 2)
        current_gender = cfg_data.get("voice_gender", "male")

        model_list = [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768"
        ]
        try:
            model_index = model_list.index(current_model)
        except ValueError:
            model_index = 0

        model_opt = st.selectbox(
            "COGNITIVE LLM CORE",
            model_list,
            index=model_index
        )
        
        # Audio threshold slider
        mic_val = st.slider("MIC SENSITIVITY THRESHOLD", 0.0, 1.0, float(current_threshold), 0.05)

        # Voice Rate slider (-10 to 10)
        rate_val = st.slider("VOICE RATE (SPEED)", -10, 10, int(current_rate), 1)

        # Voice Gender selector
        gender_opt = st.selectbox(
            "VOICE CHARACTER GENDER",
            ["male", "female"],
            index=0 if current_gender == "male" else 1
        )
        
        # Save updates to config.json
        if (model_opt != current_model or mic_val != current_threshold or 
            rate_val != current_rate or gender_opt != current_gender):
            cfg_data["selected_model"] = model_opt
            cfg_data["mic_threshold"] = mic_val
            cfg_data["voice_rate"] = rate_val
            cfg_data["voice_gender"] = gender_opt
            try:
                with open(config_path, "w") as cf:
                    json.dump(cfg_data, cf)
            except Exception:
                pass
        
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class="telemetry-card" style="padding: 15px; background: rgba(5,19,41,0.3); border-color: rgba(0,229,255,0.15);">
            <div style="color: #00e5ff; font-size: 0.85em; font-weight: 600; text-align: left; letter-spacing: 1px;">CORE INTEGRITY</div>
            <div style="color: #00e676; font-size: 1.1em; font-weight: bold; text-align: left; margin-top: 5px;">ONLINE</div>
            <div style="color: #cbd5e1; font-size: 0.7em; text-align: left; margin-top: 8px;">LATENCY: 14ms | Stark-COM v2.1</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Active Application Tile
        focused_app = "—"
        try:
            with open("activity_patterns.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                focused_app = data.get("current_window", "—")
        except Exception:
            pass
        st.markdown(f"""
        <div class="telemetry-card" style="padding:15px; background:rgba(15,5,20,0.6); border-color:rgba(255,0,60,0.2);">
            <div style="color: #ff003c; font-size: 0.85em; font-weight: 600; text-align: left; letter-spacing: 1px;">ACTIVE WINDOW</div>
            <div style="color: #ffffff; font-size: 1.0em; font-weight: bold; text-align: left; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{focused_app}</div>
        </div>
        """, unsafe_allow_html=True)

        # Encrypted Secrets Vault Tile
        try:
            import vault
            secrets_count = len(vault.list_secrets())
        except Exception:
            secrets_count = 0
            
        st.markdown(f"""
        <div class="telemetry-card" style="padding: 15px; background: rgba(10, 20, 10, 0.45); border-color: rgba(0, 230, 118, 0.25); margin-top: 10px;">
            <div style="color: #00e676; font-size: 0.85em; font-weight: 600; text-align: left; letter-spacing: 1px;">🔒 SECRETS VAULT</div>
            <div style="color: #ffffff; font-size: 1.1em; font-weight: bold; text-align: left; margin-top: 5px;">{secrets_count} SECRETS STORED</div>
            <div style="color: #cbd5e1; font-size: 0.7em; text-align: left; margin-top: 4px;">State: Keyring Encrypted</div>
        </div>
        """, unsafe_allow_html=True)

        # AI Profile Manager Tile
        try:
            import profile_manager
            profiles_count = len(profile_manager.list_profiles())
        except Exception:
            profiles_count = 0
            
        st.markdown(f"""
        <div class="telemetry-card" style="padding: 15px; background: rgba(25, 5, 25, 0.45); border-color: rgba(189, 0, 255, 0.25); margin-top: 10px;">
            <div style="color: #bd00ff; font-size: 0.85em; font-weight: 600; text-align: left; letter-spacing: 1px;">👤 PROFILE MANAGER</div>
            <div style="color: #ffffff; font-size: 1.1em; font-weight: bold; text-align: left; margin-top: 5px;">{profiles_count} ACTIVE PROFILES</div>
            <div style="color: #cbd5e1; font-size: 0.7em; text-align: left; margin-top: 4px;">Status: Cryptography Secure</div>
        </div>
        """, unsafe_allow_html=True)

        # Task Automation Engine Tile
        try:
            from task_engine import task_engine
            tasks_count = len(task_engine.get_tasks())
        except Exception:
            tasks_count = 0
            
        st.markdown(f"""
        <div class="telemetry-card" style="padding: 15px; background: rgba(25, 10, 5, 0.45); border-color: rgba(255, 23, 68, 0.25); margin-top: 10px;">
            <div style="color: #ff1744; font-size: 0.85em; font-weight: 600; text-align: left; letter-spacing: 1px;">⚙️ AUTOMATION ENGINE</div>
            <div style="color: #ffffff; font-size: 1.1em; font-weight: bold; text-align: left; margin-top: 5px;">{tasks_count} PIPELINES ACTIVE</div>
            <div style="color: #cbd5e1; font-size: 0.7em; text-align: left; margin-top: 4px;">Status: Thread Pool Synced</div>
        </div>
        """, unsafe_allow_html=True)

    # Full Dashboard Access
    col1, col2, col3 = st.columns([1, 2, 1])

    # Column 1: System Telemetry
    with col1:
        st.markdown("<h3 style='text-align:center; color:#00e5ff;'>SYSTEM TELEMETRY</h3>", unsafe_allow_html=True)
        
        cpu_val = psutil.cpu_percent()
        st.markdown(f"""
        <div class="telemetry-card">
            <div class="telemetry-label">CPU UTILIZATION</div>
            <div class="telemetry-val">{cpu_val}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="telemetry-card threat-card">
            <div class="telemetry-label">SECURITY PROTOCOL</div>
            <div class="telemetry-val" style="font-size: 2em; margin-top: 15px;">SECURE</div>
        </div>
        """, unsafe_allow_html=True)

    # Column 2: ChatGPT Voice Waveform Visualizer
    with col2:
        status_lower = current_status.lower()
        if "listening" in status_lower:
            visualizer_html = (
                '<div class="visualizer-container">'
                '<div class="wave-bars">'
                '<div class="bar"></div>'
                '<div class="bar"></div>'
                '<div class="bar"></div>'
                '<div class="bar"></div>'
                '<div class="bar"></div>'
                '</div>'
                '</div>'
            )
        elif "thinking" in status_lower or "reasoning" in status_lower:
            visualizer_html = (
                '<div class="visualizer-container">'
                '<div class="thinking-ring"></div>'
                '</div>'
            )
        elif "jarvis:" in status_lower or "speaking" in status_lower:
            visualizer_html = (
                '<div class="visualizer-container">'
                '<div class="speaking-outer"></div>'
                '<div class="orb-speaking"></div>'
                '</div>'
            )
        elif "authorizing" in status_lower or "awaiting" in status_lower or "security" in status_lower:
            visualizer_html = (
                '<div class="visualizer-container">'
                '<div class="orb-authorizing"></div>'
                '</div>'
            )
        else:
            # Standby state
            visualizer_html = (
                '<div class="visualizer-container">'
                '<div class="orb-standby"></div>'
                '</div>'
            )
        st.markdown(visualizer_html, unsafe_allow_html=True)

    # Column 3: Diagnostic Info
    with col3:
        st.markdown("<h3 style='text-align:center; color:#00e5ff;'>SYSTEM CONTROLS</h3>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="telemetry-card neural-card">
            <div class="telemetry-label">NEURAL LINK</div>
            <div class="telemetry-val" style="font-size: 2em; margin-top: 15px;">SYNCED</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free // (2**30)
        
        battery = psutil.sensors_battery()
        if battery:
            bat_str = f"{battery.percent}% {'(Charging)' if battery.power_plugged else '(Discharging)'}"
        else:
            bat_str = "A/C LINE SECURED"
            
        thread_count = os.cpu_count() or 4
        ram_val = psutil.virtual_memory().percent
        
        st.markdown(f"""
        <div class="telemetry-card" style="padding: 15px; text-align: left;">
            <div style="color: #8ab4f8; font-size: 0.8em; margin-bottom: 4px;">OS: Windows {os.name.upper()}</div>
            <div style="color: #8ab4f8; font-size: 0.8em; margin-bottom: 4px;">RAM: {ram_val}%</div>
            <div style="color: #8ab4f8; font-size: 0.8em; margin-bottom: 4px;">COGNITION: {model_opt.split(' ')[0]}</div>
            <div style="color: #8ab4f8; font-size: 0.8em; margin-bottom: 4px;">THREADS: {thread_count}</div>
            <div style="color: #8ab4f8; font-size: 0.8em; margin-bottom: 4px;">POWER: {bat_str}</div>
        </div>
        """, unsafe_allow_html=True)

    # Core status and live intelligence monitor
    st.markdown("<h3 style='text-align:center; color:#ff1744;'>COGNITIVE INTELLIGENCE MONITOR</h3>", unsafe_allow_html=True)

    st.markdown(f"""
    <div class="status-panel">
        <div class="status-text">{current_status}</div>
    </div>
    """, unsafe_allow_html=True)

    # Conversation Transcript Panel
    history_file = "session_history.json"
    history_data = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as hf:
                history_data = json.load(hf)
        except Exception:
            pass

    if history_data:
        transcript_lines = []
        for msg in history_data:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                transcript_lines.append(f'<div class="terminal-line" style="border-left-color: #00e5ff; color: #8ab4f8; font-weight: bold;">🎙️ Master: {content}</div>')
            else:
                transcript_lines.append(f'<div class="terminal-line" style="border-left-color: #bd00ff; color: #cbd5e1;">🤖 J.A.R.V.I.S.: {content}</div>')
                
        transcript_html = "".join(transcript_lines)
        
        st.markdown(f"""
        <div class="terminal-container" style="border-color: rgba(0, 229, 255, 0.45); box-shadow: 0 4px 15px rgba(0, 229, 255, 0.15); margin-top: 15px;">
            <div class="terminal-header" style="background: rgba(5, 20, 25, 0.85); border-bottom: 1px solid rgba(0, 229, 255, 0.25);">
                <span class="terminal-dot red"></span>
                <span class="terminal-dot yellow"></span>
                <span class="terminal-dot green"></span>
                <span class="terminal-title" style="color: #00e5ff; letter-spacing: 2px;">💬 CONVERSATION TRANSCRIPT PANEL</span>
            </div>
            <div class="terminal-body" style="max-height: 250px; overflow-y: auto;">
                {transcript_html}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # PDF Export Button
        try:
            from fpdf import FPDF
            class JARVIS_PDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 12)
                    self.set_text_color(0, 229, 255)
                    self.cell(0, 10, 'J.A.R.V.I.S. SYSTEM COGNITIVE TRANSCRIPT', 0, 1, 'C')
                    self.ln(10)
                def footer(self):
                    self.set_y(-15)
                    self.set_font('Arial', 'I', 8)
                    self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
            
            pdf = JARVIS_PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)
            
            for msg in history_data:
                role = msg.get("role", "user").upper()
                content = msg.get("content", "")
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(0, 8, f"[{role}]:", 0, 1)
                pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 6, content)
                pdf.ln(4)
                
            pdf_bytes = pdf.output(dest='S')
            st.download_button(
                label="📥 EXPORT CONVERSATION TO PDF",
                data=pdf_bytes,
                file_name="jarvis_transcript.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as pdf_err:
            logger.error(f"PDF generation error: {pdf_err}")

    # Deep Reasoning Board
    thoughts_file = "thoughts.txt"
    if os.path.exists(thoughts_file):
        try:
            with open(thoughts_file, "r", encoding="utf-8") as tf:
                thoughts_content = tf.read().strip()
            if thoughts_content:
                st.markdown(f"""
                <div class="terminal-container" style="border-color: rgba(255, 235, 59, 0.45); box-shadow: 0 4px 15px rgba(255, 235, 59, 0.15); margin-top: 15px;">
                    <div class="terminal-header" style="background: rgba(25, 20, 5, 0.85); border-bottom: 1px solid rgba(255, 235, 59, 0.25);">
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-title" style="color: #ffeb3b; letter-spacing: 2px;">🧠 DEEP REASONING BOARD</span>
                    </div>
                    <div class="terminal-body" style="color: #fff9c4; font-style: italic; max-height: 200px; overflow-y: auto;">
                        {thoughts_content.replace(chr(10), '<br>')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        except Exception:
            pass

    # Long-term Memory Board
    memory_file = "memory.json"
    if os.path.exists(memory_file):
        try:
            with open(memory_file, "r", encoding="utf-8") as mf:
                mem_data = json.load(mf)
            user_facts = mem_data.get("user_facts", [])
            if user_facts:
                facts_html = "".join(f'<div class="terminal-line" style="border-left-color: #00e5ff; color: #cbd5e1;">{fact}</div>' for fact in user_facts)
                st.markdown(f"""
                <div class="terminal-container" style="border-color: rgba(0, 229, 255, 0.45); box-shadow: 0 4px 15px rgba(0, 229, 255, 0.15); margin-top: 15px;">
                    <div class="terminal-header" style="background: rgba(5, 20, 25, 0.85); border-bottom: 1px solid rgba(0, 229, 255, 0.25);">
                        <span class="terminal-dot green"></span>
                        <span class="terminal-dot green"></span>
                        <span class="terminal-dot green"></span>
                        <span class="terminal-title" style="color: #00e5ff; letter-spacing: 2px;">💾 LONG-TERM MEMORY BANKS</span>
                    </div>
                    <div class="terminal-body" style="max-height: 150px; overflow-y: auto;">
                        {facts_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        except Exception:
            pass

    # Cyber terminal console listing recent system actions from logs/jarvis.log
    log_file = os.path.join("logs", "jarvis.log")
    log_lines = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as lf:
                log_lines = lf.readlines()[-8:]
        except Exception:
            pass

    formatted_logs = []
    for line in log_lines:
        line_str = line.strip()
        if "ERROR" in line_str or "CRITICAL" in line_str:
            formatted_logs.append(f'<div class="terminal-line" style="border-left-color: #ff1744; color: #ff1744; font-weight: bold;">{line_str}</div>')
        elif "WARN" in line_str:
            formatted_logs.append(f'<div class="terminal-line" style="border-left-color: #ffeb3b; color: #ffeb3b;">{line_str}</div>')
        else:
            formatted_logs.append(f'<div class="terminal-line" style="border-left-color: #bd00ff;">{line_str}</div>')

    if not formatted_logs:
        for line in st.session_state.terminal_logs:
            if "[SECURITY ALERT]" in line or "SECURITY" in line:
                formatted_logs.append(f'<div class="terminal-line" style="border-left-color: #ff1744; color: #ff1744; font-weight: bold;">{line}</div>')
            else:
                formatted_logs.append(f'<div class="terminal-line">{line}</div>')

    terminal_lines_html = "".join(formatted_logs)
    st.markdown(f"""
    <div class="terminal-container">
        <div class="terminal-header">
            <span class="terminal-dot red"></span>
            <span class="terminal-dot yellow"></span>
            <span class="terminal-dot green"></span>
            <span class="terminal-title">Cognitive Process Stream</span>
        </div>
        <div class="terminal-body">
            {terminal_lines_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Background Thread for Voice Engine (Starts only when fully unlocked!)
    def start_voice_engine():
        try:
            voice_engine.listen_loop()
        except Exception as e:
            print(f"Voice Engine Error: {e}")

    if os.getenv("START_VOICE_ENGINE", "true").lower() == "true":
        if "voice_thread_started" not in st.session_state:
            st.session_state.voice_thread_started = True
            t = threading.Thread(target=start_voice_engine, daemon=True)
            t.start()

    # Live Refresh logic
    time.sleep(1)
    st.rerun()
