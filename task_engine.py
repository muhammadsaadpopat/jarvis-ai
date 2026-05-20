# task_engine.py
"""Advanced Workflow & Task Execution Engine for J.A.R.V.I.S.

Provides custom scheduling, step-by-step progress tracking,
and integration with voice_engine execution hooks.
"""

import json
import os
import time
import threading
import subprocess
from datetime import datetime
from logger import logger

TASK_FILE = "tasks.json"

class TaskEngine:
    def __init__(self):
        self.tasks = []
        self.lock = threading.Lock()
        self.load_tasks()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def load_tasks(self):
        with self.lock:
            if os.path.exists(TASK_FILE):
                try:
                    with open(TASK_FILE, "r", encoding="utf-8") as f:
                        self.tasks = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading tasks: {e}")
                    self.tasks = []
            else:
                self.tasks = []

    def save_tasks(self):
        with self.lock:
            try:
                with open(TASK_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.tasks, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving tasks: {e}")

    def create_task(self, name: str, description: str, steps: list) -> dict:
        """Create a new automation workflow task.
        
        Steps format example:
        [
            {"action": "speak", "text": "Starting compile process..."},
            {"action": "run_command", "command": "python compiler.py"},
            {"action": "speak", "text": "Deployment complete."}
        ]
        """
        task = {
            "id": str(int(time.time() * 1000)),
            "name": name,
            "description": description,
            "steps": steps,
            "status": "PENDING",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        with self.lock:
            self.tasks.append(task)
        self.save_tasks()
        return task

    def get_tasks(self) -> list:
        """Return the current list of tasks."""
        with self.lock:
            return list(self.tasks)

    def delete_task(self, task_id: str):
        """Delete a task by its unique ID."""
        with self.lock:
            self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self.save_tasks()

    def _worker_loop(self):
        while True:
            # Find the next pending task
            active_task = None
            with self.lock:
                for t in self.tasks:
                    if t["status"] == "PENDING":
                        t["status"] = "RUNNING"
                        t["updated_at"] = datetime.now().isoformat()
                        active_task = dict(t)
                        break
            
            if active_task:
                self.save_tasks()
                self._execute_task(active_task)
            else:
                time.sleep(1)

    def _execute_task(self, task):
        logger.info(f"Starting execution of workflow task: {task['name']}")
        steps = task["steps"]
        total_steps = len(steps)
        
        # Import voice_engine locally to avoid cyclic dependency
        import voice_engine
        
        success = True
        for idx, step in enumerate(steps):
            try:
                logger.info(f"Executing step {idx+1}/{total_steps} for task {task['name']}: {step}")
                
                # Update progress
                progress_pct = int(((idx) / total_steps) * 100)
                self._update_task_progress(task["id"], "RUNNING", progress_pct)
                
                action = step.get("action")
                if action == "speak":
                    voice_engine.speak(step.get("text", ""))
                    time.sleep(len(step.get("text", "")) * 0.08 + 1)
                elif action == "run_command":
                    cmd = step.get("command")
                    if cmd:
                        subprocess.run(cmd, shell=True)
                elif action == "execute_action":
                    action_data = step.get("action_data")
                    command_text = step.get("command_text", "")
                    voice_engine.execute_action(action_data, command_text=command_text, verified=True)
                
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error executing step {idx} of task {task['id']}: {e}")
                success = False
                break
                
        final_status = "COMPLETED" if success else "FAILED"
        self._update_task_progress(task["id"], final_status, 100)
        logger.info(f"Task {task['name']} finished with status: {final_status}")

    def _update_task_progress(self, task_id: str, status: str, progress: int):
        with self.lock:
            for t in self.tasks:
                if t["id"] == task_id:
                    t["status"] = status
                    t["progress"] = progress
                    t["updated_at"] = datetime.now().isoformat()
                    break
        self.save_tasks()

task_engine = TaskEngine()
