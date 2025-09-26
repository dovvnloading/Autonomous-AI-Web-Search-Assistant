# --- config.py ---

from pathlib import Path
import os
from PySide6.QtCore import QStandardPaths

# Application Data Directory for storing history
APP_NAME = "Chorus"
APP_AUTHOR = "AI"
data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / APP_AUTHOR / APP_NAME
os.makedirs(data_dir, exist_ok=True)
CHAT_HISTORY_FILE = data_dir / "chat_history.json"


# 1. Get the directory where the currently running script is located.
script_dir = Path(__file__).resolve().parent

# 2. Join that directory path with the name of your instructions file.
#    THIS IS THE ONLY LINE THAT HAS BEEN CHANGED.
PROMPT_FILE_PATH = script_dir / "System_Instructions.txt"

# Model Names
EMBEDDING_MODEL = 'nomic-embed-text'
NARRATOR_MODEL = 'qwen2.5:3b'
TITLE_GENERATOR_MODEL = 'qwen2.5:3b' 
INTENT_MODEL = 'qwen3:8b'
VALIDATOR_MODEL = 'qwen3:8b'
REFINER_MODEL = 'qwen3:14b'
ABSTRACTION_MODEL = 'qwen3:8b'
SYNTHESIS_MODEL = 'qwen3:14b'
MEMORY_SUMMARY_MODEL = 'qwen2.5:7b-instruct'

# Search Parameters
SCRAPE_TOP_N_RESULTS = 10
MAX_SOURCES_TO_SCRAPE = 5
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# API Call Parameters
OLLAMA_VALIDATION_TIMEOUT = 90  # 1 minute 30 seconds
OLLAMA_DEFAULT_TIMEOUT = 600 # 10 minutes

# Application Behavior
WORKER_TIMEOUT_MS = 30 * 60 * 1000  # 30 minutes

# UI Logging Styles
LOG_LEVEL_STYLES = {
    "INFO":       "color: #97A3B6;",
    "STEP":       "color: #4EC9B0; font-weight: bold;",
    "WARN":       "color: #DDB45D;",
    "ERROR":      "color: #F47067; font-weight: bold;",
    "AGENT_CALL": "color: #C586C0; font-style: italic;",
    "MEMORY":     "color: #6A9955;",
    "USER":       "color: #007ACC; font-weight: bold;",
    "NARRATOR":   "color: #569CD6; font-style: italic;",
    "PAYLOAD":    "color: #666666; border-left: 2px solid #444; padding-left: 8px; font-family: Consolas, 'Courier New', monospace; white-space: pre-wrap;"
}