# --- semantic_memory.py ---
from datetime import datetime
from typing import Dict, List
import numpy as np
import ollama
from config import EMBEDDING_MODEL

class SemanticMemory:
    """Handles storing and retrieving chat messages using embeddings for semantic recall."""
    def __init__(self, model=EMBEDDING_MODEL, log_callback=None):
        self.model = model
        self.memory = []
        self.log_callback = log_callback

    def _log(self, message, level="MEMORY"):
        if self.log_callback:
            self.log_callback(f"{message}", level)

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generates an embedding for a given text."""
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return np.array(response['embedding'])
        except Exception as e:
            self._log(f"Error generating embedding: {e}", "ERROR")
            return np.zeros(768) 

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculates the cosine similarity between two vectors."""
        if np.all(vec1 == 0) or np.all(vec2 == 0):
            return 0.0
        dot_product = np.dot(vec1, vec2)
        norm_vec1 = np.linalg.norm(vec1)
        norm_vec2 = np.linalg.norm(vec2)
        return dot_product / (norm_vec1 * norm_vec2)

    def add_message(self, role: str, memory_content: str, display_content: str = None):
        """Adds a message to memory and returns a storable dictionary."""
        self._log(f"Embedding new '{role}' message for memory...")
        embedding = self._get_embedding(memory_content)
        
        # Add to live memory
        new_memory_item = {
            'role': role,
            'content': memory_content,
            'embedding': embedding,
            'timestamp': datetime.now()
        }
        self.memory.append(new_memory_item)
        self._log(f"Message added to live memory. Total: {len(self.memory)}")

        # Return the version to be saved to disk
        return {
            'role': role,
            'memory_content': memory_content,
            'display_content': display_content if display_content is not None else memory_content,
            'embedding': embedding.tolist(),
            'timestamp': new_memory_item['timestamp'].isoformat()
        }

    def retrieve_relevant_messages(self, query: str, top_k: int = 3, last_n: int = 2) -> List[Dict[str, str]]:
        if not self.memory:
            self._log("Memory is empty. No messages to retrieve.", "INFO")
            return []

        self._log(f"Retrieving contextual history: {top_k} semantic + last {last_n} guaranteed.")
        actual_last_n = min(last_n, len(self.memory))
        guaranteed_messages = self.memory[-actual_last_n:]
        searchable_memory = self.memory[:-actual_last_n] if len(self.memory) > actual_last_n else []
        
        semantic_messages = []
        if searchable_memory and top_k > 0:
            self._log(f"Searching {top_k} semantic messages in remaining {len(searchable_memory)} memories...", "INFO")
            query_embedding = self._get_embedding(query)
            scored_messages = [{'message': mem, 'score': self._cosine_similarity(query_embedding, mem['embedding'])} for mem in searchable_memory]
            scored_messages.sort(key=lambda x: x['score'], reverse=True)
            semantic_messages = [item['message'] for item in scored_messages[:top_k]]
        
        combined_messages = semantic_messages + guaranteed_messages
        final_history = [{'role': msg['role'], 'content': msg['content']} for msg in combined_messages]
        self._log(f"Final contextual history contains {len(final_history)} messages.")
        return final_history

    def load_memory(self, message_history: List[Dict]):
        """Loads and prepares a full chat history into the semantic memory."""
        self.clear()
        self._log(f"Loading {len(message_history)} messages into semantic memory...")
        loaded_memories = []
        for msg in message_history:
            # --- FIX: Add a check to prevent crashing on corrupted data ---
            if not msg:
                self._log("Skipping invalid (None) message in history.", "WARN")
                continue

            content_for_memory = msg.get('memory_content', msg.get('content', ''))
            embedding_list = msg.get('embedding', [])
            embedding_np = np.array(embedding_list) if embedding_list else self._get_embedding(content_for_memory)

            loaded_memories.append({
                'role': msg['role'],
                'content': content_for_memory,
                'embedding': embedding_np,
                'timestamp': datetime.fromisoformat(msg['timestamp']) if 'timestamp' in msg else datetime.now()
            })
        self.memory = loaded_memories
        self._log(f"Memory loaded successfully. Total memories: {len(self.memory)}")


    def clear(self):
        """Clears all messages from the semantic memory."""
        self.memory = []
        self._log("Memory has been cleared.")