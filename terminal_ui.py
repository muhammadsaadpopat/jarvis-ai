import os
import sys
import time
import json
import psutil
import threading
import ctypes

# Enable ANSI Escape Codes on Windows
try:
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

# Resize and position the terminal window
os.system("mode con: cols=65 lines=24")
time.sleep(0.2)
try:
    import win32gui
    import win32con
    hwnd = win32gui.GetForegroundWindow()
    # Set window position at (0,0) and size to 540x495 pixels to fit suggestions perfectly
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 540, 495, win32con.SWP_SHOWWINDOW)
except Exception as e:
    try:
        ps_cmd = '[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);' \
                 '[Win32.WinAPI]::SetWindowPos((Get-Process -Id ' + str(os.getpid()) + ').MainWindowHandle, 0, 0, 0, 540, 495, 0x0040)'
        os.system(f'powershell -Command "Add-Type -MemberDefinition \'{ps_cmd}\' -Name \'WinAPI\' -Namespace \'Win32\' -ErrorAction SilentlyContinue; [Win32.WinAPI]::SetWindowPos((Get-Process -Id {os.getpid()}).MainWindowHandle, 0, 0, 0, 540, 495, 0x0040)"')
    except Exception:
        pass

import voice_engine

# Start the voice engine in a background thread
def run_voice_loop():
    try:
        voice_engine.listen_loop()
    except Exception as e:
        print(f"Voice loop error: {e}")

voice_thread = threading.Thread(target=run_voice_loop, daemon=True)
voice_thread.start()

spinners = [
    ["  .---.  ", " /  |  \\ ", "| --o-- |", " \\  |  / ", "  '---'  "],
    ["  .---.  ", " /  /  / ", "|  /o/  |", " /  /  / ", "  '---'  "],
    ["  .---.  ", " /     \\ ", "|===o===|", " \\     / ", "  '---'  "],
    ["  .---.  ", " \\  \\  \\ ", "|  \\o\\  |", " \\  \\  \\ ", "  '---'  "]
]

frame_idx = 0

def make_bar(percent):
    filled = int(percent / 10)
    return "[" + "|" * filled + " " * (10 - filled) + "]"

def read_file_safe(path, default=""):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return default

# Clear screen once at boot
os.system("cls")
print("\033[?25l") # Hide text cursor to keep console extremely clean

try:
    while True:
        # Load telemetry logs and cognitive context
        status = read_file_safe("status.txt", "STANDBY")
        thoughts = read_file_safe("thoughts.txt", "")
        last_heard = read_file_safe("last_heard.txt", "Awaiting input...")
        last_response = read_file_safe("last_response.txt", "Awaiting query...")
        sentiment = read_file_safe("sentiment.txt", "NORMAL")
        suggestions_raw = read_file_safe("suggestions.txt", "All systems nominal. No optimizations currently required.")
        
        # Get System stats
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        if battery:
            bat_pct = battery.percent
            bat_charging = battery.power_plugged
        else:
            bat_pct = 100
            bat_charging = False
            
        # Read voice character gender
        try:
            with open("config.json", "r") as f:
                cfg = json.load(f)
            gender = cfg.get("voice_gender", "male")
        except Exception:
            gender = "male"
        char_name = "FRIDAY" if gender == "female" else "JARVIS"
        
        # Color definitions
        c_cyan = "\033[96m"
        c_green = "\033[92m"
        c_yellow = "\033[93m"
        c_magenta = "\033[95m"
        c_red = "\033[91m"
        c_gray = "\033[90m"
        c_white = "\033[97m\033[1m"
        c_reset = "\033[0m"
        
        # Build spinner frames
        spinner = spinners[frame_idx % len(spinners)]
        frame_idx += 1
        
        # Render screen
        out = []
        out.append(f"{c_cyan}================== {c_white}{char_name} CORE CONSOLE{c_cyan} =================={c_reset}")
        out.append("")
        
        # Left side spinner, right side stats
        out.append(f"  {c_magenta}{spinner[0]}{c_reset}      STATUS: {c_green}{status[:36]}{c_reset}")
        
        bat_status = f"{bat_pct}%" + (" +" if bat_charging else "")
        out.append(f"  {c_magenta}{spinner[1]}{c_reset}      CPU:    {cpu:4.1f}% {c_cyan}{make_bar(cpu)}{c_reset}")
        out.append(f"  {c_magenta}{spinner[2]}{c_reset}      RAM:    {ram:4.1f}% {c_cyan}{make_bar(ram)}{c_reset}")
        out.append(f"  {c_magenta}{spinner[3]}{c_reset}      POWER:  {bat_status:<5} {c_cyan}{make_bar(bat_pct)}{c_reset}")
        
        # Format Master's sentiment
        if sentiment == "STRESSED":
            sent_colored = f"{c_red}STRESSED{c_reset}"
        elif sentiment == "PRODUCTIVE_DROP":
            sent_colored = f"{c_yellow}PRODUCTIVE DROP{c_reset}"
        else:
            sent_colored = f"{c_green}NORMAL{c_reset}"
        out.append(f"  {c_magenta}{spinner[4]}{c_reset}      MOOD:   {sent_colored}")
        out.append("")
        
        # Thoughts / Deep Reasoning Board
        out.append(f"{c_cyan}🧠 COGNITION:{c_reset}")
        if thoughts:
            thought_line = thoughts.split("\n")[0][:60]
            out.append(f" {c_yellow}> {thought_line}{c_reset}")
        else:
            out.append(f" {c_gray}> Awaiting query...{c_reset}")
        out.append("")
        
        # Last Speech and Response
        out.append(f"{c_cyan}-------------------------------------------------------------{c_reset}")
        out.append(f"🎤 {c_white}HEARD:{c_reset} {last_heard[:50]}")
        out.append(f"🤖 {c_white}JARVIS:{c_reset} {last_response[:48]}")
        out.append(f"{c_cyan}-------------------------------------------------------------{c_reset}")
        
        # Predictive analytics & warning suggestions
        out.append(f"{c_cyan}🔔 PREDICTIVE SUGGESTIONS:{c_reset}")
        if "All systems nominal" not in suggestions_raw:
            warning_line = suggestions_raw.split("\n")[0][:60]
            out.append(f" {c_red}⚠️  {warning_line}{c_reset}")
        else:
            out.append(f" {c_gray}✓  {suggestions_raw[:60]}{c_reset}")
        
        # Print with ANSI Home escape code to prevent flickering
        sys.stdout.write("\033[H" + "\n".join(out))
        sys.stdout.flush()
        
        time.sleep(0.12)
        
except KeyboardInterrupt:
    print("\033[?25h") # Show text cursor again
