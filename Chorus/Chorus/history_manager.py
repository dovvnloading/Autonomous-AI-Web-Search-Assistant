# --- history_manager.py ---
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
from config import CHAT_HISTORY_FILE

class HistoryManager:
    """Handles loading, saving, and managing chat history from a JSON file."""
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.file_path = CHAT_HISTORY_FILE
        self.chats = self.load_history()

    def _log(self, message, level="INFO"):
        if self.log_callback:
            self.log_callback(f"{message}", level)

    def load_history(self) -> Dict[str, Dict]:
        """Loads the entire chat history from the JSON file."""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._log(f"Loaded {len(data)} chats from history.", "INFO")
                    return data
            self._log("No chat history file found, starting fresh.", "INFO")
            return {}
        except (json.JSONDecodeError, IOError) as e:
            self._log(f"Error loading chat history: {e}. Starting with a blank slate.", "ERROR")
            return {}

    def save_history(self):
        """Saves the entire current state of chats to the JSON file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.chats, f, indent=4)
            self._log("Chat history saved successfully.", "INFO")
        except IOError as e:
            self._log(f"Failed to save chat history: {e}", "ERROR")

    def create_new_chat(self) -> str:
        """Creates a new, empty chat session and returns its ID."""
        chat_id = str(uuid.uuid4())
        self.chats[chat_id] = {
            "id": chat_id,
            "title": "New Chat",
            "created_at": datetime.now().isoformat(),
            "messages": []
        }
        self._log(f"Created new chat with ID: {chat_id}", "INFO")
        self.save_history()
        return chat_id

    def add_message_to_chat(self, chat_id: str, message: Dict):
        """Adds a message to a specific chat and saves."""
        if chat_id in self.chats:
            self.chats[chat_id]["messages"].append(message)
            self.save_history()
        else:
            self._log(f"Attempted to add message to non-existent chat ID: {chat_id}", "WARN")

    def get_chat(self, chat_id: str) -> Optional[Dict]:
        """Retrieves a single chat by its ID."""
        return self.chats.get(chat_id)

    def get_all_chats_sorted(self) -> List[Dict]:
        """Returns a list of all chats, sorted by creation date (newest first)."""
        return sorted(self.chats.values(), key=lambda x: x['created_at'], reverse=True)

    def delete_chat(self, chat_id: str) -> bool:
        """Deletes a chat from memory and saves the history."""
        if chat_id in self.chats:
            del self.chats[chat_id]
            self.save_history()
            self._log(f"Deleted chat with ID: {chat_id}", "INFO")
            return True
        return False

    def update_chat_title(self, chat_id: str, new_title: str):
        """Updates the title of a specific chat."""
        if chat_id in self.chats:
            self.chats[chat_id]['title'] = new_title
            self.save_history()
            self._log(f"Updated title for chat {chat_id} to '{new_title}'", "INFO")
        else:
            self._log(f"Cannot update title for non-existent chat: {chat_id}", "WARN")