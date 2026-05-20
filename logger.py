import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "jarvis.log")

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger():
    """Sets up standard rotating logger for JARVIS."""
    logger = logging.getLogger("JARVIS")
    logger.setLevel(logging.DEBUG)

    # Prevent adding duplicate handlers if logger is already configured
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (Rotating, max 5MB per file, keep 3 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("J.A.R.V.I.S. Logger Initialized successfully.")
    return logger

# Global logger instance
logger = setup_logger()
