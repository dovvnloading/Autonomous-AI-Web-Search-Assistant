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

    def add_message(self, role: str, content: str):
        """Adds a message to the memory, generating and storing its embedding."""
        self._log(f"Embedding new '{role}' message...")
        embedding = self._get_embedding(content)
        self.memory.append({
            'role': role,
            'content': content,
            'embedding': embedding,
            'timestamp': datetime.now()
        })
        self._log(f"Message added. Total memories: {len(self.memory)}")

    def retrieve_relevant_messages(self, query: str, top_k: int = 3, last_n: int = 2) -> List[Dict[str, str]]:
        """
        Retrieves a combination of the most recent messages (guaranteed for conversational context) 
        and semantically relevant messages from the rest of the chat history.
        """
        if not self.memory:
            self._log("Memory is empty. No messages to retrieve.")
            return []

        self._log(f"Retrieving contextual history: {top_k} semantic + last {last_n} guaranteed.")

        actual_last_n = min(last_n, len(self.memory))
        guaranteed_messages = self.memory[-actual_last_n:]
        if guaranteed_messages:
            self._log(f"Guaranteed retrieval of last {len(guaranteed_messages)} messages.", "INFO")

        searchable_memory = self.memory[:-actual_last_n] if len(self.memory) > actual_last_n else []
        
        semantic_messages = []
        if searchable_memory and top_k > 0:
            self._log(f"Searching {top_k} semantic messages in remaining {len(searchable_memory)} memories...", "INFO")
            query_embedding = self._get_embedding(query)

            scored_messages = []
            for mem in searchable_memory:
                similarity = self._cosine_similarity(query_embedding, mem['embedding'])
                scored_messages.append({'message': mem, 'score': similarity})

            scored_messages.sort(key=lambda x: x['score'], reverse=True)

            for item in scored_messages[:top_k]:
                message_content = item['message']['content']
                self._log(f"Retrieved semantically (Score: {item['score']:.4f}): '{message_content[:60]}...'", "INFO")
                semantic_messages.append(item['message'])
        elif top_k <= 0:
             self._log("Semantic search skipped (top_k=0).", "INFO")
        else:
            self._log("No older messages available for semantic search.", "INFO")

        combined_messages = semantic_messages + guaranteed_messages

        final_history = []
        for msg in combined_messages:
            final_history.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        self._log(f"Final contextual history contains {len(final_history)} messages.")
        return final_history

    def clear(self):
        """Clears all messages from the semantic memory."""
        self.memory = []
        self._log("Memory has been cleared.")