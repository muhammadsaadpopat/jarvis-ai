import os
import json
from dotenv import load_dotenv, set_key

# Load environment variables from .env file
load_dotenv()

CONFIG_JSON_PATH = "config.json"
ENV_FILE_PATH = ".env"

class Config:
    @staticmethod
    def get(key, default=None):
        """Get configuration parameter from config.json first, then environment variables."""
        if os.path.exists(CONFIG_JSON_PATH):
            try:
                with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if key in cfg:
                        return cfg[key]
            except Exception:
                pass
        return os.getenv(key, default)

    @staticmethod
    def set_env_value(key, value):
        """Set or update configuration value in the .env file and current process environment."""
        os.environ[key] = value
        try:
            # If .env doesn't exist, create it
            if not os.path.exists(ENV_FILE_PATH):
                with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write("# J.A.R.V.I.S. CONFIGURATION PROFILE\n")
            set_key(ENV_FILE_PATH, key, value)
            return True
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to set env value {key}: {e}")
            return False

    @classmethod
    def get_groq_api_key(cls):
        return cls.get("GROQ_API_KEY", "")

    @classmethod
    def get_sender_email(cls):
        return cls.get("SENDER_EMAIL", "muhammadsaadpopat76@gmail.com")

    @classmethod
    def get_sender_app_password(cls):
        return cls.get("SENDER_APP_PASSWORD", "")

    @classmethod
    def get_voice_security_passcode(cls):
        return cls.get("VOICE_SECURITY_PASSCODE", "alpha zero")

    @classmethod
    def get_access_pin(cls):
        return cls.get("ACCESS_PIN", "0909")

    @classmethod
    def get_news_api_key(cls):
        return cls.get("NEWS_API_KEY", "")

    @classmethod
    def get_tesseract_path(cls):
        return cls.get("TESSERACT_CMD_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

    @classmethod
    def get_selected_model(cls):
        """Read selected model from config.json, default to llama-3.3-70b-versatile."""
        if os.path.exists(CONFIG_JSON_PATH):
            try:
                with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg.get("selected_model", "llama-3.3-70b-versatile")
            except Exception:
                pass
        return "llama-3.3-70b-versatile"

    @classmethod
    def set_selected_model(cls, model_name):
        """Persist selected model to config.json."""
        cfg = {}
        if os.path.exists(CONFIG_JSON_PATH):
            try:
                with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass
        cfg["selected_model"] = model_name
        try:
            with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            return True
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save config.json: {e}")
            return False
