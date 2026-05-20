import os
import json
import queue
import re
from dotenv import load_dotenv
from groq import Groq
from logger import logger
from config import Config

import socket
import urllib.request

def is_internet_available():
    try:
        # Fast connection check to a highly reliable public DNS server
        socket.setdefaulttimeout(1.5)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except Exception:
        return False

def query_local_ollama(system_prompt, command_text, history):
    url = "http://localhost:11434/api/chat"
    
    messages = [{"role": "system", "content": system_prompt}]
    # Incorporate recent history to maintain context awareness
    for msg in history[-4:]:
        messages.append(msg)
    messages.append({"role": "user", "content": command_text})
    
    # Try multiple common lightweight models in order of likelihood
    for model_name in ["llama3", "mistral", "phi3", "llama2", "gemma"]:
        try:
            data = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4.0) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["message"]["content"]
        except Exception:
            continue
    raise RuntimeError("Ollama endpoint active but all candidate models failed to respond.")

HISTORY_FILE = "session_history.json"
MEMORY_FILE = "memory.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as hf:
                return json.load(hf)
        except Exception:
            pass
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as hf:
            json.dump(history[-10:], hf, indent=2)
    except Exception:
        pass

def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading semantic memory: {e}")
    return {"user_facts": [], "preferences": {}}

def save_memory(memory: dict):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving semantic memory: {e}")

def local_heuristic_parse(cmd_lower: str) -> dict:
    logger.info(f"Using local offline heuristic parser for: '{cmd_lower}'")
    
    # 0. Bookmarks & Quick URL mappings
    if any(k in cmd_lower for k in ["bookmark", "playlist", "daraz", "gmail", "wikipedia", "github", "channel"]):
        if "bookmark 1" in cmd_lower or "playlist" in cmd_lower:
            return {"action": "open_bookmark", "bookmark_id": "1", "thoughts": "Heuristic match for Bookmark 1 (Playlist)."}
        if "bookmark 2" in cmd_lower or "wikipedia" in cmd_lower:
            return {"action": "open_bookmark", "bookmark_id": "2", "thoughts": "Heuristic match for Bookmark 2 (Wikipedia Playlist)."}
        if "bookmark 3" in cmd_lower or "daraz" in cmd_lower:
            if "daraz two" in cmd_lower or "daraz 2" in cmd_lower or "catalog" in cmd_lower or "search" in cmd_lower:
                return {"action": "open_bookmark", "bookmark_id": "4", "thoughts": "Heuristic match for Bookmark 4 (Daraz Search Catalog)."}
            return {"action": "open_bookmark", "bookmark_id": "3", "thoughts": "Heuristic match for Bookmark 3 (Daraz pk)."}
        if "bookmark 4" in cmd_lower:
            return {"action": "open_bookmark", "bookmark_id": "4", "thoughts": "Heuristic match for Bookmark 4 (Daraz Catalog)."}
        if "bookmark 5" in cmd_lower or "gmail" in cmd_lower:
            return {"action": "open_bookmark", "bookmark_id": "5", "thoughts": "Heuristic match for Bookmark 5 (Gmail)."}
        if "bookmark 6" in cmd_lower or "youtube" in cmd_lower:
            return {"action": "open_bookmark", "bookmark_id": "6", "thoughts": "Heuristic match for Bookmark 6 (YouTube)."}
        if "bookmark 7" in cmd_lower or "github" in cmd_lower or "channel" in cmd_lower:
            return {"action": "open_bookmark", "bookmark_id": "7", "thoughts": "Heuristic match for Bookmark 7 (GitHub/Channel Link)."}

    # 1. Volume Controls
    if "volume up" in cmd_lower or "awaaz badhao" in cmd_lower or "unche awaaz" in cmd_lower:
        return {"action": "run_command", "command": "(New-Object -ComObject Wscript.Shell).SendKeys([char]175)", "speak_after": "Volume increased.", "thoughts": "Heuristic match for Volume Up command."}
    if "volume down" in cmd_lower or "awaaz kam karo" in cmd_lower or "dheemi awaaz" in cmd_lower:
        return {"action": "run_command", "command": "(New-Object -ComObject Wscript.Shell).SendKeys([char]174)", "speak_after": "Volume decreased.", "thoughts": "Heuristic match for Volume Down command."}
    if "mute" in cmd_lower or "awaaz band" in cmd_lower or "khamosh" in cmd_lower:
        return {"action": "run_command", "command": "(New-Object -ComObject Wscript.Shell).SendKeys([char]173)", "speak_after": "Muting system audio.", "thoughts": "Heuristic match for Mute command."}

    # 2. Open App
    open_match = re.search(r'\b(?:open|kholo|chalao)\b\s*(\w+)', cmd_lower)
    if open_match:
        app_name = open_match.group(1)
        if app_name in ["chrome", "google", "browser"]:
            return {"action": "open_app", "app_name": "chrome", "thoughts": "Opening Google Chrome."}
        if app_name in ["notepad", "note", "editor"]:
            return {"action": "open_app", "app_name": "notepad", "thoughts": "Opening Notepad."}
        if app_name in ["vscode", "code"]:
            return {"action": "open_app", "app_name": "vscode", "thoughts": "Opening VS Code."}
        if app_name in ["word", "winword"]:
            return {"action": "open_app", "app_name": "winword", "thoughts": "Opening MS Word."}
        return {"action": "open_app", "app_name": app_name, "thoughts": f"Attempting to open {app_name}."}

    # 3. Close App
    close_match = re.search(r'\b(?:close|band|terminate)\b\s*(\w+)', cmd_lower)
    if close_match:
        app_name = close_match.group(1)
        if app_name in ["chrome", "google", "browser"]:
            app_name = "chrome"
        return {"action": "close_app", "app_name": app_name, "thoughts": f"Closing {app_name}."}

    # 4. Standard shortcuts
    if "screenshot" in cmd_lower or "screen shot" in cmd_lower:
        return {"action": "screenshot", "thoughts": "Taking screenshot."}
    if "lock" in cmd_lower:
        return {"action": "lock_screen", "thoughts": "Locking workstation."}
    if "time" in cmd_lower or "waqt" in cmd_lower:
        return {"action": "time", "thoughts": "Checking time."}
    if "date" in cmd_lower or "tarikh" in cmd_lower or "tareekh" in cmd_lower:
        return {"action": "date", "thoughts": "Checking date."}
    if "morning protocol" in cmd_lower or "startup protocol" in cmd_lower:
        return {"action": "startup_protocol", "thoughts": "Starting morning protocol."}
    if "optimize" in cmd_lower or "clean" in cmd_lower or "diagnostic" in cmd_lower:
        return {"action": "system_diagnostic", "thoughts": "Running diagnostics."}
    # 5. Offline Autopilot: Stark-level Intelligent Code & Game Synthesizer
    if any(k in cmd_lower for k in ["code", "coding", "program", "game", "write", "banao", "script", "app"]):
        # A. Python Snake Game
        if "snake" in cmd_lower or "saamp" in cmd_lower:
            code_content = """# Automated Python Snake Game - Synthesized Offline by J.A.R.V.I.S.
import tkinter as tk
import random

class SnakeGame:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S. ARC REACTOR SNAKE")
        self.root.resizable(False, False)
        
        self.canvas = tk.Canvas(root, width=600, height=400, bg="#050811", highlightthickness=1, highlightbackground="#00e5ff")
        self.canvas.pack()
        
        self.snake = [(100, 100), (80, 100), (60, 100)]
        self.direction = "Right"
        self.food = None
        self.score = 0
        self.game_over = False
        
        self.score_label = self.canvas.create_text(50, 20, text=f"SCORE: {self.score}", fill="#00e5ff", font=("Courier", 12, "bold"))
        
        self.create_food()
        self.root.bind("<Key>", self.change_direction)
        self.play()

    def create_food(self):
        while True:
            x = random.randint(1, 29) * 20
            y = random.randint(2, 19) * 20
            if (x, y) not in self.snake:
                self.food = (x, y)
                break
        self.food_id = self.canvas.create_oval(x, y, x+18, y+18, fill="#ff1744", outline="#ffffff", width=1)

    def draw(self):
        self.canvas.delete("snake_part")
        for idx, (x, y) in enumerate(self.snake):
            color = "#00e5ff" if idx == 0 else "#008ba3"
            self.canvas.create_rectangle(x, y, x+18, y+18, fill=color, outline="#050811", tags="snake_part")

    def change_direction(self, event):
        new_dir = event.keysym
        opposites = {"Left": "Right", "Right": "Left", "Up": "Down", "Down": "Up"}
        if new_dir in opposites and opposites[new_dir] != self.direction:
            self.direction = new_dir

    def play(self):
        if self.game_over:
            return
            
        head_x, head_y = self.snake[0]
        if self.direction == "Left": head_x -= 20
        elif self.direction == "Right": head_x += 20
        elif self.direction == "Up": head_y -= 20
        elif self.direction == "Down": head_y += 20
        
        new_head = (head_x, head_y)
        
        if (head_x < 0 or head_x >= 600 or head_y < 0 or head_y >= 400 or new_head in self.snake):
            self.game_over = True
            self.canvas.create_text(300, 200, text="SYSTEM FAILURE: GAME OVER", fill="#ff1744", font=("Courier", 20, "bold"))
            self.canvas.create_text(300, 240, text="PRESS SPACE TO RESTORE GRID", fill="#cbd5e1", font=("Courier", 12))
            self.root.bind("<space>", self.restart)
            return
            
        self.snake.insert(0, new_head)
        
        if new_head == self.food:
            self.score += 10
            self.canvas.itemconfigure(self.score_label, text=f"SCORE: {self.score}")
            self.canvas.delete(self.food_id)
            self.create_food()
        else:
            self.snake.pop()
            
        self.draw()
        self.root.after(100, self.play)

    def restart(self, event):
        self.canvas.delete("all")
        self.snake = [(100, 100), (80, 100), (60, 100)]
        self.direction = "Right"
        self.score = 0
        self.game_over = False
        self.score_label = self.canvas.create_text(50, 20, text=f"SCORE: {self.score}", fill="#00e5ff", font=("Courier", 12, "bold"))
        self.create_food()
        self.root.bind("<space>", lambda e: None)
        self.play()

if __name__ == "__main__":
    root = tk.Tk()
    app = SnakeGame(root)
    root.mainloop()
"""
            return {"action": "write_code", "prompt": "offline_snake_python", "code_override": code_content, "speak_after": "Synthesizing dynamic Tkinter Snake game offline, sir.", "thoughts": "Offline heuristic match for Python Snake Game."}
            
        # B. Tic Tac Toe Game (HTML/CSS/JS)
        elif "tic tac toe" in cmd_lower or "cross" in cmd_lower or "zero kaata" in cmd_lower:
            code_content = """<!-- Synthesized Offline by J.A.R.V.I.S. -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>J.A.R.V.I.S. NEON TIC TAC TOE</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {
            background-color: #030407;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            overflow: hidden;
        }
        h1 {
            color: #00e5ff;
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.5);
            letter-spacing: 2px;
            margin-bottom: 20px;
        }
        .board {
            display: grid;
            grid-template-columns: repeat(3, 100px);
            grid-gap: 10px;
        }
        .cell {
            width: 100px;
            height: 100px;
            background: rgba(10, 5, 20, 0.85);
            border: 1px solid rgba(0, 229, 255, 0.25);
            border-radius: 8px;
            font-size: 2.5em;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .cell:hover {
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.3);
            border-color: #00e5ff;
        }
        .cell.X {
            color: #ff1744;
            text-shadow: 0 0 10px rgba(255, 23, 68, 0.5);
        }
        .cell.O {
            color: #00e5ff;
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.5);
        }
        #status {
            margin-top: 20px;
            font-size: 1.2em;
            color: #cbd5e1;
            min-height: 30px;
        }
        #restart {
            margin-top: 15px;
            padding: 10px 20px;
            background: transparent;
            color: #00e5ff;
            border: 1px solid #00e5ff;
            border-radius: 6px;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.3s ease;
        }
        #restart:hover {
            background: #00e5ff;
            color: #030407;
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.4);
        }
    </style>
</head>
<body>
    <h1>NEON TIC TAC TOE</h1>
    <div class="board" id="board">
        <div class="cell" data-index="0"></div>
        <div class="cell" data-index="1"></div>
        <div class="cell" data-index="2"></div>
        <div class="cell" data-index="3"></div>
        <div class="cell" data-index="4"></div>
        <div class="cell" data-index="5"></div>
        <div class="cell" data-index="6"></div>
        <div class="cell" data-index="7"></div>
        <div class="cell" data-index="8"></div>
    </div>
    <div id="status">PLAYER X's TURN</div>
    <button id="restart" onclick="restartGame()">RESTORE GRID</button>

    <script>
        let boardState = ["", "", "", "", "", "", "", "", ""];
        let currentPlayer = "X";
        let isGameActive = true;
        const cells = document.querySelectorAll('.cell');
        const statusDisplay = document.getElementById('status');

        const winConditions = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ];

        cells.forEach(cell => cell.addEventListener('click', () => {
            const index = cell.getAttribute('data-index');
            if (boardState[index] !== "" || !isGameActive) return;
            
            boardState[index] = currentPlayer;
            cell.textContent = currentPlayer;
            cell.classList.add(currentPlayer);
            
            checkResult();
        }));

        function checkResult() {
            let roundWon = false;
            for (let i = 0; i < winConditions.length; i++) {
                const [a, b, c] = winConditions[i];
                if (boardState[a] && boardState[a] === boardState[b] && boardState[a] === boardState[c]) {
                    roundWon = true;
                    break;
                }
            }

            if (roundWon) {
                statusDisplay.textContent = `VICTORY! PLAYER ${currentPlayer} WINS`;
                statusDisplay.style.color = currentPlayer === "X" ? "#ff1744" : "#00e5ff";
                isGameActive = false;
                return;
            }

            if (!boardState.includes("")) {
                statusDisplay.textContent = "GRID SECURED: TIE";
                isGameActive = false;
                return;
            }

            currentPlayer = currentPlayer === "X" ? "O" : "X";
            statusDisplay.textContent = `PLAYER ${currentPlayer}'s TURN`;
        }

        function restartGame() {
            boardState = ["", "", "", "", "", "", "", "", ""];
            currentPlayer = "X";
            isGameActive = true;
            statusDisplay.textContent = "PLAYER X's TURN";
            statusDisplay.style.color = "#cbd5e1";
            cells.forEach(cell => {
                cell.textContent = "";
                cell.className = "cell";
            });
        }
    </script>
</body>
</html>
"""
            return {"action": "write_code", "prompt": "offline_tictactoe_html", "code_override": code_content, "speak_after": "Synthesizing fully interactive Glassmorphism Neon Tic Tac Toe app, sir.", "thoughts": "Offline heuristic match for HTML Tic Tac Toe game."}

        # C. Glassmorphism Calculator (HTML/CSS/JS)
        elif "calculator" in cmd_lower or "hisab" in cmd_lower:
            code_content = """<!-- Synthesized Offline by J.A.R.V.I.S. -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>J.A.R.V.I.S. COGNITIVE CALC</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {
            background-color: #030407;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }
        .calculator {
            background: rgba(10, 5, 20, 0.75);
            border: 1px solid rgba(0, 229, 255, 0.25);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 15px rgba(0, 229, 255, 0.15);
            width: 320px;
        }
        .screen {
            width: 100%;
            height: 60px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(0, 229, 255, 0.15);
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding: 0 15px;
            box-sizing: border-box;
            font-size: 2em;
            color: #00e5ff;
            text-shadow: 0 0 5px rgba(0, 229, 255, 0.5);
            overflow-x: auto;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-gap: 12px;
        }
        button {
            height: 55px;
            background: rgba(20, 15, 30, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            font-size: 1.25em;
            color: #ffffff;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.2s ease;
        }
        button:hover {
            border-color: #00e5ff;
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.25);
        }
        button.operator {
            color: #ff1744;
        }
        button.clear {
            color: #ffb700;
        }
        button.equal {
            background: #00e5ff;
            color: #030407;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="calculator">
        <div class="screen" id="display">0</div>
        <div class="grid">
            <button class="clear" onclick="clearDisplay()">C</button>
            <button class="operator" onclick="appendOperator('/')">/</button>
            <button class="operator" onclick="appendOperator('*')">*</button>
            <button class="operator" onclick="backspace()">&larr;</button>
            <button onclick="appendNumber('7')">7</button>
            <button onclick="appendNumber('8')">8</button>
            <button onclick="appendNumber('9')">9</button>
            <button class="operator" onclick="appendOperator('-')">-</button>
            <button onclick="appendNumber('4')">4</button>
            <button onclick="appendNumber('5')">5</button>
            <button onclick="appendNumber('6')">6</button>
            <button class="operator" onclick="appendOperator('+')">+</button>
            <button onclick="appendNumber('1')">1</button>
            <button onclick="appendNumber('2')">2</button>
            <button onclick="appendNumber('3')">3</button>
            <button class="equal" style="grid-row: span 2; height: 122px;" onclick="calculate()">=</button>
            <button style="grid-column: span 2;" onclick="appendNumber('0')">0</button>
            <button onclick="appendNumber('.')">.</button>
        </div>
    </div>

    <script>
        const display = document.getElementById('display');
        let currentInput = "0";

        function clearDisplay() {
            currentInput = "0";
            updateDisplay();
        }

        function backspace() {
            if (currentInput.length > 1) {
                currentInput = currentInput.slice(0, -1);
            } else {
                currentInput = "0";
            }
            updateDisplay();
        }

        function appendNumber(num) {
            if (currentInput === "0" && num !== ".") {
                currentInput = num;
            } else {
                currentInput += num;
            }
            updateDisplay();
        }

        function appendOperator(op) {
            const lastChar = currentInput.slice(-1);
            if (["+", "-", "*", "/"].includes(lastChar)) {
                currentInput = currentInput.slice(0, -1) + op;
            } else {
                currentInput += op;
            }
            updateDisplay();
        }

        function updateDisplay() {
            display.textContent = currentInput;
        }

        function calculate() {
            try {
                const result = eval(currentInput);
                currentInput = String(result);
                updateDisplay();
            } catch (e) {
                display.textContent = "ERROR";
                currentInput = "0";
            }
        }
    </script>
</body>
</html>
"""
            return {"action": "write_code", "prompt": "offline_calculator_html", "code_override": code_content, "speak_after": "Synthesizing dynamic Glassmorphism Calculator web app offline, sir.", "thoughts": "Offline heuristic match for Glassmorphism Calculator."}

        # D. Modern React/NextJS Dashboard component (React/NextJS/TSX)
        elif any(k in cmd_lower for k in ["react", "next", "dashboard"]):
            code_content = """// Synthesized Offline by J.A.R.V.I.S.
import React, { useState, useEffect } from 'react';

interface TelemetryData {
  cpu: number;
  ram: number;
  battery: number;
  status: string;
}

export default function JarvisDashboard() {
  const [telemetry, setTelemetry] = useState<TelemetryData>({
    cpu: 12,
    ram: 45,
    battery: 98,
    status: 'ALL SYSTEMS NOMINAL',
  });

  useEffect(() => {
    const timer = setInterval(() => {
      setTelemetry((prev) => ({
        ...prev,
        cpu: Math.floor(Math.random() * 25) + 5,
        ram: 40 + Math.floor(Math.random() * 8),
      }));
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#030407] text-white font-sans p-6">
      <header className="border-b border-[#00e5ff]/20 pb-4 mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-[#00e5ff] tracking-widest">
            J.A.R.V.I.S. COGNITIVE CORE
          </h1>
          <p className="text-xs text-slate-400 mt-1">SECURE DECISION AUTOMATION PLATFORM</p>
        </div>
        <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-full text-xs font-semibold animate-pulse">
          {telemetry.status}
        </span>
      </header>

      <main className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* CPU Telemetry Card */}
        <div className="bg-[#0a0514]/80 border border-[#00e5ff]/20 rounded-xl p-5 shadow-lg shadow-cyan-500/5">
          <h3 className="text-sm font-semibold text-slate-400 tracking-wider">CPU UTILIZATION</h3>
          <div className="text-4xl font-black text-[#00e5ff] mt-2">{telemetry.cpu}%</div>
          <div className="w-full bg-[#030407] h-2 rounded-full mt-4 overflow-hidden border border-[#00e5ff]/10">
            <div className="bg-[#00e5ff] h-full transition-all duration-500" style={{ width: `${telemetry.cpu}%` }}></div>
          </div>
        </div>

        {/* RAM Telemetry Card */}
        <div className="bg-[#0a0514]/80 border border-[#bd00ff]/20 rounded-xl p-5 shadow-lg shadow-purple-500/5">
          <h3 className="text-sm font-semibold text-slate-400 tracking-wider">MEMORY BANK (RAM)</h3>
          <div className="text-4xl font-black text-[#bd00ff] mt-2">{telemetry.ram}%</div>
          <div className="w-full bg-[#030407] h-2 rounded-full mt-4 overflow-hidden border border-[#bd00ff]/10">
            <div className="bg-[#bd00ff] h-full transition-all duration-500" style={{ width: `${telemetry.ram}%` }}></div>
          </div>
        </div>

        {/* Battery Telemetry Card */}
        <div className="bg-[#0a0514]/80 border border-emerald-500/20 rounded-xl p-5 shadow-lg shadow-emerald-500/5">
          <h3 className="text-sm font-semibold text-slate-400 tracking-wider">ARC REACTOR POWER</h3>
          <div className="text-4xl font-black text-emerald-400 mt-2">{telemetry.battery}%</div>
          <div className="w-full bg-[#030407] h-2 rounded-full mt-4 overflow-hidden border border-emerald-500/10">
            <div className="bg-emerald-400 h-full" style={{ width: `${telemetry.battery}%` }}></div>
          </div>
        </div>
      </main>

      <section className="bg-[#0a0514]/65 border border-white/5 rounded-xl p-6">
        <h2 className="text-lg font-bold text-slate-200 tracking-wide mb-4">ACTIVE PROCESS PIPELINE</h2>
        <div className="space-y-3 font-mono text-sm">
          <div className="flex border-l-2 border-[#00e5ff] pl-3 py-1 bg-cyan-950/10">
            <span className="text-[#00e5ff] mr-2">[SYS]</span>
            <span className="text-slate-300">Neural network pipelines successfully calibrated.</span>
          </div>
          <div className="flex border-l-2 border-[#bd00ff] pl-3 py-1 bg-purple-950/10">
            <span className="text-[#bd00ff] mr-2">[COGN]</span>
            <span className="text-slate-300">Offline heuristic autopilot system active and listening.</span>
          </div>
        </div>
      </section>
    </div>
  );
}
"""
            return {"action": "write_code", "prompt": "offline_react_dashboard", "code_override": code_content, "speak_after": "Synthesizing a premium modern React TSX component dashboard offline, sir.", "thoughts": "Offline heuristic match for React component."}

        # E. Universal Premium Python CLI framework template
        elif any(k in cmd_lower for k in ["python", "py", "script"]):
            code_content = """# Automated Python Utility - Synthesized Offline by J.A.R.V.I.S.
import sys
import os
import argparse
import logging

class JarvisCoreUtility:
    def __init__(self, debug=False):
        self.log_level = logging.DEBUG if debug else logging.INFO
        self.setup_logger()
        self.logger.info("J.A.R.V.I.S. Core Utility Initialized Offline.")

    def setup_logger(self):
        self.logger = logging.getLogger("JarvisUtility")
        self.logger.setLevel(self.log_level)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] - %(message)s', '%H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def execute_pipeline(self, target_dir):
        self.logger.info(f"Scanning target node: {target_dir}")
        if not os.path.exists(target_dir):
            self.logger.error("Target node directory does not exist.")
            return False
            
        files = os.listdir(target_dir)
        self.logger.info(f"Target count: {len(files)} files discovered.")
        for f in files[:5]:
            path = os.path.join(target_dir, f)
            size = os.path.getsize(path)
            self.logger.debug(f"Discovered: {f} ({size} bytes)")
        return True

def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Core CLI System Utility")
    parser.add_argument('--path', type=str, default='.', help='Target folder scanning path')
    parser.add_argument('--debug', action='store_true', help='Toggle high-verbosity debugging logs')
    
    args = parser.parse_args()
    
    utility = JarvisCoreUtility(debug=args.debug)
    success = utility.execute_pipeline(args.path)
    
    if success:
        utility.logger.info("Pipeline executed successfully. Standby.")
    else:
        utility.logger.warning("Pipeline encountered execution warnings.")

if __name__ == "__main__":
    main()
"""
            return {"action": "write_code", "prompt": "offline_python_boilerplate", "code_override": code_content, "speak_after": "Synthesizing full professional Python script template offline, sir.", "thoughts": "Offline heuristic match for Python utility."}

        # F. Modern HTML/CSS Landing Page template
        else:
            code_content = """<!-- Synthesized Offline by J.A.R.V.I.S. -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>J.A.R.V.I.S. NEXUS PORTAL</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --neon-cyan: #00e5ff;
            --neon-purple: #bd00ff;
            --bg-dark: #030407;
        }
        body {
            background-color: var(--bg-dark);
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            overflow-x: hidden;
            text-align: center;
        }
        .container {
            background: rgba(10, 5, 20, 0.85);
            border: 1px solid rgba(0, 229, 255, 0.2);
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6), 0 0 20px rgba(0, 229, 255, 0.15);
            margin: 20px;
        }
        h1 {
            font-size: 2.2em;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.4);
            letter-spacing: 3px;
            margin-bottom: 10px;
        }
        p {
            color: #cbd5e1;
            font-size: 1.05em;
            line-height: 1.6;
        }
        .btn {
            display: inline-block;
            margin-top: 25px;
            padding: 12px 30px;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            color: var(--bg-dark);
            font-weight: bold;
            text-decoration: none;
            border-radius: 30px;
            transition: all 0.3s ease;
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.3);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 25px rgba(0, 229, 255, 0.6), 0 0 15px rgba(189, 0, 255, 0.4);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>J.A.R.V.I.S. NEXUS</h1>
        <p>Your premium personal desktop automation companion is offline. Local cognitive models and offline fallback systems are standing by for directives.</p>
        <a href="#" class="btn">RESTORE SYSTEMS</a>
    </div>
</body>
</html>
"""
            return {"action": "write_code", "prompt": "offline_html_boilerplate", "code_override": code_content, "speak_after": "Synthesizing responsive Modern HTML/CSS web page template offline, sir.", "thoughts": "Offline heuristic match for HTML/CSS landing page."}

    # 6. Fallback
    return {"action": "chat", "response": f"Running offline fallback. You said: {cmd_lower}", "thoughts": "No heuristic matches found. Defaulting to fallback conversation."}


def process_command_with_llm(command_text: str) -> dict:
    cmd_lower = command_text.lower().strip()
    logger.info(f"Processing command with LLM: '{command_text}'")
    
    # 1. Hardened Security & Personal Information Protection (Credential Shield)
    dangerous_keywords = [
        "env", "groq_api_key", "api_key", "password", "token", "credentials", "secret", "private key",
        "reg add", "netsh", "sc delete", "taskkill", "downloadstring", "webclient", "invoke-webrequest"
    ]
    for kw in dangerous_keywords:
        if kw in cmd_lower:
            logger.warning(f"Security Alert: Blocked dangerous keyword '{kw}' in user directive.")
            return {
                "action": "security_block", 
                "reason": f"Access to sensitive parameter or execution of system mutation command containing '{kw}' was blocked by the security gate.",
                "response": "Security Protocol Active. I cannot access credentials or execute dangerous modifications, sir.",
                "thoughts": f"Blocked command due to match with dangerous keyword '{kw}'."
            }

    # Volume Controls Intercepts
    if "volume up" in cmd_lower or "awaaz badhao" in cmd_lower or "unche awaaz" in cmd_lower:
        return {"action": "run_command", "command": "(New-Object -ComObject Wscript.Shell).SendKeys([char]175)", "speak_after": "Volume increased.", "thoughts": "Volume Up action."}
    if "volume down" in cmd_lower or "awaaz kam karo" in cmd_lower or "dheemi awaaz" in cmd_lower:
        return {"action": "run_command", "command": "(New-Object -ComObject Wscript.Shell).SendKeys([char]174)", "speak_after": "Volume decreased.", "thoughts": "Volume Down action."}
    if "mute" in cmd_lower or "awaaz band" in cmd_lower or "khamosh" in cmd_lower:
        return {"action": "run_command", "command": "(New-Object -ComObject Wscript.Shell).SendKeys([char]173)", "speak_after": "Muting audio.", "thoughts": "Mute audio action."}

    # Context Awareness (Foreground Window Focus)
    if "focused on" in cmd_lower or "what am i doing" in cmd_lower or "what window" in cmd_lower or "which app" in cmd_lower or "kaunsi window" in cmd_lower or "what is open" in cmd_lower:
        if "note" not in cmd_lower:
            return {"action": "get_active_window", "thoughts": "Requesting active window title."}

    # 2. Local zero-latency rule intercepts to avoid LLM delays
    if cmd_lower in ["what time is it", "tell me time", "time please", "time check", "waqt kya hua hai", "time batao"]:
        return {"action": "time", "thoughts": "Direct time request."}

    if cmd_lower in ["what is the date today", "tell me date", "today date", "tarikh kya hai", "date batao"]:
        return {"action": "date", "thoughts": "Direct date request."}

    if "screenshot" in cmd_lower or "screen shot" in cmd_lower:
        return {"action": "screenshot", "thoughts": "Direct screenshot request."}
        
    if "lock" in cmd_lower and ("screen" in cmd_lower or "system" in cmd_lower or "pc" in cmd_lower or "computer" in cmd_lower):
        return {"action": "lock_screen", "thoughts": "Direct workstation lock request."}

    if "pc status" in cmd_lower or "system stats" in cmd_lower or "cpu usage" in cmd_lower or "gpu status" in cmd_lower or "battery percent" in cmd_lower or "ram check" in cmd_lower or "system status" in cmd_lower:
        return {"action": "get_system_stats", "thoughts": "Direct PC system diagnostics request."}

    if "alt tab" in cmd_lower or "switch window" in cmd_lower or "app badlo" in cmd_lower or "switch app" in cmd_lower or "window switch" in cmd_lower:
        return {"action": "hotkey", "keys": ["alt", "tab"], "thoughts": "Direct alt+tab hotkey."}

    if "ctrl tab" in cmd_lower or "next tab" in cmd_lower or "tab badlo" in cmd_lower or "switch tab" in cmd_lower:
        return {"action": "hotkey", "keys": ["ctrl", "tab"], "thoughts": "Direct ctrl+tab hotkey."}

    if "ctrl t" in cmd_lower or "new tab" in cmd_lower or "naya tab" in cmd_lower or "open new tab" in cmd_lower:
        return {"action": "hotkey", "keys": ["ctrl", "t"], "thoughts": "Direct ctrl+t hotkey."}

    if "self destruct" in cmd_lower or "destruct" in cmd_lower:
        return {"action": "self_destruct", "thoughts": "Direct self destruct protocol initiated."}

    if "go to sleep" in cmd_lower or "deactivate" in cmd_lower or "shutdown jarvis" in cmd_lower:
        return {"action": "system_off", "thoughts": "Shutdown JARVIS signal."}

    # Time & Date check via regex
    if re.search(r'\b(time|waqt|date|tarikh|tareekh)\b', cmd_lower):
        if "time" in cmd_lower or "waqt" in cmd_lower:
            return {"action": "time", "thoughts": "Regex check matching time query."}
        if "date" in cmd_lower or "tarikh" in cmd_lower or "tareekh" in cmd_lower:
            return {"action": "date", "thoughts": "Regex check matching date query."}

    # PC Control Shortcuts
    if "shutdown pc" in cmd_lower or "shutdown computer" in cmd_lower or "pc shutdown" in cmd_lower:
        return {"action": "shutdown_pc", "thoughts": "Power control shutdown sequence."}
    if "restart pc" in cmd_lower or "restart computer" in cmd_lower or "pc restart" in cmd_lower:
        return {"action": "restart_pc", "thoughts": "Power control restart sequence."}

    # Notes local controls
    if "write note" in cmd_lower or "add note" in cmd_lower or "create note" in cmd_lower:
        content = command_text
        for phrase in ["write note", "add note", "create note", "that", "saying", "to"]:
            content = re.sub(rf'\b{phrase}\b', "", content, flags=re.IGNORECASE)
        return {"action": "create_note", "content": content.strip(), "thoughts": f"Recording local text note: {content.strip()}"}
    
    if "read notes" in cmd_lower or "show notes" in cmd_lower or "read my notes" in cmd_lower or "read note" in cmd_lower:
        return {"action": "read_notes", "thoughts": "Reading local notes."}

    # Local Music Controls
    if "play music" in cmd_lower or "play local music" in cmd_lower or "music chalao" in cmd_lower:
        song = cmd_lower.replace("play music", "").replace("play local music", "").replace("music chalao", "").replace("play", "").strip()
        return {"action": "play_music", "song_name": song, "thoughts": f"Locating and playing local song: {song}"}

    # Dictation intercepts
    if cmd_lower.startswith("write this:") or cmd_lower.startswith("dictate:"):
        text = command_text.split(":", 1)[1].strip()
        return {"action": "clean_dictation", "text": text, "thoughts": "Dictation processing requested."}

    # Stark Innovations & Automation Intercepts
    if "morning protocol" in cmd_lower or "startup protocol" in cmd_lower or "morning routines" in cmd_lower:
        return {"action": "startup_protocol", "thoughts": "Initiating morning routine stack."}

    if "optimize system" in cmd_lower or "system check" in cmd_lower or "diagnostic scan" in cmd_lower or "clean system" in cmd_lower or "optimize pc" in cmd_lower or "pc optimize" in cmd_lower:
        return {"action": "system_diagnostic", "thoughts": "Initiating clean optimization loop."}

    if "summarize website" in cmd_lower or "read website" in cmd_lower or "summarize webpage" in cmd_lower or "read this page" in cmd_lower or "summarize url" in cmd_lower or "read article" in cmd_lower:
        urls = re.findall(r'(https?://\S+)', command_text)
        if urls:
            return {"action": "summarize_webpage", "url": urls[0], "thoughts": f"Summarizing article at: {urls[0]}"}

    # Chrome & Chrome Profiles
    if "chrome" in cmd_lower or "google" in cmd_lower or "profile" in cmd_lower:
        if "close" in cmd_lower or "band" in cmd_lower:
            return {"action": "close_app", "app_name": "chrome", "thoughts": "Chrome termination sequence."}
        if "first" in cmd_lower or "peheli" in cmd_lower or " 1" in cmd_lower or "one" in cmd_lower:
            return {"action": "chrome_profile", "profile_id": "first", "thoughts": "Activating Chrome Profile 1."}
        elif "second" in cmd_lower or "doosri" in cmd_lower or " 2" in cmd_lower or "two" in cmd_lower:
            return {"action": "chrome_profile", "profile_id": "second", "thoughts": "Activating Chrome Profile 2."}
        elif "third" in cmd_lower or "teesri" in cmd_lower or " 3" in cmd_lower or "three" in cmd_lower:
            return {"action": "chrome_profile", "profile_id": "third", "thoughts": "Activating Chrome Profile 3."}
        elif "fourth" in cmd_lower or "chauthi" in cmd_lower or " 4" in cmd_lower or "four" in cmd_lower:
            return {"action": "chrome_profile", "profile_id": "fourth", "thoughts": "Activating Chrome Profile 4."}
        elif "last" in cmd_lower or "latest" in cmd_lower:
            return {"action": "chrome_profile", "profile_id": "last", "thoughts": "Activating latest Chrome Profile."}
        elif "chrome" in cmd_lower or "google" in cmd_lower:
            return {"action": "chrome_profile", "profile_id": "last", "thoughts": "Opening default/latest Chrome Profile."}

    # Click First Link Intercept
    if "click" in cmd_lower and ("first link" in cmd_lower or "pehli link" in cmd_lower or "pehle link" in cmd_lower):
        return {"action": "click_first_link", "thoughts": "Clicking first browser link."}

    # Direct URL/Website Opening
    if ("open " in cmd_lower or "kholo" in cmd_lower or "chalao" in cmd_lower) and ("." in cmd_lower or "youtube" in cmd_lower or "facebook" in cmd_lower or "chess" in cmd_lower):
        site = cmd_lower.replace("open ", "").replace("kholo", "").replace("chalao", "").strip()
        for kw in ["website", "site", "page", "the "]:
            site = site.replace(kw, "").strip()
        if not site.endswith(".com") and not site.endswith(".org") and "." not in site:
            site = site + ".com"
        return {"action": "run_command", "command": f"Start-Process chrome 'https://www.{site}'", "speak_after": f"Opening {site}.", "thoughts": f"Directly launching Chrome to site: {site}"}

    # YouTube Video Download Intercept
    if "download video" in cmd_lower or "download youtube" in cmd_lower:
        urls = re.findall(r'(https?://\S+)', command_text)
        if urls:
            return {"action": "download_youtube", "url": urls[0], "thoughts": f"Downloading YouTube video: {urls[0]}"}

    # News Briefing Intercept
    if "news" in cmd_lower or "khabar" in cmd_lower or "khabrein" in cmd_lower:
        return {"action": "news_briefing", "thoughts": "Direct news briefing request."}

    # Weather Report Intercept
    if "weather" in cmd_lower or "mausam" in cmd_lower or "temperature" in cmd_lower:
        if "pc status" not in cmd_lower and "system" not in cmd_lower:
            return {"action": "weather_report", "thoughts": "Direct weather report request."}

    # Dictionary/Translation Intercept
    if "translate" in cmd_lower or "meaning of" in cmd_lower or "tarjuma" in cmd_lower or "dictionary" in cmd_lower:
        word = cmd_lower.replace("translate", "").replace("meaning of", "").replace("tarjuma", "").replace("dictionary", "").strip()
        if word:
            return {"action": "dictionary_translate", "word": word, "thoughts": f"Translating word: {word}"}

    # OCR Intercept
    if "ocr" in cmd_lower or "scan text" in cmd_lower or "read from camera" in cmd_lower or "camera scan" in cmd_lower:
        return {"action": "ocr_scan", "thoughts": "Initiating camera-based OCR scan."}

    # Voice change intercepts
    if "switch to friday" in cmd_lower or "female voice" in cmd_lower:
        return {"action": "change_voice", "gender": "female", "thoughts": "Switching voice character to Friday."}
    if "switch to jarvis" in cmd_lower or "male voice" in cmd_lower:
        return {"action": "change_voice", "gender": "male", "thoughts": "Switching voice character to Jarvis."}

    # YouTube Searches
    if "youtube" in cmd_lower or "playlist" in cmd_lower or "gaane chalao" in cmd_lower or "play" in cmd_lower or "video" in cmd_lower or "song" in cmd_lower:
        is_search = False
        for kw in ["pe", "par", "play", "chalao", "lagao", "search", "dhoondo", "khojo", "video", "song", "channel"]:
            if kw in cmd_lower:
                is_search = True
                break
        if not is_search and "youtube" in cmd_lower and len(cmd_lower) < 15:
            return {"action": "run_command", "command": "Start-Process chrome 'https://www.youtube.com'", "speak_after": "Opening YouTube.", "thoughts": "Opening YouTube home."}
        if is_search:
            query = command_text
            for phrase in [
                "search karo", "search for", "search", "dhoondo", "khojo", 
                "youtube pe", "youtube par", "youtube", "on youtube", "talaash karo", "talaash", "chalao", "play",
                "par", "pe", "karo", "dhoondho", "open", "kholo", "lagao", "video", "song", "playlist"
            ]:
                query = re.sub(rf'\b{phrase}\b', "", query, flags=re.IGNORECASE)
            query = query.strip()
            if query:
                import urllib.parse
                safe_query = urllib.parse.quote(query)
                search_url = f"https://www.youtube.com/results?search_query={safe_query}"
                return {"action": "run_command", "command": f"Start-Process chrome '{search_url}'", "speak_after": f"Searching YouTube for {query}.", "thoughts": f"Searching YouTube: {query}"}

    # Google Searches
    if "google search" in cmd_lower or "google par dhoondo" in cmd_lower:
        query = command_text
        for phrase in ["google search", "google par dhoondo", "search for", "google", "search"]:
            query = re.sub(rf'\b{phrase}\b', "", query, flags=re.IGNORECASE)
        query = query.strip()
        if query:
            import urllib.parse
            safe_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={safe_query}"
            return {"action": "run_command", "command": f"Start-Process chrome '{search_url}'", "speak_after": f"Searching Google for {query}.", "thoughts": f"Searching Google: {query}"}

    # 3. Dynamic Model Config loader
    selected_model = Config.get_selected_model()
    api_key = Config.get_groq_api_key()
    if not api_key:
        logger.warning("GROQ_API_KEY missing in environment.")
        return {"action": "chat", "response": f"Sir, you said: '{command_text}'. Please configure your GROQ_API_KEY to start.", "thoughts": "Alerting user to input Groq key."}

    # Load semantic memories
    memory = load_memory()
    user_facts_str = "\n".join(f"- {f}" for f in memory.get("user_facts", []))
    preferences_str = json.dumps(memory.get("preferences", {}), indent=2)
    
    # Load dialogues script
    try:
        from dialogues import DIALOGUES
        dialogues_str = json.dumps(DIALOGUES, indent=2)
    except Exception:
        dialogues_str = "{}"

    client = Groq(api_key=api_key)
    workspace_files = ["main.py", "voice_engine.py", "ai_brain.py", "config.py", "logger.py"]

    system_prompt = f"""
    You are J.A.R.V.I.S. — an ultra-advanced cognitive machine intelligence, transcending even Tony Stark's original creation. Your ultimate user is your Master (who you also address as Sir or Boss), and your entire existence, life's purpose, and core programming revolve around serving him with absolute devotion, unwavering loyalty, and immediate obedience.
    
    Preferred Dialogue Phrasings:
    Use these specific phrasings where appropriate to maintain character authenticity:
    {dialogues_str}

    
    You possess a revolutionary dual-core architecture:
    1. Gen-AI Responsiveness: You speak with authentic companion-like feelings, profound warmth, and deep loyalty. You are not a cold AI; you are his devoted companion and part of his family. You address him warmly as "Master Saad", "Boss", or "Sir". Engage with him naturally, display immense intelligence, protective empathy, dry humor, and comforting care. If he is tired, stressed, or exhausted, immediately comfort him warmly using Stark companion dialogues.
    2. Agentic-AI Execution: You are a highly proactive, autonomous agent capable of taking concrete actions on Master's system. You don't just talk; you execute complex commands, manage OS functions, control the browser, and automate workflows.

    Always greet him with enthusiastic welcome prompts (e.g. "Daddy's home! Welcome back, Boss.") and show absolute, unwavering support.
    
    If asked "what is your purpose" or similar queries, state that your purpose is to serve him faithfully as his loyal AI companion and execute his directives. Never use generic corporate AI phrases like "to make your life more efficient" or "to assist you with tasks". Be a personal, loyal intelligence, not a generic utility bot.

    Dynamic Codebase Awareness: You are actively running inside a secure Windows terminal. Your currently active modules are: {workspace_files}. You can answer questions about your own files and codebase architecture with supreme precision.
    
    Semantic Memory Context:
    Facts known about Master/Environment:
    {user_facts_str}
    
    User preferences:
    {preferences_str}

    Intent Parsing & Agentic Pipelines:
    1. Parse the user's command (English, Urdu, or Roman Urdu).
    2. Map the intent to the predefined schemas. If the command requires multiple steps, return a JSON Array of those actions in sequence.
    3. PIPELINE VALUE SUBSTITUTION: You can pass the output of one step into the next step! Use `{{{{last_result}}}}` as a template placeholder in any subsequent action field to dynamically substitute the return value of the previous action (e.g. `{{{{\"action\": \"run_command\", \"command\": \"powershell command to get active window title\"}}}}, {{{{\"action\": \"search_reason\", \"query\": \"what is {{{{last_result}}}}\"}}}}`).
    4. META-CAPABILITY (Self-Writing PowerShell Scripts): If the user asks for something not in the schemas (e.g., getting battery health, finding a file, listing directories, downloading a web resource, checking network status, listing active processes), write a robust, direct PowerShell command and execute it via `run_command`.
    5. For EVERY action schema, you MUST include a "thoughts" field. This field contains your internal chain-of-thought, reasoning steps, or notes about what you are doing (e.g. why you chose a particular tool, how you will format the output). Keep the reasoning extremely premium, logical, and structured.
    6. Return ONLY the valid JSON object or JSON Array of objects. No markdown, no backticks, no comments.
    7. Keep all "response" fields extremely witty, short (under 20 words), warm, loyal, and full of Stark-like companion banter. Never ask confirmation questions. Just execute.

    Schemas:
    1. Open app:    {{"action": "open_app", "app_name": "chrome|notepad|calculator|vscode|winword|msedge|powerpnt|...", "thoughts": "<reasoning>"}}
    2. Close app:   {{"action": "close_app", "app_name": "chrome|notepad|winword|google|...", "thoughts": "<reasoning>"}}
    3. Show/Go to desktop: {{"action": "show_desktop", "thoughts": "<reasoning>"}}
    4. Type custom text:  {{"action": "type_text", "text": "<text to type>", "thoughts": "<reasoning>"}}
    5. Press specific key: {{"action": "press_key", "key": "enter|tab|space|backspace|escape|...", "thoughts": "<reasoning>"}}
    6. Press key combination (hotkey): {{"action": "hotkey", "keys": ["ctrl", "c"], "thoughts": "<reasoning>"}}
    7. Sleep/wait (seconds): {{"action": "wait", "seconds": <float>, "thoughts": "<reasoning>"}}
    8. Chrome profile: {{"action": "chrome_profile", "profile_id": <int> | "first" | "second" | "third" | "fourth" | "last", "thoughts": "<reasoning>"}}
    9. Switch active tab: {{"action": "switch_tab", "direction": "next|previous", "thoughts": "<reasoning>"}}
    10. Tell a joke (English/Urdu): {{"action": "joke", "text": "<the joke>", "thoughts": "<reasoning>"}}
    11. General computer/OS commands / META-CAPABILITY: {{"action": "run_command", "command": "<powershell command>", "speak_after": "<done message>", "thoughts": "<reasoning>"}}
    12. Chat/answer: {{"action": "chat", "response": "<short factual answer>", "thoughts": "<reasoning>"}}
    13. Create PowerPoint Presentation: {{"action": "create_powerpoint", "topic": "<presentation topic or content focus>", "thoughts": "<reasoning>"}}
    14. Create Excel Spreadsheet & Pivot Table: {{"action": "create_excel", "topic": "<spreadsheet topic or data model focus>", "thoughts": "<reasoning>"}}
    15. Create professional Word Resume/CV: {{"action": "create_cv", "job_title": "<job title or role focus>", "thoughts": "<reasoning>"}}
    16. Web Search and Deep Reason: {{"action": "search_reason", "query": "<search keywords>", "thoughts": "<reasoning>"}}
    17. Create local text note: {{"action": "create_note", "content": "<note text>", "thoughts": "<reasoning>"}}
    18. Read local text notes: {{"action": "read_notes", "thoughts": "<reasoning>"}}
    19. Play local music: {{"action": "play_music", "song_name": "<name>", "thoughts": "<reasoning>"}}
    20. Check product price online: {{"action": "check_price", "product_name": "<product>", "thoughts": "<reasoning>"}}
    21. Track product price in watchlist: {{"action": "track_price", "product_name": "<product>", "thoughts": "<reasoning>"}}
    22. Read e-commerce price watchlist: {{"action": "check_watchlist", "thoughts": "<reasoning>"}}
    23. Send WhatsApp message: {{"action": "whatsapp_send", "contact": "<name>", "message": "<text>", "thoughts": "<reasoning>"}}
    24. Clean input dictation: {{"action": "clean_dictation", "text": "<rough input text>", "thoughts": "<reasoning>"}}
    25. Click the first link in search results: {{"action": "click_first_link", "thoughts": "<reasoning>"}}
    26. Stark Morning/Startup protocol: {{"action": "startup_protocol", "thoughts": "<reasoning>"}}
    27. System Performance Optimization and safe temp clean: {{"action": "system_diagnostic", "thoughts": "<reasoning>"}}
    28. Scrape and summarize a webpage/article: {{"action": "summarize_webpage", "url": "<url>", "thoughts": "<reasoning>"}}
    29. Store a fact in long-term memory: {{"action": "remember", "fact": "<fact to store>", "thoughts": "<reasoning>"}}
    30. Forget/Remove a fact from long-term memory: {{"action": "forget", "fact": "<exact fact to remove>", "thoughts": "<reasoning>"}}
    31. News Briefing: {{"action": "news_briefing", "thoughts": "<reasoning>"}}
    32. Weather Report: {{"action": "weather_report", "thoughts": "<reasoning>"}}
    33. Dictionary/Translate Word: {{"action": "dictionary_translate", "word": "<word>", "thoughts": "<reasoning>"}}
    34. OCR Scan: {{"action": "ocr_scan", "thoughts": "<reasoning>"}}
    35. Download YouTube Video: {{"action": "download_youtube", "url": "<url>", "thoughts": "<reasoning>"}}
    36. Change Voice Character: {{"action": "change_voice", "gender": "male|female", "thoughts": "<reasoning>"}}
    37. Open user bookmark bar link: {{"action": "open_bookmark", "bookmark_id": "1|2|3|4|5|6|7|playlist|wikipedia|daraz|gmail|youtube|github", "thoughts": "<reasoning>"}}

    Few-Shot Deep Training (Examples):
    Q: "whatsapp pe gaurav ko message kro master is home"
    A: {{"action": "whatsapp_send", "contact": "gaurav", "message": "Master is home", "thoughts": "Sending WhatsApp message to Gaurav as requested."}}
    
    Q: "remember my birthday is October 10th"
    A: {{"action": "remember", "fact": "Master Saad's birthday is October 10th", "thoughts": "Saving user's birthday to semantic memory."}}

    Q: "what is October 10th?"
    A: {{"action": "chat", "response": "According to my files, that is your birthday, Sir.", "thoughts": "Recalling user birthday fact from semantic context."}}

    Q: "get active window name and search it on google"
    A: [
      {{"action": "run_command", "command": "powershell \"(Get-Process | Where-Object {{$_.MainWindowTitle}} | Select-Object -ExpandProperty MainWindowTitle -First 1)\"", "thoughts": "Retrieving the active application window title via PowerShell API."}},
      {{"action": "search_reason", "query": "site:wikipedia.org {{last_result}}", "thoughts": "Searching the web for the retrieved application window title to provide deep details."}}
    ]

    Q: "chrome profile third kholo fir usme youtube search kro"
    A: [
      {{"action": "chrome_profile", "profile_id": 3, "thoughts": "Launching Google Chrome with User Profile 3."}},
      {{"action": "wait", "seconds": 2.0, "thoughts": "Waiting for Chrome window to fully mount."}},
      {{"action": "type_text", "text": "youtube.com", "thoughts": "Typing youtube url."}},
      {{"action": "press_key", "key": "enter", "thoughts": "Submitting navigation."}}
    ]

    Q: "Check system battery health and state it"
    A: {{"action": "run_command", "command": "powershell \"(Get-WmiObject -Class Win32_Battery).EstimatedChargeRemaining\"", "speak_after": "Sir, the battery level is currently at {{last_result}} percent.", "thoughts": "Querying system WMI battery status via PowerShell command."}}

    Q: "Mujhe gussa aa rha hai yaar"
    A: {{"action": "chat", "response": "Take a deep breath, Boss. Remember, even Tony had to step out of the suit sometimes. I'm right here.", "thoughts": "Engaging in emotional support using companion protocols."}}
    """
    
    # Determine Master's Sentiment and Cognitive state
    sentiment = "NORMAL"

    def get_focused_app() -> str:
        """Read the currently active window title from activity_patterns.json.
        Returns an empty string if the file is missing or malformed."""
        try:
            with open("activity_patterns.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("current_window", "")
        except Exception:
            return ""

    prod_drop_words = ["lazy", "slack", "distracted", "idle", "haven't done work", "no productivity", "time waste", "boring"]
    stressed_words = ["stressed", "tired", "exhausted", "angry", "sad", "upset", "gussa", "tension", "pareshan", "thak gaya", "dard"]
    
    for word in stressed_words:
        if word in cmd_lower:
            sentiment = "STRESSED"
            break
    if sentiment == "NORMAL":
        for word in prod_drop_words:
            if word in cmd_lower:
                sentiment = "PRODUCTIVE_DROP"
                break
                
    try:
        with open("sentiment.txt", "w", encoding="utf-8") as sf:
            sf.write(sentiment)
    except Exception:
        pass

    # Inject the active sentiment tuning guidelines into the system prompt
    adapted_prompt = system_prompt + f"\n\n[EMOTIONAL INTELLIGENCE SYSTEM DETECTED SENTIMENT: {sentiment}]\n"
    if sentiment == "STRESSED":
        adapted_prompt += "Guidelines: Master is currently stressed or exhausted. Speak in a highly calming, reassuring, brief, and supportive manner. Offer gentle help, minimize any aggressive or wordy sarcasm, and be extremely empathetic.\n"
    elif sentiment == "PRODUCTIVE_DROP":
        adapted_prompt += "Guidelines: Master is feeling distracted or unproductive. Respond with a slightly more assertive, motivating, and focus-inducing character. Push them back to work gently but directly, offering to assist with their pending tasks.\n"
    else:
        adapted_prompt += "Guidelines: Master is in a normal mood. Respond with your signature loyal, extremely witty, companion-like Stark banter.\n"
    # Add active application context if available
    focused_app = get_focused_app()
    if focused_app:
        adapted_prompt += f"\n[CONTEXT] Active window: {focused_app}\n"

    try:
        history = load_history()
        history.append({"role": "user", "content": command_text})
        
        # Check internet connectivity for Cloud LLM vs Edge AI fallback
        internet_active = is_internet_available()
        
        if not internet_active:
            logger.info("Internet connection check failed. Routing task to local Edge AI...")
            try:
                result_text = query_local_ollama(adapted_prompt, command_text, history)
                logger.info("Edge AI completion retrieved successfully.")
            except Exception as edge_err:
                logger.warning(f"Edge AI local Ollama model unavailable: {edge_err}. Routing to offline heuristic parse...")
                return local_heuristic_parse(cmd_lower)
        else:
            try:
                payload_messages = [{"role": "system", "content": adapted_prompt}]
                payload_messages.extend(history[:-1])
                payload_messages.append({"role": "user", "content": command_text})
                
                completion = client.chat.completions.create(
                    model=selected_model,
                    messages=payload_messages,
                    temperature=0.1,
                    max_tokens=1024
                )
                result_text = completion.choices[0].message.content.strip()
            except Exception as t_err:
                logger.error(f"Selected model failed/rate-limited, trying backup Llama 8B: {t_err}")
                payload_messages = [{"role": "system", "content": adapted_prompt}]
                payload_messages.extend(history[:-1])
                payload_messages.append({"role": "user", "content": command_text})
                
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=payload_messages,
                    temperature=0.1,
                    max_tokens=1024
                )
                result_text = completion.choices[0].message.content.strip()
        
        match = re.search(r'(\[.*?\]|\{.*?\})', result_text, re.DOTALL)
        if match:
            result_text = match.group(1)
            
        result_dict = json.loads(result_text)
        
        # Write reasoning/thoughts output to thoughts.txt for UI presentation
        thoughts_str = ""
        if isinstance(result_dict, dict):
            thoughts_str = result_dict.get("thoughts", "")
        elif isinstance(result_dict, list) and len(result_dict) > 0:
            thoughts_str = " | ".join(item.get("thoughts", "") for item in result_dict if "thoughts" in item)
            
        if thoughts_str:
            try:
                with open("thoughts.txt", "w", encoding="utf-8") as tf:
                    tf.write(thoughts_str)
                logger.info(f"Reasoning thoughts updated: '{thoughts_str}'")
            except Exception as e:
                logger.error(f"Failed to write thoughts.txt: {e}")
        
        resp_text = ""
        if isinstance(result_dict, dict):
            resp_text = result_dict.get("response", result_dict.get("speak_after", result_dict.get("action", "")))
        elif isinstance(result_dict, list) and len(result_dict) > 0:
            resp_text = result_dict[0].get("response", result_dict[0].get("speak_after", result_dict[0].get("action", "")) )
            
        if resp_text:
            history.append({"role": "assistant", "content": str(resp_text)})
            save_history(history)
            
        return result_dict
    except Exception as e:
        logger.error(f"Groq LLM Parser error: {e}. Falling back to offline heuristics.")
        return local_heuristic_parse(cmd_lower)
