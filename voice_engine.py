import speech_recognition as sr
import os
import subprocess
import pyautogui
import time
import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import queue
import win32com.client
import json
import sqlite3
import shutil
import xml.etree.ElementTree as ET
from ai_brain import process_command_with_llm
from datetime import datetime
from dotenv import load_dotenv
from logger import logger
load_dotenv()

# ── Process Global Lock & Transcription Helper ───────────────────────────
_voice_engine_running = False
_whatsapp_watcher_running = False
_last_notif_time = None
_whatsapp_prompt_active = False

def get_current_filetime():
    import datetime as dt
    return int((dt.datetime.utcnow().timestamp() + 11644473600) * 10000000)

def handle_whatsapp_incoming(sender, body):
    speak(f"Sir, you have a new WhatsApp message in your chat from {sender}. Should I read it or ignore it?")
    update_status(f"WHATSAPP MSG FROM {sender.upper()}")
    
    response_file = "temp_whatsapp_response.wav"
    record_dynamic_audio(response_file, max_duration=5.0, silence_duration=0.8)
    
    r = sr.Recognizer()
    action_type = "ignore"
    if os.path.exists(response_file):
        try:
            with sr.AudioFile(response_file) as src:
                audio = r.record(src)
            transcribed = transcribe_audio(r, audio).lower()
            print(f"[WHATSAPP PROMPT HEARD] {transcribed}")
            
            if any(w in transcribed for w in ["read", "sunao", "yes", "batao", "suna", "sunaen", "read it"]):
                action_type = "read"
            elif any(w in transcribed for w in ["ignore", "no", "choro", "rahne do", "bhool jao"]):
                action_type = "ignore"
        except Exception:
            pass
        try:
            os.remove(response_file)
        except Exception:
            pass

    if action_type == "read":
        speak(f"{sender} says: {body}")
        speak("Would you like to send a reply, sir?")
        record_dynamic_audio(response_file, max_duration=5.0, silence_duration=0.8)
        try:
            with sr.AudioFile(response_file) as src:
                audio = r.record(src)
            reply_choice = transcribe_audio(r, audio).lower()
            if any(w in reply_choice for w in ["yes", "haan", "reply", "haji", "ji"]):
                speak("What should the reply say, sir?")
                record_dynamic_audio(response_file, max_duration=8.0, silence_duration=0.8)
                with sr.AudioFile(response_file) as src:
                    audio_msg = r.record(src)
                reply_text = transcribe_audio(r, audio_msg)
                if reply_text:
                    execute_action({"action": "whatsapp_send", "contact": sender, "message": reply_text}, verified=True)
        except Exception:
            speak("Reply sequence cancelled.")
        try:
            os.remove(response_file)
        except Exception:
            pass
    else:
        speak("Ignoring message.")

def whatsapp_watcher():
    global _last_notif_time, _whatsapp_prompt_active
    
    if _last_notif_time is None:
        _last_notif_time = get_current_filetime()
        
    localappdata = os.environ.get("LOCALAPPDATA")
    db_dir = os.path.join(localappdata, "Microsoft\\Windows\\Notifications")
    src_db = os.path.join(db_dir, "wpndatabase.db")
    temp_dir = "temp_whatsapp_watcher_db"
    
    while True:
        time.sleep(3)
        if _whatsapp_prompt_active or not os.path.exists(src_db):
            continue
            
        try:
            os.makedirs(temp_dir, exist_ok=True)
            for f in os.listdir(db_dir):
                if f.startswith("wpndatabase.db"):
                    shutil.copy2(os.path.join(db_dir, f), os.path.join(temp_dir, f))
                    
            dest_db = os.path.join(temp_dir, "wpndatabase.db")
            conn = sqlite3.connect(dest_db)
            cursor = conn.cursor()
            
            query = """
                SELECT n.Payload, n.ArrivalTime, n.Id
                FROM Notification n
                LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
                WHERE h.PrimaryId LIKE '%WhatsApp%' AND n.ArrivalTime > ?
                ORDER BY n.ArrivalTime ASC
            """
            cursor.execute(query, (_last_notif_time,))
            rows = cursor.fetchall()
            
            for row in rows:
                payload, arrival_time, notif_id = row
                _last_notif_time = max(_last_notif_time, arrival_time)
                payload_str = payload.decode('utf-8', errors='ignore') if isinstance(payload, bytes) else str(payload)
                
                try:
                    root = ET.fromstring(payload_str)
                    texts = root.findall(".//text")
                    sender = texts[0].text if len(texts) > 0 else None
                    body = texts[1].text if len(texts) > 1 else ""
                    
                    if sender and body and "WhatsApp" not in sender and "checking for new messages" not in body.lower():
                        _whatsapp_prompt_active = True
                        handle_whatsapp_incoming(sender, body)
                        _whatsapp_prompt_active = False
                except Exception:
                    pass
            conn.close()
        except Exception as e:
            print(f"[WHATSAPP WATCHER ERROR] {e}")
        finally:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass

def transcribe_audio(recognizer, audio):
    """Transcribes audio using en-IN (English/Roman Urdu) with seamless fallback to ur-PK (Urdu script)."""
    try:
        # Attempt en-IN which captures English and Roman Urdu keywords perfectly
        text = recognizer.recognize_google(audio, language="en-IN").strip()
        print(f"[TRANSCRIBED EN-IN] {text}")
        return text
    except sr.UnknownValueError:
        # On failure, fall back to ur-PK to capture native Urdu script commands
        try:
            text = recognizer.recognize_google(audio, language="ur-PK").strip()
            print(f"[TRANSCRIBED UR-PK] {text}")
            return text
        except sr.UnknownValueError:
            # Both failed to find recognizable speech
            raise sr.UnknownValueError("Speech was not understood in English or Urdu.")

# ── Custom Profile → Folder Mapping ──────────────────────────────────────────
# When user says "chrome 3 id" → opens this folder instead of Chrome profile
PROFILE_FOLDER_MAP = {
    3: r"C:\Users\DELL\Desktop\saad\saad",
}

# ── Custom File Search Directories ───────────────────────────────────────────
CUSTOM_SEARCH_DIRS = [
    r"C:\Users\DELL\Desktop\saad\saad",
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Pictures"),
]

import threading
import pythoncom
import voice_engine_natural

def set_voice_character(gender="male"):
    try:
        voice_engine_natural.set_voice_character(gender)
    except Exception:
        pass

def is_speaking():
    try:
        return voice_engine_natural.is_speaking()
    except Exception:
        return False

def stop_speaking():
    try:
        voice_engine_natural.stop_speaking()
    except Exception:
        pass

def check_interrupted():
    if os.path.exists("interrupt.txt"):
        try:
            os.remove("interrupt.txt")
        except Exception:
            pass
        stop_speaking()
        return True
    return False

def speak(text, rate=None):
    if rate is None:
        from config import Config
        try:
            rate = int(Config.get("voice_rate", 2))
        except Exception:
            rate = 2
    
    from config import Config
    gender = Config.get("voice_gender", "male")
    
    print(f">> {text}")
    try:
        with open("last_response.txt", "w", encoding="utf-8") as rf:
            rf.write(text)
    except Exception:
        pass
    update_status(f"JARVIS: {text[:80]}")
    try:
        voice_engine_natural.speak(text, rate=rate, gender=gender)
    except Exception as e:
        logger.error(f"[TTS ERROR] {e}")

def update_status(text):
    try:
        # Clear reasoning board on standby
        if text.strip() == "STANDBY" and os.path.exists("thoughts.txt"):
            try:
                os.remove("thoughts.txt")
            except Exception:
                pass
        # Explicitly write in UTF-8 to prevent Windows 'charmap' encoding crash
        with open("status.txt", "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        print(f"[STATUS WRITE ERROR] {e}")

# ── Human-Override Safety Lock ────────────────────────────────────────────────
_last_action_mouse_pos = None

def check_user_override():
    # Disabled override pause to allow seamless background automation
    return False

def update_action_mouse_pos():
    global _last_action_mouse_pos
    _last_action_mouse_pos = pyautogui.position()

# ── Privacy Passcode Verification Gate ─────────────────────────────────────────
def verify_privacy_gate(action_data, command_text):
    cmd_lower = str(command_text).lower()
    
    # Core Codebase Protection boundary:
    # Strictly forbid any LLM action from writing/deleting/modifying J.A.R.V.I.S system files
    system_files = ["main.py", "voice_engine.py", "ai_brain.py", ".env", "requirements.txt"]
    
    def check_system_violation(data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    v_lower = v.lower()
                    if any(sys_f in v_lower for sys_f in system_files):
                        action = data.get("action", "")
                        if "run_command" in action or "remove" in v_lower or "delete" in v_lower or "write" in action or "type_text" in action:
                            return True
        return False

    has_violation = False
    if isinstance(action_data, list):
        for item in action_data:
            if check_system_violation(item):
                has_violation = True
                break
    else:
        if check_system_violation(action_data):
            has_violation = True
            
    if has_violation:
        speak("System integrity violation detected. Codebase modification blocked.")
        return False

    # 1. Identify sensitive keywords & directories
    sensitive_keywords = [
        "saad", "downloads", "documents", "pictures", "history", "chrome history", 
        "personal", "credentials", "password", "private", "secret", "onedrive", 
        "appdata", "localappdata", "system32", "windows", "registry", ".env", 
        ".git", "credit card", "bank", "tax", "identity", "token", "key"
    ]
    is_sensitive = False
    
    # Check vocal query
    if any(keyword in cmd_lower for keyword in sensitive_keywords):
        is_sensitive = True
        
    # Check action data
    if isinstance(action_data, dict):
        action = action_data.get("action", "")
        folder = str(action_data.get("folder", "")).lower()
        file_name = str(action_data.get("file_name", "")).lower()
        file_path = str(action_data.get("file_path", "")).lower()
        
        # Opening private folders
        if action == "open_folder" and folder in ["saad", "downloads", "documents", "pictures"]:
            is_sensitive = True
        # Accessing private profiles or files
        if action == "chrome_profile" and "history" in cmd_lower:
            is_sensitive = True
        if any(keyword in file_name or keyword in file_path for keyword in sensitive_keywords):
            is_sensitive = True
        # If running shell command containing sensitive paths/terms
        if action == "run_command":
            cmd_val = str(action_data.get("command", "")).lower()
            if any(k in cmd_val for k in sensitive_keywords):
                is_sensitive = True
            
    elif isinstance(action_data, list):
        for item in action_data:
            if isinstance(item, dict):
                action = item.get("action", "")
                folder = str(item.get("folder", "")).lower()
                file_name = str(item.get("file_name", "")).lower()
                file_path = str(item.get("file_path", "")).lower()
                if action == "open_folder" and folder in ["saad", "downloads", "documents", "pictures"]:
                    is_sensitive = True
                    break
                if any(keyword in file_name or keyword in file_path for keyword in sensitive_keywords):
                    is_sensitive = True
                    break
                if action == "run_command":
                    cmd_val = str(item.get("command", "")).lower()
                    if any(k in cmd_val for k in sensitive_keywords):
                        is_sensitive = True
                        break
                    
    if not is_sensitive:
        return True
        
    # 2. Double-passcode verification challenge
    speak("Warning. Access to sensitive resources detected. Speak primary passcode.")
    update_status("AUTHORIZING_1")
    
    # Stage 1: "0909"
    try:
        record_dynamic_audio("temp_passcode.wav", max_duration=6.0, silence_duration=0.8)
        r = sr.Recognizer()
        if not os.path.exists("temp_passcode.wav"):
            speak("No audio signal. Access denied.")
            return False
            
        with sr.AudioFile("temp_passcode.wav") as src:
            audio = r.record(src)
            
        transcribed = transcribe_audio(r, audio).lower().strip()
        print(f"[AUTH GATE 1] Heard: {transcribed}")
        
        # Word-to-digit conversion
        cleaned = transcribed.replace(" ", "").replace("-", "")
        for word, digit in [("zero","0"), ("one","1"), ("two","2"), ("three","3"), ("four","4"), ("five","5"), ("six","6"), ("seven","7"), ("eight","8"), ("nine","9")]:
            cleaned = cleaned.replace(word, digit)
            
        if "0909" not in cleaned and "909" not in cleaned:
            speak("Verification failed. Access denied.")
            return False
            
    except Exception as e:
        print(f"[AUTH GATE 1 ERROR] {e}")
        speak("Verification timeout. Access denied.")
        return False
        
    # Stage 2: "alpha zero"
    speak("Primary passcode verified. Speak secondary passcode.")
    update_status("AUTHORIZING_2")
    
    try:
        record_dynamic_audio("temp_passcode.wav", max_duration=6.0, silence_duration=0.8)
        r = sr.Recognizer()
        if not os.path.exists("temp_passcode.wav"):
            speak("No audio signal. Access denied.")
            return False
            
        with sr.AudioFile("temp_passcode.wav") as src:
            audio = r.record(src)
            
        transcribed = transcribe_audio(r, audio).lower().strip()
        print(f"[AUTH GATE 2] Heard: {transcribed}")
        
        cleaned = transcribed.replace(" ", "").replace("-", "")
        if "alphazero" not in cleaned and "alpha0" not in cleaned and "alphao" not in cleaned:
            speak("Verification failed. Access denied.")
            return False
            
    except Exception as e:
        print(f"[AUTH GATE 2 ERROR] {e}")
        speak("Verification timeout. Access denied.")
        return False
        
    speak("Vocal signature verified. Access granted.")
    return True


def rgb_color(r, g, b):
    """Converts standard R, G, B color values to a Windows COM COLORREF integer."""
    return r + (g * 256) + (b * 65536)

# ── Stark PowerPoint Maker ────────────────────────────────────────────────────
def create_powerpoint_com(topic):
    speak("Initiating slide generation.")
    update_status("THINKING...")
    
    slides = []
    
    # Try calling LLaMA for slide data
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            prompt = f"Create a slide deck of 5 slides about: {topic}"
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a professional PowerPoint designer. Generate content for a presentation on the requested topic. Output ONLY a valid JSON array of objects representing slides. Each slide object MUST have: 'title' (string) and 'bullets' (list of 3-4 strings). Keep descriptions extremely premium, clear, and professional. Output NO markdown, NO backticks, NO comments. Format: [{\"title\": \"slide 1\", \"bullets\": [\"pt1\", \"pt2\"]}, ...]"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1024
            )
            raw = res.choices[0].message.content.strip()
            
            # Robust JSON array extraction
            import re, json
            match = re.search(r'(\[.*?\])', raw, re.DOTALL)
            if match:
                slides = json.loads(match.group(1))
        except Exception as e:
            print(f"[COM PPT LLM ERROR] {e}. Using fallback presentation.")
            
    if not slides:
        # Fallback slides if API or parsing fails
        slides = [
            {"title": f"{topic} - Executive Brief", "bullets": [f"Deep analysis into {topic} frameworks.", "Key strategic foundations and conceptual paradigms.", "Evaluating initial deployment models."]},
            {"title": "Core Technical Dimension", "bullets": ["High-performance optimization layers.", "Scalable abstractions and interface modularity.", "Seamless integration with pre-existing telemetry dashboards."]},
            {"title": "Security & Security Architecture", "bullets": ["Multi-factor vocal signatures and security boundaries.", "Double-gate verification checking.", "Resilient local script and automation sandboxes."]},
            {"title": "Performance Outcomes", "bullets": ["Blistering fast automated action processing.", "Elimination of repetitive user confirmation delays.", "Near-instantaneous local productivity scaling."]},
            {"title": "Vision & Next Steps", "bullets": ["Deep cognitive enhancements through advanced LLM parsing.", "Broader COM automation integrations.", "Interactive Q&A and next phases."]}
        ]
        
    try:
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
        ppt_app.Visible = True
        presentation = ppt_app.Presentations.Add()
        
        for i, slide_info in enumerate(slides):
            title_text = slide_info.get("title", f"Slide {i+1}")
            bullets = slide_info.get("bullets", [])
            
            layout_type = 1 if i == 0 else 2 # Slide layout title or standard text
            slide = presentation.Slides.Add(i + 1, layout_type)
            
            # Apply premium Stark dark theme background (0x0B0C10)
            slide.FollowMasterBackground = False
            slide.Background.Fill.Solid()
            slide.Background.Fill.ForeColor.RGB = rgb_color(11, 12, 16)
            
            # Set Title Typography
            slide.Shapes.Title.TextFrame.TextRange.Text = title_text
            slide.Shapes.Title.TextFrame.TextRange.Font.Name = "Segoe UI"
            slide.Shapes.Title.TextFrame.TextRange.Font.Size = 40 if layout_type == 1 else 32
            slide.Shapes.Title.TextFrame.TextRange.Font.Color.RGB = rgb_color(102, 252, 241) # Neon Cyan
            slide.Shapes.Title.TextFrame.TextRange.Font.Bold = True
            
            # Set Subtitle or Bullets Text
            if len(slide.Shapes) > 1:
                body_shape = slide.Shapes.Placeholders(2)
                body_shape.TextFrame.TextRange.Text = "\n".join(bullets)
                body_shape.TextFrame.TextRange.Font.Name = "Segoe UI"
                body_shape.TextFrame.TextRange.Font.Size = 20 if layout_type == 1 else 16
                # Light silver for body/bullets, slate-teal for title slide subtitle
                body_color = rgb_color(69, 162, 158) if layout_type == 1 else rgb_color(220, 224, 230)
                body_shape.TextFrame.TextRange.Font.Color.RGB = body_color
                
        speak("PowerPoint slides generated live, sir.")
    except Exception as e:
        print(f"[COM PPT ERROR] {e}")
        speak("PowerPoint automation failed.")


# ── Stark Excel Creator ───────────────────────────────────────────────────────
def create_excel_com(topic):
    speak("Generating Excel sheet.")
    update_status("THINKING...")
    
    dataset = {}
    
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a senior data analyst. Generate a professional dataset for the requested topic. Output ONLY a valid JSON object with: 'headers' (list of 4 strings like ['Date', 'Category', 'Salesperson', 'Amount']), and 'data' (list of 8-10 rows where each row is a list matching headers). The 'Category' column must contain 3-4 distinct values to support pivot filtering. Output NO markdown, NO backticks, NO comments. Format: {\"headers\": [\"h1\", \"h2\"], \"data\": [[\"val1\", \"val2\"], ...]}"},
                    {"role": "user", "content": f"Create a dataset about: {topic}"}
                ],
                temperature=0.2,
                max_tokens=1024
            )
            raw = res.choices[0].message.content.strip()
            
            import re, json
            match = re.search(r'(\{.*?\})', raw, re.DOTALL)
            if match:
                dataset = json.loads(match.group(1))
        except Exception as e:
            print(f"[COM EXCEL LLM ERROR] {e}. Using fallback dataset.")
            
    if not dataset or "headers" not in dataset:
        dataset = {
            "headers": ["Date", "Category", "Salesperson", "Revenue"],
            "data": [
                ["2026-05-01", "Hardware", "Saad", 1200],
                ["2026-05-02", "Software", "Ali", 800],
                ["2026-05-03", "Hardware", "Saad", 1500],
                ["2026-05-04", "Services", "Zainab", 600],
                ["2026-05-05", "Software", "Ali", 950],
                ["2026-05-06", "Services", "Zainab", 1100],
                ["2026-05-07", "Hardware", "Ali", 700],
                ["2026-05-08", "Software", "Saad", 1300]
            ]
        }
        
    try:
        excel_app = win32com.client.Dispatch("Excel.Application")
        excel_app.Visible = True
        workbook = excel_app.Workbooks.Add()
        
        # 1. Populate Data
        ws_data = workbook.Sheets(1)
        ws_data.Name = "DataSheet"
        
        headers = dataset.get("headers", [])
        data_rows = dataset.get("data", [])
        
        # Populate headers with professional formatting
        for col_idx, h in enumerate(headers, 1):
            cell = ws_data.Cells(1, col_idx)
            cell.Value = h
            cell.Font.Bold = True
            cell.Interior.Color = 0x00E5FF # Neon cyan headers
            cell.Font.Color = 0x000000
            
        # Populate data rows
        for row_idx, row in enumerate(data_rows, 2):
            for col_idx, val in enumerate(row, 1):
                ws_data.Cells(row_idx, col_idx).Value = val
                
        ws_data.Columns.AutoFit()
        
        # 2. Populate Pivot Table
        ws_pivot = workbook.Sheets.Add()
        ws_pivot.Name = "PivotSheet"
        
        # Dynamic Range
        last_col = chr(64 + len(headers))
        last_row = len(data_rows) + 1
        source_range = f"DataSheet!A1:{last_col}{last_row}"
        
        pivot_cache = workbook.PivotCaches().Create(SourceType=1, SourceData=source_range)
        pivot_table = pivot_cache.CreatePivotTable(TableDestination=ws_pivot.Range("A3"), TableName="StarkPivot")
        
        # Rows
        row_field_name = headers[1] if len(headers) > 1 else headers[0]
        row_field = pivot_table.PivotFields(row_field_name)
        row_field.Orientation = 1  # xlRowField
        
        if len(headers) > 2:
            sub_field = pivot_table.PivotFields(headers[2])
            sub_field.Orientation = 1  # xlRowField
            
        # Value sum field
        val_field_name = headers[-1]
        val_field = pivot_table.PivotFields(val_field_name)
        pivot_table.AddDataField(val_field, f"Total {val_field_name}", -4157) # xlSum
        
        speak("Excel sheet and Pivot Table created, sir.")
    except Exception as e:
        print(f"[COM EXCEL ERROR] {e}")
        speak("Excel automation failed.")


# ── Stark CV Maker ────────────────────────────────────────────────────────────
def create_cv_com(job_title):
    speak("Generating CV in Word.")
    update_status("THINKING...")
    
    cv_data = {}
    
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a professional executive resume writer. Generate extremely high-quality CV text for the requested role. The summary, skills, and experience bullets MUST be highly detailed, professional, and metrics-driven (e.g. using numbers, percentages, and the STAR methodology: 'Pioneered migration of X system, increasing output by 35% and reducing infrastructure costs by $12,000 annually'). Output ONLY a valid JSON object with fields: 'name', 'contact', 'summary', 'skills' (list of 6-8 strings), 'experience' (list of 2 objects with: 'title', 'company', 'dates', 'bullets' (list of 3 bullets)), 'education' (list of 1-2 strings). Output NO markdown, NO backticks, NO comments. Format: {\"name\": \"...\", \"contact\": \"...\", \"summary\": \"...\", \"skills\": [\"...\"], \"experience\": [{\"title\": \"...\", \"company\": \"...\", \"dates\": \"...\", \"bullets\": [\"...\"]}], \"education\": [\"...\"]}"},
                    {"role": "user", "content": f"Create CV details for: {job_title}"}
                ],
                temperature=0.2,
                max_tokens=1024
            )
            raw = res.choices[0].message.content.strip()
            
            import re, json
            match = re.search(r'(\{.*?\})', raw, re.DOTALL)
            if match:
                cv_data = json.loads(match.group(1))
        except Exception as e:
            print(f"[COM CV LLM ERROR] {e}. Using fallback CV.")
            
    if not cv_data or "name" not in cv_data:
        cv_data = {
            "name": "MUHAMMAD SAAD",
            "contact": "Email: muhammadsaadpopat76@gmail.com | Karachi, Pakistan",
            "summary": f"Highly accomplished software systems architect and experienced developer specialized in building automated local COM control loops, real-time audio telemetry visualizers, and robust deep-learning pipelines as {job_title}.",
            "skills": ["Enterprise AI Integrations", "Microsoft COM Automation", "Vocal Biometric Privacy Locks", "Cyberpunk Telemetry Dashboarding", "Blistering Fast Typing Animation", "Agile Task Execution"],
            "experience": [
                {
                    "title": f"Lead {job_title}",
                    "company": "Stark Desktop intelligence division",
                    "dates": "2024 - Present",
                    "bullets": [
                        "Architected double-passcode voice authorization gates to shield sensitive system resources from unverified access.",
                        "Built real-time COM integration pipelines automating PowerPoint, Word, and Excel live updates directly from neural prompts.",
                        "Optimized execution sequences for dynamic hotkey combinations and blistering fast clipboard typing."
                    ]
                },
                {
                    "title": f"Senior {job_title}",
                    "company": "Cyber Dynamics Corporation",
                    "dates": "2021 - 2024",
                    "bullets": [
                        "Scaled background audio listening loops on sounddevice backend, completely bypassing PyAudio dependency issues.",
                        "Maintained 99.8% semantic classification accuracy for dual Urdu and English vocal queries.",
                        "Developed automated desktop screenshot pipelines and telemetry widgets."
                    ]
                }
            ],
            "education": [
                "Bachelor of Science in Software Engineering - National University of Computer and Emerging Sciences"
            ]
        }
        
    try:
        word_app = win32com.client.Dispatch("Word.Application")
        word_app.Visible = True
        document = word_app.Documents.Add()
        
        selection = word_app.Selection
        
        # Custom Narrow Margins
        for margin in ["TopMargin", "BottomMargin", "LeftMargin", "RightMargin"]:
            setattr(document.PageSetup, margin, 54) # Sleek modern look
            
        # Name Heading
        selection.Font.Name = "Calibri"
        selection.Font.Size = 24
        selection.Font.Bold = True
        selection.Font.Color = rgb_color(26, 54, 93)  # Professional Deep Navy
        selection.TypeText(cv_data.get("name") + "\n")
        
        # Contact subheader
        selection.Font.Name = "Calibri"
        selection.Font.Size = 10
        selection.Font.Bold = False
        selection.Font.Color = rgb_color(113, 128, 150)  # Muted slate gray
        selection.TypeText(cv_data.get("contact") + "\n")
        selection.TypeText("-" * 95 + "\n")
        
        # Sections Formatting
        sections = [
            ("Professional Summary", cv_data.get("summary")),
            ("Core Competencies", "  •  ".join(cv_data.get("skills")))
        ]
        
        for section_title, section_text in sections:
            selection.Font.Name = "Calibri"
            selection.Font.Size = 13
            selection.Font.Bold = True
            selection.Font.Color = rgb_color(26, 54, 93)
            selection.TypeText(section_title + "\n")
            
            selection.Font.Name = "Calibri"
            selection.Font.Size = 10.5
            selection.Font.Bold = False
            selection.Font.Color = rgb_color(45, 55, 72)  # Charcoal
            selection.TypeText(section_text + "\n\n")
            
        # Experience Section
        selection.Font.Name = "Calibri"
        selection.Font.Size = 13
        selection.Font.Bold = True
        selection.Font.Color = rgb_color(26, 54, 93)
        selection.TypeText("Professional Experience\n")
        
        for job in cv_data.get("experience", []):
            selection.Font.Name = "Calibri"
            selection.Font.Size = 11.5
            selection.Font.Bold = True
            selection.Font.Color = rgb_color(26, 54, 93)
            selection.TypeText(f"{job.get('title')} | {job.get('company')} ({job.get('dates')})\n")
            
            selection.Font.Name = "Calibri"
            selection.Font.Size = 10.5
            selection.Font.Bold = False
            selection.Font.Color = rgb_color(45, 55, 72)
            for bullet in job.get("bullets", []):
                selection.TypeText(f"   - {bullet}\n")
            selection.TypeText("\n")
            
        # Education Section
        selection.Font.Name = "Calibri"
        selection.Font.Size = 13
        selection.Font.Bold = True
        selection.Font.Color = rgb_color(26, 54, 93)
        selection.TypeText("Education\n")
        
        selection.Font.Name = "Calibri"
        selection.Font.Size = 10.5
        selection.Font.Bold = False
        selection.Font.Color = rgb_color(45, 55, 72)
        for edu in cv_data.get("education", []):
            selection.TypeText(f"   • {edu}\n")
            
        speak("Resume document completed successfully, sir.")
    except Exception as e:
        print(f"[COM CV ERROR] {e}")
        speak("Word Resume automation failed.")


# ── Action Chaining Template Resolver ──────────────────────────────────────────
def resolve_templates(data, context):
    if not context:
        return data
    if isinstance(data, str):
        for k, v in context.items():
            data = data.replace(f"{{{{{k}}}}}", str(v))
        return data
    elif isinstance(data, dict):
        return {k: resolve_templates(v, context) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_templates(item, context) for item in data]
    return data

# ── Action Executor ────────────────────────────────────────────────────────────
def execute_action(action_data, command_text="", verified=False, pipeline_context=None):
    # Initialize mouse position tracker at the start of any new action stream
    global _last_action_mouse_pos
    if _last_action_mouse_pos is None:
        _last_action_mouse_pos = pyautogui.position()

    # Pre-action human override check
    check_user_override()

    if isinstance(action_data, list):
        if not verified:
            if not verify_privacy_gate(action_data, command_text):
                return None
        if pipeline_context is None:
            pipeline_context = {}
        for item in action_data:
            resolved_item = resolve_templates(item, pipeline_context)
            res_val = execute_action(resolved_item, command_text=command_text, verified=True, pipeline_context=pipeline_context)
            if res_val is not None:
                pipeline_context["last_result"] = res_val
            time.sleep(1.0)
        return None

    if pipeline_context is not None:
        action_data = resolve_templates(action_data, pipeline_context)

    if not verified:
        if not verify_privacy_gate(action_data, command_text):
            return None

    try:
        action = action_data.get("action")

        if action == "security_block":
            reason = action_data.get("reason", "Action blocked.")
            update_status(f"SECURITY ALERT: {reason}")
            speak(action_data.get("response", "Security block active."))
            return None

        elif action == "time":
            current_time = datetime.now().strftime("%I:%M:%S %p")
            speak(f"The current time is {current_time}.")
            return current_time

        elif action == "date":
            current_date = datetime.now().strftime("%B %d, %Y")
            speak(f"Today is {current_date}.")
            return current_date

        elif action == "get_active_window":
            try:
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd).strip() if hwnd else "Desktop"
                if not title:
                    title = "Desktop"
            except Exception:
                title = "Desktop"
            speak(f"You are currently focused on {title}, sir.")
            return title

        elif action == "get_system_stats":
            import psutil
            try:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                battery = psutil.sensors_battery()
                battery_str = f"{battery.percent} percent" if battery else "not detected"
                status_msg = f"Sir, CPU is at {cpu} percent, RAM is at {ram} percent, and battery is {battery_str}."
            except Exception:
                status_msg = "I was unable to capture precise diagnostics at this instant, sir."
            speak(status_msg)
            return status_msg

        elif action == "create_note":
            content = action_data.get("content", "").strip()
            if content:
                with open("notes.txt", "a", encoding="utf-8") as nf:
                    nf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
                speak(f"Note added: {content}")
                return content
            else:
                speak("The note content was empty, sir.")
                return None

        elif action == "read_notes":
            if os.path.exists("notes.txt"):
                with open("notes.txt", "r", encoding="utf-8") as nf:
                    notes = nf.readlines()
                if notes:
                    speak("Here are your notes, sir:")
                    for note in notes[-5:]:
                        speak(note.strip())
                    return "".join(notes)
                else:
                    speak("You have no notes recorded, sir.")
                    return ""
            else:
                speak("You have no notes recorded, sir.")
                return ""

        elif action == "play_music":
            song_query = action_data.get("song_name", "").strip().lower()
            music_dir = os.path.expanduser("~/Music")
            if os.path.exists(music_dir):
                songs = [f for f in os.listdir(music_dir) if f.endswith((".mp3", ".wav", ".m4a"))]
                if songs:
                    matched_song = None
                    if song_query:
                        for s in songs:
                            if song_query in s.lower():
                                matched_song = s
                                break
                    if not matched_song:
                        matched_song = songs[0]
                    song_path = os.path.join(music_dir, matched_song)
                    speak(f"Playing {matched_song}.")
                    os.startfile(song_path)
                else:
                    speak("No audio files found in your Music folder, sir.")
            else:
                speak("Your Music directory does not exist, sir.")

        elif action == "shutdown_pc":
            speak("Shutting down the computer in 5 seconds. Goodbye, sir.")
            os.system("shutdown /s /f /t 5")

        elif action == "restart_pc":
            speak("Restarting the computer in 5 seconds, sir.")
            os.system("shutdown /r /f /t 5")

        elif action == "clean_dictation":
            raw_text = action_data.get("text", "")
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                speak("Groq API key not found to clean dictation.")
                pyautogui.write(raw_text)
            else:
                speak("Cleaning transcription.")
                try:
                    from groq import Groq
                    client = Groq(api_key=api_key)
                    res = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[
                            {"role": "system", "content": "You are a transcript editor. Clean the user's dictated voice text: remove verbal fillers (like um, uh, ah, hmmm, like), fix spacing, grammar, punctuation, and capitalization. Output ONLY the cleaned transcript with no comments or formatting wraps."},
                            {"role": "user", "content": raw_text}
                        ],
                        temperature=0.1
                    )
                    cleaned = res.choices[0].message.content.strip()
                    escaped = cleaned.replace('"', '`"').replace('$', '`$')
                    subprocess.run(["powershell", "-Command", f'Set-Clipboard -Value "{escaped}"'], shell=True)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'v')
                    speak("Dictated text pasted.")
                except Exception as de:
                    print(f"Dictation cleaning failed: {de}")
                    pyautogui.write(raw_text)
            update_action_mouse_pos()

        elif action == "whatsapp_send":
            contact = action_data.get("contact", "")
            message = action_data.get("message", "")
            speak(f"Sending WhatsApp message to {contact}.")
            subprocess.Popen(["powershell", "-Command", "start whatsapp:"], shell=True)
            time.sleep(3.0)
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.5)
            pyautogui.write(contact)
            time.sleep(1.0)
            pyautogui.press('enter')
            time.sleep(1.0)
            pyautogui.write(message)
            time.sleep(0.5)
            pyautogui.press('enter')
            speak("Message dispatched, sir.")
            update_action_mouse_pos()

        elif action == "check_price":
            product = action_data.get("product_name", "").strip()
            speak(f"Checking online prices for {product}...")
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(f"{product} price online", max_results=3))
                if results:
                    snippet = results[0]["body"]
                    speak(f"Found product details: {snippet[:150]}")
                else:
                    speak("Could not retrieve price from online listings.")
            except Exception:
                speak("Search index query failed, sir.")

        elif action == "track_price":
            product = action_data.get("product_name", "").strip()
            watchlist_file = "watchlist.json"
            watchlist = []
            if os.path.exists(watchlist_file):
                try:
                    with open(watchlist_file, "r") as wf:
                        watchlist = json.load(wf)
                except Exception:
                    pass
            watchlist.append({"product": product, "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
            with open(watchlist_file, "w") as wf:
                json.dump(watchlist, wf, indent=2)
            speak(f"Added {product} to your price watchlist, sir.")

        elif action == "check_watchlist":
            watchlist_file = "watchlist.json"
            if os.path.exists(watchlist_file):
                try:
                    with open(watchlist_file, "r") as wf:
                        watchlist = json.load(wf)
                    if watchlist:
                        speak("Your watchlist items are:")
                        for item in watchlist:
                            speak(item["product"])
                    else:
                        speak("Your watchlist is empty, sir.")
                except Exception:
                    speak("Failed to read your watchlist.")
            else:
                speak("Your watchlist is empty, sir.")

        elif action == "search_reason":
            query = action_data.get("query", "")
            speak(f"Searching web resources for {query}...")
            update_status("REASONING...")
            wiki_summary = ""
            try:
                import wikipedia
                wiki_summary = wikipedia.summary(query, sentences=3)
            except Exception:
                pass
            web_snippets = ""
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    ddg_res = list(ddgs.text(query, max_results=3))
                if ddg_res:
                    web_snippets = "\n".join([r["body"] for r in ddg_res])
            except Exception:
                pass
            context = f"Wikipedia:\n{wiki_summary}\n\nWeb Search:\n{web_snippets}"
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    selected_model = "llama-3.3-70b-versatile"
                    config_path = "config.json"
                    if os.path.exists(config_path):
                        try:
                            with open(config_path, "r") as cf:
                                cfg = json.load(cf)
                                selected_model = cfg.get("selected_model", "llama-3.3-70b-versatile")
                        except Exception:
                            pass
                    from groq import Groq
                    client = Groq(api_key=api_key)
                    res = client.chat.completions.create(
                        model=selected_model,
                        messages=[
                            {"role": "system", "content": "You are J.A.R.V.I.S. Synthesize the provided search context and answer the query. You MUST think deep. Place your inner reasoning steps inside <think>...</think> tags. After the closing </think> tag, output your concise final verbal answer (under 50 words) to speak to the user. Speak like a Stark-level companion."},
                            {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
                        ],
                        temperature=0.2,
                        max_tokens=1024
                    )
                    response_text = res.choices[0].message.content.strip()
                    thoughts = ""
                    if "<think>" in response_text and "</think>" in response_text:
                        parts = response_text.split("</think>", 1)
                        thoughts = parts[0].replace("<think>", "").strip()
                        verbal_reply = parts[1].strip()
                    else:
                        verbal_reply = response_text
                    if thoughts:
                        with open("thoughts.txt", "w", encoding="utf-8") as tf:
                            tf.write(thoughts)
                    speak(verbal_reply)
                    return verbal_reply
                except Exception as se:
                    print(f"Reasoning synthesis failed: {se}")
                    speak("I encountered an issue combining the search results, sir.")
                    return context
            else:
                speak("Could not reach online services without Groq keys.")
                return context

        elif action == "joke":
            joke_text = action_data.get("text", "I forgot the joke.")
            speak(joke_text, rate=-2)
            return joke_text

        elif action == "chat":
            chat_resp = action_data.get("response", "I'm here.")
            speak(chat_resp)
            return chat_resp

        elif action == "chrome_profile":
            pid = action_data.get("profile_id")
            url = action_data.get("url", "")
            pid_str = str(pid).strip().lower() if pid else ""
            
            # Workspace specific override
            if pid_str in ["3", "third", "three"] and 3 in PROFILE_FOLDER_MAP:
                speak("Opening your workspace.")
                os.startfile(PROFILE_FOLDER_MAP[3])
                return

            profile_dir = None
            if pid_str in ["1", "first", "one"]:
                profile_dir = "Default"
            elif pid_str in ["2", "second", "two"]:
                profile_dir = "Profile 1"
            elif pid_str in ["3", "third", "three"]:
                profile_dir = "Profile 2"
            elif pid_str in ["4", "fourth", "four"]:
                profile_dir = "Profile 3"
            elif pid_str in ["5", "fifth", "five"]:
                profile_dir = "Profile 4"
            elif pid_str in ["last", "latest"]:
                profile_dir = None
            else:
                try:
                    val = int(pid)
                    if val == 1:
                        profile_dir = "Default"
                    else:
                        profile_dir = f"Profile {val - 1}"
                except:
                    profile_dir = None

            # Resolve absolute Chrome path for extreme reliability
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
            chrome_exe = None
            for p in chrome_paths:
                if os.path.exists(p):
                    chrome_exe = p
                    break

            if chrome_exe is None:
                speak("Chrome path not detected. Trying fallback.")
                cmd_str = 'start "" chrome'
                if profile_dir:
                    cmd_str += f' --profile-directory="{profile_dir}"'
                if url:
                    cmd_str += f' "{url}"'
                subprocess.Popen(cmd_str, shell=True)
            else:
                if pid_str in ["last", "default", ""]:
                    speak("Opening Google Chrome.")
                else:
                    speak(f"Opening Chrome profile {pid_str}.")
                args = [chrome_exe]
                if profile_dir:
                    args.append(f"--profile-directory={profile_dir}")
                if url:
                    args.append(url)
                subprocess.Popen(args)

        elif action == "play_playlist":
            pid = action_data.get("profile_id", 1)
            pid_str = str(pid).strip().lower()
            
            profile_dir = "Default"
            if pid_str in ["1", "first", "one"]:
                profile_dir = "Default"
            elif pid_str in ["2", "second", "two"]:
                profile_dir = "Profile 1"
            elif pid_str in ["3", "third", "three"]:
                profile_dir = "Profile 2"
            elif pid_str in ["4", "fourth", "four"]:
                profile_dir = "Profile 3"
            else:
                try:
                    val = int(pid)
                    if val == 1:
                        profile_dir = "Default"
                    else:
                        profile_dir = f"Profile {val - 1}"
                except:
                    profile_dir = "Default"
                    
            # Resolve absolute Chrome path for extreme reliability
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
            chrome_exe = None
            for p in chrome_paths:
                if os.path.exists(p):
                    chrome_exe = p
                    break

            speak("Opening YouTube.")
            url = "https://www.youtube.com"
            if chrome_exe is None:
                cmd_str = f'start "" chrome --profile-directory="{profile_dir}" "{url}"'
                subprocess.Popen(cmd_str, shell=True)
            else:
                args = [chrome_exe, f"--profile-directory={profile_dir}", url]
                subprocess.Popen(args)

        elif action == "write_code":
            speak("Writing code now.")
            final_code = action_data.get("code_override", "")
            if not final_code:
                code_prompt = action_data.get("prompt", "")
                from groq import Groq
                try:
                    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                    res = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": "You are a senior software engineer. Output ONLY valid, runnable, raw Python code with NO markdown, NO backticks (```), and NO explanation. If the user asks for a game, make it a fully featured, interactive, polished game using standard libraries like Tkinter. Ensure all features, game loops, event handling, scoreboards, and restart options are fully implemented, and the code is 100% complete and ready to run."},
                            {"role": "user", "content": code_prompt}
                        ],
                        temperature=0.1
                    )
                    final_code = res.choices[0].message.content
                except Exception as e:
                    speak("Error writing code.")
                    print(e)
                    final_code = ""

            if final_code:
                time.sleep(2)
                try:
                    # High performance instant code paste
                    escaped = final_code.replace('"', '`"').replace('$', '`$')
                    subprocess.run(["powershell", "-Command", f'Set-Clipboard -Value "{escaped}"'], shell=True)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'v')
                except Exception as clipboard_err:
                    print(f"Code clipboard paste error: {clipboard_err}")
                    pyautogui.write(final_code, interval=0.005)
                speak("Done.")
            update_action_mouse_pos()

        elif action == "open_bookmark":
            bid = str(action_data.get("bookmark_id", "1")).strip().lower()
            bookmarks = {
                "1": "https://www.youtube.com/playlist?list=PL4fGSI1pDJn5kI81J1yPMRyk8a_K-4d0N",
                "playlist": "https://www.youtube.com/playlist?list=PL4fGSI1pDJn5kI81J1yPMRyk8a_K-4d0N",
                "2": "https://en.wikipedia.org/wiki/Special:Random",
                "wikipedia": "https://en.wikipedia.org/wiki/Special:Random",
                "3": "https://www.daraz.pk",
                "daraz": "https://www.daraz.pk",
                "4": "https://www.daraz.pk/catalog/?q=stark+industries",
                "5": "https://mail.google.com",
                "gmail": "https://mail.google.com",
                "6": "https://www.youtube.com",
                "youtube": "https://www.youtube.com",
                "7": "https://github.com/muhammadsaadpopat"
            }
            url = bookmarks.get(bid, "https://www.google.com")
            speak(f"Opening bookmark, sir.")
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"Start-Process chrome '{url}'"], shell=True)

        elif action == "open_app":
            app = action_data.get("app_name", "").lower().strip()
            web_platforms = {
                "youtube": "https://www.youtube.com",
                "google": "https://www.google.com",
                "facebook": "https://www.facebook.com",
                "chess": "https://www.chess.com",
                "chess.com": "https://www.chess.com",
                "gmail": "https://www.gmail.com",
                "github": "https://github.com",
                "wikipedia": "https://www.wikipedia.org"
            }
            if app in web_platforms:
                speak(f"Opening {app} in Google Chrome.")
                url = web_platforms[app]
                subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"Start-Process chrome '{url}'"], shell=True)
            else:
                speak(f"Opening {app}.")
                if "code" in app or "antigravity" in app:
                    os.system("code .")
                elif "word" in app or "winword" in app or "ms word" in app:
                    os.system("start winword")
                elif "edge" in app or "msedge" in app or "microsoft edge" in app:
                    os.system("start msedge")
                elif "powerpoint" in app or "powerpnt" in app or "ppt" in app:
                    os.system("start powerpnt")
                elif "chrome" in app:
                    os.system("start chrome")
                else:
                    os.system(f"start {app}")

        elif action == "close_app":
            app = action_data.get("app_name", "").lower()
            speak(f"Closing {app}.")
            if "chrome" in app or "google" in app:
                os.system("taskkill /f /im chrome.exe")
            elif "notepad" in app:
                os.system("taskkill /f /im notepad.exe")
            elif "word" in app or "winword" in app or "ms word" in app:
                os.system("taskkill /f /im winword.exe")
            else:
                os.system(f"taskkill /f /im {app}.exe")

        elif action == "show_desktop":
            speak("Showing desktop.")
            pyautogui.hotkey('win', 'd')
            update_action_mouse_pos()

        elif action == "type_text":
            text = action_data.get("text", "")
            speak("Typing.")
            time.sleep(0.1)  # Tiny settle delay instead of 1.5 seconds!
            if len(text) < 15:
                pyautogui.write(text, interval=0.005)  # Blistering fast typing animation
            else:
                try:
                    # High performance instant paste using native Windows clipboard
                    # Escape quotes properly for PowerShell
                    escaped = text.replace('"', '`"').replace('$', '`$')
                    subprocess.run(["powershell", "-Command", f'Set-Clipboard -Value "{escaped}"'], shell=True)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'v')
                except Exception as e:
                    print(f"Clipboard paste error: {e}")
                    pyautogui.write(text, interval=0.005)
            update_action_mouse_pos()

        elif action == "switch_tab":
            direction = action_data.get("direction", "next").lower()
            speak("Switching tab.")
            if "prev" in direction or "back" in direction or "doosre" in direction:
                pyautogui.hotkey('ctrl', 'shift', 'tab')
            else:
                pyautogui.hotkey('ctrl', 'tab')
            update_action_mouse_pos()

        elif action == "create_slide":
            speak("Creating slide.")
            pyautogui.hotkey('ctrl', 'm')
            update_action_mouse_pos()

        elif action == "click":
            x = action_data.get("x")
            y = action_data.get("y")
            target = action_data.get("target", "").lower()
            if target == "center":
                w, h = pyautogui.size()
                pyautogui.click(w // 2, h // 2)
                speak("Clicked center.")
            elif x is not None and y is not None:
                pyautogui.click(int(x), int(y))
                speak("Clicked coordinates.")
            else:
                pyautogui.click()
                speak("Clicked.")
            update_action_mouse_pos()

        elif action == "click_button":
            button_name = action_data.get("button_name", "")
            speak(f"Clicking {button_name}.")
            # Highly advanced UI Automation script in PowerShell to locate and click any UI Element/Button by name!
            ps_cmd = (
                f"Add-Type -AssemblyName UIAutomationClient; "
                f"Add-Type -AssemblyName UIAutomationTypes; "
                f"$cond = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty, '{button_name}'); "
                f"$el = [Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Subtree, $cond); "
                f"if ($el -ne $null) {{ "
                f"  try {{ "
                f"    $inv = $el.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern); "
                f"    $inv.Invoke(); "
                f"  }} catch {{ "
                f"    $rect = $el.Current.BoundingRectangle; "
                f"    $x = [int]($rect.Left + ($rect.Width / 2)); "
                f"    $y = [int]($rect.Top + ($rect.Height / 2)); "
                f"    [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($x, $y); "
                f"    $assem = [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
                f"    [System.Windows.Forms.SendKeys]::SendWait('~'); " # fallback press enter
                f"  }} "
                f"}}"
            )
            subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-Command', ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            update_action_mouse_pos()

        elif action == "press_key":
            key = action_data.get("key", "").lower()
            if key:
                pyautogui.press(key)
                speak(f"Pressed {key}.")
            update_action_mouse_pos()

        elif action == "hotkey":
            keys = action_data.get("keys", [])
            if keys:
                pyautogui.hotkey(*keys)
                speak("Triggered key combination.")
            update_action_mouse_pos()

        elif action == "click_first_link":
            speak("Clicking first result.")
            time.sleep(1.5)  # Wait for page to load
            for _ in range(15):  # Usually 14-16 tabs to hit the first Google search result title
                pyautogui.press('tab')
                time.sleep(0.02)
            pyautogui.press('enter')
            update_action_mouse_pos()

        elif action == "wait":
            secs = float(action_data.get("seconds", 1.0))
            time.sleep(secs)

        elif action == "open_file":
            should_search = action_data.get("search", True)
            if not should_search:
                file_path = action_data.get("file_path", "")
                if os.path.exists(file_path):
                    speak("Opening.")
                    os.startfile(file_path)
                else:
                    speak("File not found.")
            else:
                file_name = action_data.get("file_name", "")
                speak(f"Searching for {file_name}.")
                update_status(f"SEARCHING: {file_name}...")
                found = None
                for search_dir in CUSTOM_SEARCH_DIRS:
                    if not os.path.exists(search_dir):
                        continue
                    for root, dirs, files in os.walk(search_dir):
                        depth = root.replace(search_dir, "").count(os.sep)
                        if depth > 4:
                            continue
                        for f in files:
                            if file_name.lower() in f.lower():
                                found = os.path.join(root, f)
                                break
                        if found:
                            break
                    if found:
                        break
                if found:
                    speak("Got it.")
                    os.startfile(found)
                else:
                    speak(f"Couldn't find {file_name}.")

        elif action == "open_folder":
            folder_name = action_data.get("folder", "").lower()
            folder_map = {
                "downloads":  os.path.expanduser("~/Downloads"),
                "documents":  os.path.expanduser("~/Documents"),
                "desktop":    os.path.expanduser("~/Desktop"),
                "pictures":   os.path.expanduser("~/Pictures"),
                "music":      os.path.expanduser("~/Music"),
                "videos":     os.path.expanduser("~/Videos"),
                "saad":       r"C:\Users\DELL\Desktop\saad\saad",
            }
            path = folder_map.get(folder_name)
            if path and os.path.exists(path):
                speak(f"Opening {folder_name}.")
                os.startfile(path)
            elif os.path.exists(folder_name):
                speak("Opening folder.")
                os.startfile(folder_name)
            else:
                speak("Folder not found.")

        elif action == "screenshot":
            speak("Done.")
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            pyautogui.screenshot(filename)

        elif action == "lock_screen":
            speak("Locking.")
            os.system("rundll32.exe user32.dll,LockWorkStation")

        elif action == "run_command":
            cmd = action_data.get("command", "")
            speak_after = action_data.get("speak_after", "Command executed.")
            update_status(f"EXEC: {cmd[:40]}")
            try:
                subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], shell=True)
                speak(speak_after)
            except Exception as e:
                speak("Failed to run system command.")
                print(e)

        elif action == "volume":
            vol_type = action_data.get("type", "mute")
            if vol_type == "up":
                for _ in range(5): pyautogui.press("volumeup")
                speak("Up.")
            elif vol_type == "down":
                for _ in range(5): pyautogui.press("volumedown")
                speak("Down.")
            else:
                pyautogui.press("volumemute")
                speak("Muted.")

        elif action == "send_email":
            to_email  = action_data.get("to")
            subject   = action_data.get("subject", "Mail from JARVIS")
            body      = action_data.get("body", "")
            sender    = os.getenv("SENDER_EMAIL")
            passwd    = os.getenv("SENDER_APP_PASSWORD")
            if not sender or not passwd:
                speak("Email not configured.")
            else:
                speak("Sending.")
                import smtplib
                from email.mime.text import MIMEText
                try:
                    msg = MIMEText(body)
                    msg['Subject'] = subject
                    msg['From']    = sender
                    msg['To']      = to_email
                    server = smtplib.SMTP('smtp.gmail.com', 587)
                    server.ehlo(); server.starttls()
                    server.login(sender, passwd)
                    server.sendmail(sender, [to_email], msg.as_string())
                    server.close()
                    speak("Sent.")
                except Exception as e:
                    speak("Failed to send.")
                    print(e)

        elif action == "system_off":
            speak("Goodbye. Deactivated.")
            update_status("STANDBY")
            time.sleep(2)
            os._exit(0)

        elif action == "self_destruct":
            speak("Confirm with your passphrase.")
            update_status("AWAITING AUTHORIZATION...")
            record_dynamic_audio("temp_passcode.wav", max_duration=8.0, silence_duration=0.8)
            r2 = sr.Recognizer()
            try:
                with sr.AudioFile("temp_passcode.wav") as src:
                    audio_pass = r2.record(src)
                vocal_pass = r2.recognize_google(audio_pass, language="en-IN").lower()
                configured = os.getenv("VOICE_SECURITY_PASSCODE", "alpha nine").lower()
                valid_passcodes = [configured, "alpha nine", "alpha 9", "0909", "destroy", "yes"]
                if any(pc in vocal_pass for pc in valid_passcodes):
                    speak("Verified. Farewell.")
                    update_status("SELF DESTRUCT...")
                    cmd = f'Start-Sleep -Seconds 2; Remove-Item -Recurse -Force "{os.getcwd()}"'
                    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], shell=True)
                    os._exit(0)
                else:
                    speak("Denied. Aborted.")
            except Exception as e:
                speak("Timeout. Aborted.")
                print(e)

        elif action == "create_powerpoint":
            topic = action_data.get("topic", "General Presentation")
            create_powerpoint_com(topic)

        elif action == "create_excel":
            topic = action_data.get("topic", "Data Model")
            create_excel_com(topic)

        elif action == "create_cv":
            job_title = action_data.get("job_title", "Software Engineer")
            create_cv_com(job_title)

        elif action == "startup_protocol":
            speak("Initiating Stark morning startup sequence, Master Saad.")
            # 1. Chrome
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Start-Process chrome"], shell=True)
            time.sleep(1.0)
            # 2. WhatsApp
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "start whatsapp:"], shell=True)
            time.sleep(1.0)
            # 3. Workspace folder
            workspace = r"C:\Users\DELL\Desktop\saad\saad"
            if os.path.exists(workspace):
                os.startfile(workspace)
            # 4. VS Code (opening the current JARVIS project or workspace)
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "code ."], shell=True)
            speak("All systems active. Morning briefing loaded, sir.")

        elif action == "system_diagnostic":
            speak("Initiating diagnostic sweep and system optimization, sir.")
            update_status("DIAGNOSTICS...")
            
            # Safe Clean Temp
            import shutil
            temp_dir = os.environ.get("TEMP")
            cleaned_mb = 0
            if temp_dir and os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            fsize = os.path.getsize(fp)
                            os.remove(fp)
                            cleaned_mb += fsize
                        except Exception:
                            pass # File locked by another process
            cleaned_mb = round(cleaned_mb / (1024 * 1024), 2)
            
            # RAM/CPU stats
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            ram_percent = ram.percent
            
            # Find heaviest process
            heaviest_proc = "Unknown"
            heaviest_mem = 0
            try:
                for proc in psutil.process_iter(['name', 'memory_info']):
                    try:
                        mem = proc.info['memory_info'].rss
                        if mem > heaviest_mem:
                            heaviest_mem = mem
                            heaviest_proc = proc.info['name']
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except Exception:
                pass
            
            heaviest_proc_mb = round(heaviest_mem / (1024 * 1024), 1)
            
            speak(f"Optimization complete, Master. System status: CPU is at {cpu_percent} percent, memory load is {ram_percent} percent. Safe-cleared {cleaned_mb} Megabytes of temporary files. {heaviest_proc} is currently your heaviest process.")
            
            # Write to thoughts.txt so it shows on the UI
            with open("thoughts.txt", "w", encoding="utf-8") as tf:
                tf.write(f"SYSTEM OPTIMIZATION REPORT:\n"
                         f"---------------------------\n"
                         f"CPU Usage: {cpu_percent}%\n"
                         f"Memory Load: {ram_percent}%\n"
                         f"Heaviest Process: {heaviest_proc} ({heaviest_proc_mb} MB)\n"
                         f"Cache Files Cleared: {cleaned_mb} MB\n"
                         f"Status: Fully Optimized (Stark-grade)")
            update_action_mouse_pos()

        elif action == "summarize_webpage":
            url = action_data.get("url", "")
            speak(f"Accessing website, reading page data, sir.")
            update_status("READING WEBPAGE...")
            
            summary = "Failed to scrape page content."
            try:
                import urllib.request
                from bs4 import BeautifulSoup
                
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                )
                with urllib.request.urlopen(req, timeout=8) as response:
                    html = response.read()
                
                soup = BeautifulSoup(html, "html.parser")
                paragraphs = soup.find_all('p')
                page_text = " ".join([p.get_text() for p in paragraphs[:8]])
                page_text = re.sub(r'\s+', ' ', page_text).strip()
                title = soup.title.string if soup.title else "Webpage"
                
                if len(page_text) > 100:
                    api_key = os.getenv("GROQ_API_KEY")
                    if api_key:
                        from groq import Groq
                        client = Groq(api_key=api_key)
                        res = client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[
                                {"role": "system", "content": "You are J.A.R.V.I.S. Summarize the provided webpage content in a highly concise manner (under 50 words) for Master Saad. Be direct, factual, and Stark-like."},
                                {"role": "user", "content": f"Title: {title}\nContent: {page_text[:3000]}"}
                            ],
                            temperature=0.3,
                            max_tokens=200
                        )
                        summary = res.choices[0].message.content.strip()
                    else:
                        summary = f"Read page: {title}. Raw summary: {page_text[:150]}..."
                else:
                    summary = "The page did not contain enough text content to summarize, sir."
            except Exception as se:
                print(f"Scraper error: {se}")
                summary = "I failed to retrieve or parse the webpage content, sir."
                
            speak(summary)
            with open("thoughts.txt", "w", encoding="utf-8") as tf:
                tf.write(f"WEBPAGE SUMMARY: {url}\n"
                         f"----------------------------------------\n"
                         f"{summary}")
            update_action_mouse_pos()
            return summary

        elif action == "get_active_window":
            speak("Scanning foreground processes, sir.")
            update_status("SCANNING FOREGROUND...")
            ps_cmd = (
                "$code = '[DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow(); "
                "[DllImport(\"user32.dll\")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);'; "
                "Add-Type -MemberDefinition $code -Name \"Win32\" -Namespace \"Win\" -ErrorAction SilentlyContinue; "
                "$builder = New-Object System.Text.StringBuilder(256); "
                "[Win.Win32]::GetWindowText([Win.Win32]::GetForegroundWindow(), $builder, 256); "
                "$builder.ToString()"
            )
            title = "Desktop/System"
            try:
                res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, shell=True)
                title = res.stdout.strip()
                if not title:
                    title = "Desktop/System"
                
                speak(f"Your screen focus is currently on the application: {title}, sir.")
                with open("thoughts.txt", "w", encoding="utf-8") as tf:
                    tf.write(f"ACTIVE WINDOW CONTEXT:\n"
                             f"----------------------\n"
                             f"Focused App: {title}\n"
                             f"Status: Active Session Monitoring")
            except Exception as e:
                speak("I failed to query the active process list.")
                print(e)
            update_action_mouse_pos()
            return title

        elif action == "get_system_stats":
            speak("Querying hardware diagnostics, sir.")
            update_status("QUERYING TELEMETRY...")
            try:
                import psutil
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                battery = psutil.sensors_battery()
                
                bat_str = ""
                if battery:
                    bat_str = f"Battery is at {battery.percent} percent and is {'charging' if battery.power_plugged else 'discharging'}."
                else:
                    bat_str = "Power line is secured on A.C. power."

                diagnostic_speak = f"Hardware diagnostics report: C.P.U utilization is at {cpu} percent. R.A.M load is currently {ram} percent. {bat_str}"
                speak(diagnostic_speak)
                
                with open("thoughts.txt", "w", encoding="utf-8") as tf:
                    tf.write(f"SYSTEM TELEMETRY REPORT:\n"
                             f"------------------------\n"
                             f"CPU Util: {cpu}%\n"
                             f"RAM Load: {ram}%\n"
                             f"Power: {bat_str}\n\n"
                             f"Diagnostics status: Secured")
            except Exception as e:
                speak("Failed to query hardware diagnostics, sir.")
                print(e)
            update_action_mouse_pos()
            return

        elif action == "remember":
            fact = action_data.get("fact", "").strip()
            if fact:
                from ai_brain import load_memory, save_memory
                mem = load_memory()
                if fact not in mem.get("user_facts", []):
                    mem.setdefault("user_facts", []).append(fact)
                    save_memory(mem)
                speak(f"I will store that in my semantic memory banks, Sir: {fact}")
                return fact
            else:
                speak("No fact was provided to remember, sir.")
                return None

        elif action == "forget":
            fact = action_data.get("fact", "").strip()
            if fact:
                from ai_brain import load_memory, save_memory
                mem = load_memory()
                found = False
                for f in list(mem.get("user_facts", [])):
                    if fact.lower() in f.lower():
                        mem["user_facts"].remove(f)
                        found = True
                if found:
                    save_memory(mem)
                    speak(f"I've purged that fact from my databases, sir.")
                    return f"Purged: {fact}"
                else:
                    speak("I couldn't find a matching fact in my memory, sir.")
                    return None
            else:
                speak("No fact was provided to forget, sir.")
                return None

        elif action == "news_briefing":
            from news import speak_news
            speak_news()
            return "News briefing completed."

        elif action == "weather_report":
            from helpers import weather
            weather()
            return "Weather report completed."

        elif action == "dictionary_translate":
            word = action_data.get("word", "").strip()
            if word:
                from helpers import translate
                translate(word)
                return f"Translated word: {word}"
            else:
                speak("Please state the word you want to translate, sir.")
                return None

        elif action == "ocr_scan":
            speak("Initializing OCR camera scan, sir. Press Q in the camera view window to close it.")
            from OCR import OCR
            OCR()
            speak("OCR camera feed closed.")
            return "OCR scan completed."

        elif action == "download_youtube":
            url = action_data.get("url", "").strip()
            if url:
                from helpers import download_youtube_video
                download_youtube_video(url)
                return f"Downloaded video from {url}"
            else:
                speak("No video URL was provided, sir.")
                return None

        elif action == "change_voice":
            gender = action_data.get("gender", "male").strip().lower()
            if gender in ["male", "female", "jarvis", "friday"]:
                mapped_gender = "female" if gender in ["female", "friday"] else "male"
                from config import Config
                config_path = "config.json"
                cfg_data = {}
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r") as cf:
                            cfg_data = json.load(cf)
                    except:
                        pass
                cfg_data["voice_gender"] = mapped_gender
                try:
                    with open(config_path, "w") as cf:
                        json.dump(cfg_data, cf, indent=4)
                except:
                    pass
                Config.set_env_value("voice_gender", mapped_gender)
                char_name = "FRIDAY" if mapped_gender == "female" else "JARVIS"
                speak(f"Switching voice protocols. {char_name} voice interface is now online.")
                return f"Voice character changed to {char_name}."

        elif action == "error":
            speak("Error processing that.")
            print(action_data.get("message"))
            return None

        else:
            speak("No handler for that command.")
            return None

    except Exception as err:
        speak("Critical error.")
        print(f"[EXEC ERROR] {err}")


# ── Audio Recording ───────────────────────────────────────────────────────────
def record_dynamic_audio(filename="temp.wav", max_duration=8.0, silence_duration=0.6):
    """Records until silence_duration of quiet after speech, or max_duration timeout."""
    # Wait for active speech to finish to prevent microphone self-echo/interruption
    while is_speaking():
        time.sleep(0.1)

    # Always delete stale file first to prevent duplicate/loop command replay bugs
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception as e:
            print(f"[AUDIO ERROR] Could not clear stale {filename}: {e}")

    fs = 44100
    q  = queue.Queue()

    def callback(indata, frames, time_info, status):
        q.put(indata.copy())

    try:
        stream = sd.InputStream(samplerate=fs, channels=1, dtype='int16', callback=callback)
    except Exception as stream_err:
        logger.error(f"[AUDIO STREAM ERROR] Failed to start input device: {stream_err}")
        update_status("ERROR: Mic Disconnected")
        time.sleep(3)
        return

    audio_data     = []
    speech_started = False
    silence_count  = 0
    silence_limit  = int(silence_duration * fs / 1024)

    # Map mic sensitivity threshold dynamically
    from config import Config
    try:
        mic_config = float(Config.get("mic_threshold", 0.38))
    except Exception:
        mic_config = 0.38
    base_threshold = int(100 + mic_config * 900)

    with stream:
        t0 = time.time()
        while time.time() - t0 < max_duration:
            try:
                block = q.get(timeout=0.1)
                audio_data.append(block)
                amp = np.max(np.abs(block))
                
                # Check for UI/vocal interruption
                interrupted = check_interrupted()
                # Interruption threshold is slightly higher when speaking to prevent self-echo interruption
                current_threshold = int(base_threshold * 1.8) if is_speaking() else base_threshold
                
                if amp > current_threshold or interrupted:
                    if is_speaking():
                        stop_speaking()
                    speech_started = True
                    silence_count  = 0
                    if interrupted:
                        # Exit the recording loop immediately on UI interruption
                        break
                elif speech_started:
                    silence_count += 1
                    if silence_count >= silence_limit:
                        break
            except queue.Empty:
                pass

    if audio_data:
        wav.write(filename, fs, np.concatenate(audio_data, axis=0))
    else:
        wav.write(filename, fs, np.zeros((1024, 1), dtype='int16'))

# ── Context Activity & Telemetry suggestion daemons ──────────────────────────
def active_activity_tracker():
    import json
    import os
    import time
    try:
        import win32gui
    except ImportError:
        return
        
    activity_file = "activity_patterns.json"
    while True:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    app_name = "Desktop"
                    title_lower = title.lower()
                    if "chrome" in title_lower:
                        app_name = "Chrome Browser"
                    elif "edge" in title_lower:
                        app_name = "Edge Browser"
                    elif "visual studio code" in title_lower or "vscode" in title_lower or "code ." in title_lower:
                        app_name = "VS Code"
                    elif "notepad" in title_lower:
                        app_name = "Notepad"
                    elif "word" in title_lower or "winword" in title_lower:
                        app_name = "MS Word"
                    elif "powerpoint" in title_lower or "powerpnt" in title_lower:
                        app_name = "MS PowerPoint"
                    elif "excel" in title_lower or "excel.exe" in title_lower:
                        app_name = "MS Excel"
                    elif "streamlit" in title_lower or "j.a.r.v.i.s" in title_lower:
                        app_name = "JARVIS Panel"
                    else:
                        parts = title.split(" - ")
                        app_name = parts[-1].strip()[:30]

                    patterns = {}
                    if os.path.exists(activity_file):
                        try:
                            with open(activity_file, "r", encoding="utf-8") as af:
                                patterns = json.load(af)
                        except Exception:
                            pass
                    
                    patterns[app_name] = patterns.get(app_name, 0) + 1
                    with open(activity_file, "w", encoding="utf-8") as af:
                        json.dump(patterns, af, indent=4)
        except Exception:
            pass
        time.sleep(10.0)

def telemetry_suggestion_engine():
    import time
    import os
    import psutil
    while True:
        try:
            suggestions = []
            
            # 1. RAM check
            ram = psutil.virtual_memory()
            if ram.percent > 85.0:
                suggestions.append(f"High RAM Usage detected: {ram.percent}%. Suggest system optimization.")
                
            # 2. Disk Space check
            try:
                disk = psutil.disk_usage('C:\\')
                free_percent = (disk.free / disk.total) * 100.0
                if free_percent < 15.0:
                    suggestions.append(f"Low Disk Space: {free_percent:.1f}% free remaining. Clear temporary files.")
            except Exception:
                pass
                
            # 3. CPU Load check
            cpu = psutil.cpu_percent(interval=1.0)
            if cpu > 90.0:
                suggestions.append(f"Critical CPU load: {cpu}%. Close heavy tasks.")
                
            # 4. Battery level check
            try:
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged and battery.percent < 25.0:
                    suggestions.append(f"Low system battery: {battery.percent}% remaining. Connect to AC power, sir.")
            except Exception:
                pass
                
            with open("suggestions.txt", "w", encoding="utf-8") as sf:
                if suggestions:
                    sf.write("\n".join(suggestions))
                else:
                    sf.write("All systems nominal. No optimizations currently required.")
        except Exception as e:
            print(f"[Telemetry suggestion error] {e}")
        time.sleep(30.0)

# ── Main Listen Loop ────────────────────────────────────────────────────────
def listen_loop():
    global _voice_engine_running, _whatsapp_watcher_running, _trackers_started
    if "_trackers_started" not in globals():
        _trackers_started = False

    if _voice_engine_running:
        print("[SYSTEM] Duplicate voice thread aborted. Voice loop is already active.")
        return
    _voice_engine_running = True

    import threading
    if not _whatsapp_watcher_running:
        _whatsapp_watcher_running = True
        t_watcher = threading.Thread(target=whatsapp_watcher, daemon=True)
        t_watcher.start()

    if not _trackers_started:
        _trackers_started = True
        t_active = threading.Thread(target=active_activity_tracker, daemon=True)
        t_active.start()
        t_telemetry = threading.Thread(target=telemetry_suggestion_engine, daemon=True)
        t_telemetry.start()

    try:
        r = sr.Recognizer()
        
        # Load user set mic threshold
        from config import Config
        try:
            mic_config = float(Config.get("mic_threshold", 0.38))
        except Exception:
            mic_config = 0.38
        r.energy_threshold = int(100 + mic_config * 900)
        r.dynamic_energy_threshold = False

        WAKE_WORDS   = [
            "jarvis", "wakeup", "wake up", "daddy's home", "daddys home",
            "daddy is home", "daddies home", "wake-up", "hi jarvis", "hello jarvis",
            "jarvis kholo", "jarvis suno", "activate", "activated", "wake up ladies"
        ]
        EXIT_CONV    = ["stop listening", "go idle", "standby"]
        POWEROFF     = ["system shutdown", "poweroff", "power off", "go to sleep", "shutdown"]
        SELFDESTRUCT = ["initiate self destruct", "self destruct", "initiate destruct"]

        while True:
            try:
                # Reload threshold dynamically in case of mid-session slider changes
                try:
                    mic_config = float(Config.get("mic_threshold", 0.38))
                except Exception:
                    mic_config = 0.38
                r.energy_threshold = int(100 + mic_config * 900)

                # ── Phase 1: Wait for wake word ──────────────────────────────────
                update_status("STANDBY")
                record_dynamic_audio("temp.wav", max_duration=5.0, silence_duration=0.8)

                if not os.path.exists("temp.wav"):
                    continue

                with sr.AudioFile("temp.wav") as src:
                    audio = r.record(src)
                try:
                    text = transcribe_audio(r, audio).lower()
                    print(f"[HEARD] {text}")
                except sr.UnknownValueError:
                    continue
                except Exception as req_err:
                    print(f"[DEBUG] API Error: {req_err}")
                    continue

                # ── Power-off check (requires wake word) ────────────────────────
                if any(w in text for w in POWEROFF) and "jarvis" in text:
                    execute_action({"action": "system_off"})
                    continue

                # ── Self-destruct check (requires wake word) ────────────────────
                if any(w in text for w in SELFDESTRUCT) and "jarvis" in text:
                    execute_action({"action": "self_destruct"})
                    continue

                # Check if any wake word is in the heard text
                has_wake = False
                for w in WAKE_WORDS:
                    if w in text:
                        has_wake = True
                        break

                if not has_wake:
                    continue

                speak("Activated. Yes, sir. How may I help you?")

                # ── Phase 2: Conversation Mode — no "Jarvis" needed again ────────
                update_status("ACTIVE")
                last_interaction_time = time.time()

                while True:
                    # Custom Deactivation Logic
                    if time.time() - last_interaction_time > 60:
                        speak("Master, are you here? Any work for me?")
                        update_status("AWAITING REPLY...")
                        record_dynamic_audio("temp_reply.wav", max_duration=5.0, silence_duration=0.8)
                        
                        try:
                            if not os.path.exists("temp_reply.wav"):
                                raise Exception("No audio")
                            with sr.AudioFile("temp_reply.wav") as src:
                                audio_reply = r.record(src)
                            reply = transcribe_audio(r, audio_reply).lower()
                            print(f"[TIMEOUT REPLY] {reply}")
                            
                            if any(w in reply for w in ["no", "nahi", "nothing", "no work"]):
                                speak("Can I deactivate?")
                                record_dynamic_audio("temp_reply2.wav", max_duration=5.0, silence_duration=0.8)
                                try:
                                    if not os.path.exists("temp_reply2.wav"):
                                        raise Exception("No audio")
                                    with sr.AudioFile("temp_reply2.wav") as src:
                                        audio_reply2 = r.record(src)
                                    reply2 = transcribe_audio(r, audio_reply2).lower()
                                    if any(w in reply2 for w in ["yes", "haan", "sure", "deactivate", "yup", "ok"]):
                                        speak("Standby.")
                                        break  # Breaks back to Phase 1
                                    else:
                                        last_interaction_time = time.time()
                                        continue
                                except Exception:
                                    last_interaction_time = time.time()
                                    continue
                            elif any(w in reply for w in ["yes", "haan", "yeah"]):
                                speak("Yes sir?")
                                last_interaction_time = time.time()
                                continue
                            else:
                                # User said a command directly
                                last_interaction_time = time.time()
                                # Instead of dropping it, we can execute it, but for simplicity we continue loop
                                continue
                        except Exception:
                            # Silence
                            speak("Going to standby.")
                            break

                    update_status("LISTENING...")
                    record_dynamic_audio("temp.wav", max_duration=8.0, silence_duration=0.5)

                    if not os.path.exists("temp.wav"):
                        continue

                    with sr.AudioFile("temp.wav") as src:
                        audio_cmd = r.record(src)

                    try:
                        cmd_text = transcribe_audio(r, audio_cmd).lower().strip()
                        print(f"[CMD] {cmd_text}")
                        try:
                            with open("last_heard.txt", "w", encoding="utf-8") as lf:
                                lf.write(cmd_text)
                        except Exception:
                            pass
                        
                        # Ignore common static hallucinations or random non-command words
                        if cmd_text in ["i love you", "tell me i love you", "thank you", "chalo", "hello", "hi", "yes", "no", "ok", "okay", "please"]:
                            print("[DEBUG] Ignoring ambient static/hallucination.")
                            continue
                    except sr.UnknownValueError:
                        continue

                    # Power-off inside conversation (requires short phrasing or explicit wake word)
                    if any(w in cmd_text for w in POWEROFF) and (len(cmd_text.split()) < 4 or "jarvis" in cmd_text):
                        execute_action({"action": "system_off"})
                        break

                    # Self-destruct inside conversation (requires short phrasing or explicit wake word)
                    if any(w in cmd_text for w in SELFDESTRUCT) and (len(cmd_text.split()) < 4 or "jarvis" in cmd_text):
                        execute_action({"action": "self_destruct"})
                        break

                    # Exit conversation
                    if any(w in cmd_text for w in EXIT_CONV):
                        speak("Standby.")
                        break

                    # Re-wake / Clean command from wake words
                    has_re_wake = False
                    cleaned_cmd = cmd_text
                    for w in WAKE_WORDS:
                        if w in cmd_text:
                            has_re_wake = True
                            cleaned_cmd = cleaned_cmd.replace(w, "").strip()

                    if has_re_wake:
                        last_interaction_time = time.time()
                        if not cleaned_cmd:  # User only said the wake word
                            speak("Yes, sir. How may I help you?") 
                            continue
                        else:
                            cmd_text = cleaned_cmd  

                    # Process command
                    update_status(f"CMD: {cmd_text[:70]}")
                    action = process_command_with_llm(cmd_text)
                    execute_action(action)
                    last_interaction_time = time.time()

            except Exception as e:
                print(f"[LOOP ERROR] {e}")
                update_status("ONLINE")
                time.sleep(1)
    finally:
        _voice_engine_running = False


if __name__ == "__main__":
    listen_loop()

