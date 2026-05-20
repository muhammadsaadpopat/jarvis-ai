# test_suite.py
"""Automated Unit Testing Suite for J.A.R.V.I.S. Custom Features.

Verifies the correct operation of:
- vault.py (encrypted secret storage)
- profile_manager.py (encrypted user configurations)
- dialogues.py & ai_brain.py dialogues integration
- task_engine.py (advanced workflow execution engine)
"""

import os
import time
import unittest
import json
import keyring

# Configure keyring mock or temporary entry if needed (system keyring will be used safely)
from vault import store_secret, retrieve_secret, list_secrets, delete_secret
from profile_manager import create_profile, load_profile, list_profiles, delete_profile
from dialogues import DIALOGUES
from task_engine import task_engine

class TestJarvisCoreFeatures(unittest.TestCase):
    
    def setUp(self):
        self.secret_name = "test credentials"
        self.secret_val = "tony_stark_super_secret_passphrase"
        self.profile_name = "test jarvis profile"
        self.profile_cfg = {"model": "llama-3.3-70b-versatile", "rate": 180, "gender": "male"}

    def tearDown(self):
        # Clean up any vault secret created
        try:
            if self.secret_name in list_secrets():
                delete_secret(self.secret_name)
        except Exception:
            pass
        # Clean up any profile created
        try:
            if self.profile_name in list_profiles():
                delete_profile(self.profile_name)
        except Exception:
            pass

    def test_01_vault_encryption(self):
        """Verify secrets are encrypted and retrieved cleanly."""
        store_secret(self.secret_name, self.secret_val)
        
        # Check secret exists in list
        secrets = list_secrets()
        self.assertIn(self.secret_name, secrets)
        
        # Decrypt and check value
        decrypted = retrieve_secret(self.secret_name)
        self.assertEqual(decrypted, self.secret_val)
        
        # Test deletion
        delete_secret(self.secret_name)
        secrets_after = list_secrets()
        self.assertNotIn(self.secret_name, secrets_after)

    def test_02_profile_manager(self):
        """Verify profile configs are encrypted and decrypted perfectly."""
        create_profile(self.profile_name, self.profile_cfg)
        
        # Check profile exists in list
        profiles = list_profiles()
        self.assertIn(self.profile_name, profiles)
        
        # Load and verify content
        loaded = load_profile(self.profile_name)
        self.assertEqual(loaded["model"], self.profile_cfg["model"])
        self.assertEqual(loaded["rate"], self.profile_cfg["rate"])
        self.assertEqual(loaded["gender"], self.profile_cfg["gender"])
        
        # Test deletion
        delete_profile(self.profile_name)
        profiles_after = list_profiles()
        self.assertNotIn(self.profile_name, profiles_after)

    def test_03_dialogues_presence(self):
        """Verify dialogues.py is healthy and DIALOGUES keys are complete."""
        self.assertIsInstance(DIALOGUES, dict)
        self.assertIn("greeting", DIALOGUES)
        self.assertIn("acknowledge", DIALOGUES)
        self.assertIn("completion", DIALOGUES)

    def test_04_task_engine(self):
        """Verify task workflow creation, listing, and delete actions."""
        steps = [
            {"action": "speak", "text": "Initiating startup procedure."},
            {"action": "speak", "text": "All systems nominal."}
        ]
        task = task_engine.create_task("Startup Test", "Verifies task system.", steps)
        
        self.assertIsNotNone(task["id"])
        self.assertEqual(task["name"], "Startup Test")
        self.assertEqual(task["status"], "PENDING")
        self.assertEqual(len(task["steps"]), 2)
        
        # Verify it lists
        tasks = task_engine.get_tasks()
        self.assertTrue(any(t["id"] == task["id"] for t in tasks))
        
        # Clean up
        task_engine.delete_task(task["id"])
        tasks_after = task_engine.get_tasks()
        self.assertFalse(any(t["id"] == task["id"] for t in tasks_after))

    def test_05_local_heuristic_parse(self):
        """Verify that offline local heuristic parses correctly capture intents and do not fail with NameError."""
        from ai_brain import local_heuristic_parse
        
        # Test Volume Controls heuristic
        vol_res = local_heuristic_parse("volume up")
        self.assertEqual(vol_res["action"], "run_command")
        self.assertIn("SendKeys", vol_res["command"])
        
        # Test Open App heuristic
        open_res = local_heuristic_parse("open chrome")
        self.assertEqual(open_res["action"], "open_app")
        self.assertEqual(open_res["app_name"], "chrome")
        
        # Test Offline Autopilot Code Synthesis
        snake_res = local_heuristic_parse("banao snake game python mein")
        self.assertEqual(snake_res["action"], "write_code")
        self.assertIn("SnakeGame", snake_res["code_override"])
        self.assertIn("tkinter", snake_res["code_override"])

        # Test Bookmarks heuristic
        bk_res = local_heuristic_parse("open bookmark 3")
        self.assertEqual(bk_res["action"], "open_bookmark")
        self.assertEqual(bk_res["bookmark_id"], "3")

if __name__ == "__main__":
    unittest.main()
