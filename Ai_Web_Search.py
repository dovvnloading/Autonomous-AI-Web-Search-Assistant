import sys
import re
from PySide6.QtGui import QTextCursor
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import ollama
import markdown2
import trafilatura
import numpy as np

# --- LIBRARIES for robust scraping ---
from ddgs import DDGS
from bs4 import BeautifulSoup

# This script uses PySide6.
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QPushButton, QLabel,

                             QFrame, QScrollArea, QProgressBar, QSplitter)
from PySide6.QtCore import QTimer, Qt, QThread, Signal, QPropertyAnimation, QEasingCurve

# --- NEW: SEMANTIC MEMORY CLASS ---
class SemanticMemory:
    """Handles storing and retrieving chat messages using embeddings for semantic recall."""
    def __init__(self, model='nomic-embed-text', log_callback=None):
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

class SearchWorker(QThread):
    finished = Signal(str, str)
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def _load_prompts_from_file(self, file_path: str) -> Dict[str, str]:
        """Loads and parses all system prompts from a single text file."""
        prompts = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = re.split(r'(\[--- PROMPT: .*? ---\]\n)', content)
            if len(sections) < 2:
                raise ValueError("Prompt file is empty or has an invalid format. No delimiters found.")

            for i in range(1, len(sections), 2):
                header = sections[i]
                prompt_text = sections[i+1].strip()
                
                match = re.search(r'\[--- PROMPT: (.*?) ---\]', header)
                if match:
                    prompt_name = match.group(1)
                    prompts[prompt_name] = prompt_text
                else:
                    self.log_message.emit(f"Could not parse prompt header: {header}", "WARN")

            required_prompts = ['NARRATOR_PROMPT', 'SEARCH_INTENT_PROMPT', 'VALIDATOR_PROMPT', 'REFINER_PROMPT', 'ABSTRACTION_PROMPT', 'SYNTHESIS_PROMPT', 'MEMORY_SUMMARY_PROMPT']
            for p_name in required_prompts:
                if p_name not in prompts:
                    raise KeyError(f"Required prompt '{p_name}' not found in the instructions file.")
            
            self.log_message.emit(f"Successfully loaded {len(prompts)} system prompts from file.", "INFO")
            return prompts

        except FileNotFoundError:
            error_msg = f"CRITICAL ERROR: The system instructions file was not found at '{file_path}'. The application cannot start."
            self.log_message.emit(error_msg, "ERROR")
            print(error_msg)
            sys.exit(1)
        except (ValueError, KeyError) as e:
            error_msg = f"CRITICAL ERROR: Failed to parse system instructions file. Reason: {e}. The application cannot start."
            self.log_message.emit(error_msg, "ERROR")
            print(error_msg)
            sys.exit(1)
        except Exception as e:
            error_msg = f"An unexpected critical error occurred while loading prompts: {e}"
            self.log_message.emit(error_msg, "ERROR")
            print(error_msg)
            sys.exit(1)

    def __init__(self, prompt: str, memory: SemanticMemory):
        super().__init__()
        self.prompt = prompt
        self.memory = memory
        self.start_time = None
        self.last_step_time = None

        self.SCRAPE_TOP_N_RESULTS = 5
        self.MAX_SOURCES_TO_SCRAPE = 2

        prompt_file_path = r"C:\Users\Admin\source\repos\Phi-Search\System_Instructions.txt"
        self.prompts = self._load_prompts_from_file(prompt_file_path)

        now = datetime.now()
        
        temporal_context = {
            "current_date": now.strftime('%A, %B %d, %Y'),
            "current_time": now.strftime('%I:%M:%S %p'),
            "current_timezone": now.astimezone().tzname()
        }
        
        formatted_search_intent_prompt = self.prompts['SEARCH_INTENT_PROMPT'].format(**temporal_context)

        self.validator_messages = [{'role': 'system', 'content': self.prompts['VALIDATOR_PROMPT']}]
        self.refiner_messages = [{'role': 'system', 'content': self.prompts['REFINER_PROMPT']}]
        self.abstraction_messages = [{'role': 'system', 'content': self.prompts['ABSTRACTION_PROMPT']}]
        self.narrator_messages = [{'role': 'system', 'content': self.prompts['NARRATOR_PROMPT']}]
        self.search_intent_messages = [{'role': 'system', 'content': formatted_search_intent_prompt}]
        self.synthesis_messages = [{'role': 'system', 'content': self.prompts['SYNTHESIS_PROMPT']}]
        self.memory_summary_messages = [{'role': 'system', 'content': self.prompts['MEMORY_SUMMARY_PROMPT']}]


    def _format_duration(self, duration: timedelta) -> str:
        """Formats a timedelta object into a human-readable string."""
        seconds = duration.total_seconds()
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes, seconds = divmod(seconds, 60)
        return f"{int(minutes)}m {int(seconds)}s"

    def _log_step(self, message: str):
        """Logs a step message and includes the time taken since the last step."""
        now = datetime.now()
        duration = now - self.last_step_time
        formatted_duration = self._format_duration(duration)
        
        self.log_message.emit(f"{message} (took {formatted_duration})", "STEP")
        self.last_step_time = now

    def _narrate_step(self, current_action_description: str):
        if len(self.narrator_messages) > 5:
            self.narrator_messages = [self.narrator_messages[0]] + self.narrator_messages[-4:]

        prompt = f"""## Your Previous Thoughts:
        {chr(10).join(f"- {m['content']}" for m in self.narrator_messages if m['role'] == 'assistant')}

        ## Current Action:
        {current_action_description}
        """
        messages_for_narrator = self.narrator_messages + [{'role': 'user', 'content': prompt}]

        try:
            response = ollama.chat(model='qwen2.5:7b-instruct', messages=messages_for_narrator, stream=False)
            narration = response['message']['content'].strip()
            
            narration = re.sub(r'["\']', '', narration)
            if not narration.endswith(('.', '!', '?')):
                narration += '.'

            self.log_message.emit(narration, "NARRATOR")
            self.narrator_messages.append({'role': 'assistant', 'content': narration})
        except Exception as e:
            self.log_message.emit(f"Narrator agent failed: {e}", "WARN")

    def _get_search_plan(self, user_query: str) -> Tuple[List[Tuple[str, None]], str]:
        """
        Calls the IntentAgent to get a search plan, including topics and a search type.
        Returns a tuple containing a list of topic tuples and the determined search type.
        """
        self.log_message.emit("Calling IntentAgent with conversational context...", "AGENT_CALL")
        self.progress.emit("Decomposing query for targeted search...")
        try:
            relevant_history = self.memory.retrieve_relevant_messages(user_query, top_k=3, last_n=2)
            
            sanitized_history = []
            for msg in relevant_history:
                if msg['role'] == 'assistant':
                    clean_content = re.sub(r'<think>.*?</think>', '', msg['content'], flags=re.DOTALL)
                    clean_content = re.sub(r'<search_request>.*?</search_request>', '', clean_content, flags=re.DOTALL).strip()
                    sanitized_history.append({'role': 'assistant', 'content': clean_content})
                else:
                    sanitized_history.append(msg)
            
            self.log_message.emit(f"Providing {len(sanitized_history)} contextual messages to IntentAgent.", "INFO")
            
            system_message = self.search_intent_messages[0]
            current_user_message = {'role': 'user', 'content': user_query}
            
            messages = [system_message] + sanitized_history + [current_user_message]
            
            response = ollama.chat(model='qwen3:14b', messages=messages, stream=False)
            plan_text = response['message']['content'].strip()
            self.log_message.emit(f"IntentAgent Plan received:\n{plan_text}", "PAYLOAD")
            
            search_type_match = re.search(r'<search_type>(.*?)</search_type>', plan_text, re.DOTALL)
            search_type = "general"
            if search_type_match:
                search_type = search_type_match.group(1).strip().lower()
                self.log_message.emit(f"IntentAgent classified search type as: '{search_type.upper()}'", "INFO")
            else:
                self.log_message.emit("IntentAgent did not provide a search type. Defaulting to 'GENERAL'.", "WARN")

            topics = re.findall(r'<topic>(.*?)</topic>', plan_text, re.DOTALL)
            search_requests = []
            if topics:
                search_requests = [(topic.strip(), None) for topic in topics]
                self.log_message.emit(f"Plan parsed into {len(search_requests)} search operations.", "INFO")
            else:
                self.log_message.emit("Plan was generated but no topics found. Using original prompt as fallback.", "WARN")
                search_requests = [(user_query, None)]
            
            return search_requests, search_type
            
        except Exception as e:
            self.log_message.emit(f"IntentAgent Failed: {e}. Proceeding without plan.", "ERROR")
            return [(user_query, None)], "general"
    
    def _summarize_for_memory(self, user_query: str, final_answer: str) -> str:
        """Generates a concise summary of the interaction for storing in semantic memory."""
        self.log_message.emit("Calling MemorySummaryAgent to condense the response...", "AGENT_CALL")
        
        clean_answer = re.sub(r'<think>.*?</think>', '', final_answer, flags=re.DOTALL).strip()
        clean_answer = re.sub(r'<sources>.*?</sources>', '', clean_answer, flags=re.DOTALL).strip()

        if not clean_answer:
            self.log_message.emit("Final answer was empty; creating a placeholder memory.", "WARN")
            return f"An answer was generated for the query '{user_query}' but it was empty."

        summary_prompt = f"""USER QUERY:
        {user_query}

        FULL AI ANSWER:
        {clean_answer}
        """
        
        try:
            messages = self.memory_summary_messages + [{'role': 'user', 'content': summary_prompt}]
            response = ollama.chat(model='qwen2.5:7b-instruct', messages=messages, stream=False)
            summary = response['message']['content'].strip()
            
            if not summary:
                self.log_message.emit("MemorySummaryAgent produced an empty response. Falling back.", "WARN")
                return f"Provided a detailed, source-based answer to the user's query about: '{user_query[:100]}...'"

            self.log_message.emit("Successfully generated memory summary.", "INFO")
            return summary
        except Exception as e:
            self.log_message.emit(f"MemorySummaryAgent Failed: {e}. Creating a basic summary.", "ERROR")
            return f"Responded to the user query: '{user_query}'"

    def _get_refined_search_plan(self, failed_query: str, failure_reason: str) -> List[Tuple[str, None]]:
        self.log_message.emit("Calling RefinerAgent to improve failed search...", "AGENT_CALL")
        self.progress.emit("Refining search plan based on feedback...")
        
        refiner_prompt = f"""ORIGINAL USER QUERY: {self.prompt}
        FAILED SEARCH QUERY: {failed_query}
        FAILURE REASON: {failure_reason}
        """
        
        try:
            messages = self.refiner_messages + [{'role': 'user', 'content': refiner_prompt}]
            response = ollama.chat(model='qwen3:14b', messages=messages, stream=False)
            plan = response['message']['content'].strip()
            self.log_message.emit(f"RefinerAgent plan received:\n{plan}", "PAYLOAD")
            
            topics = re.findall(r'<topic>(.*?)</topic>', plan, re.DOTALL)
            if topics:
                refined_requests = [(topic.strip(), None) for topic in topics]
                self.log_message.emit(f"RefinerAgent parsed {len(refined_requests)} new search topics.", "INFO")
                return refined_requests
            else:
                self.log_message.emit("RefinerAgent produced a plan, but no topics were found in it.", "WARN")
                return []
        except Exception as e:
            self.log_message.emit(f"RefinerAgent Failed: {e}. Cannot refine search.", "ERROR")
            return []
    
    def _structure_scraped_data_batch(self, user_query: str, raw_scraped_results: List[str]) -> str:
        self.log_message.emit(f"Calling AbstractionAgent in batch mode for {len(raw_scraped_results)} sources...", "AGENT_CALL")
        self.progress.emit("Abstracting key information...")
        
        all_structured_summaries = []
        
        for i, result_str in enumerate(raw_scraped_results):
            self.log_message.emit(f"Abstracting source {i+1}/{len(raw_scraped_results)}...", "INFO")
            
            abstraction_task_prompt = f"""ORIGINAL USER QUERY: {user_query}
            
            RAW SCRAPED DATA:
            {result_str}
            """
            
            try:
                messages = self.abstraction_messages + [{'role': 'user', 'content': abstraction_task_prompt}]
                response = ollama.chat(model='qwen3:8b', messages=messages, stream=False)
                structured_output = response['message']['content'].strip()
                
                match = re.search(r'<structured_data>(.*?)</structured_data>', structured_output, re.DOTALL)
                if match:
                    clean_structured_data = match.group(1).strip()
                    all_structured_summaries.append(clean_structured_data)
                    self.log_message.emit(f"Source {i+1} successfully structured.", "INFO")
                else:
                    self.log_message.emit(f"Source {i+1} response did not contain valid <structured_data> tags. Skipping.", "WARN")
                    # self.log_message.emit(f"INVALID ABSTRACTION PAYLOAD:\n{structured_output}", "PAYLOAD")

            except Exception as e:
                self.log_message.emit(f"AbstractionAgent failed for source {i+1}: {e}. Skipping.", "ERROR")

        if not all_structured_summaries:
            self.log_message.emit("AbstractionAgent failed to structure any data. Falling back to raw data.", "ERROR")
            return "\n".join(raw_scraped_results)
        
        final_combined_summary = "\n\n".join(all_structured_summaries)
        self.log_message.emit(f"Abstraction complete. {len(all_structured_summaries)}/{len(raw_scraped_results)} sources successfully summarized.", "INFO")
        # self.log_message.emit(f"FINAL STRUCTURED DATA:\n{final_combined_summary}", "PAYLOAD")
        return final_combined_summary

    def _validate_scraped_content_batch(self, content_query_pairs: List[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
        self.log_message.emit(f"Calling ValidatorAgent in batch mode for {len(content_query_pairs)} sources...", "AGENT_CALL")
        
        passed_content = []
        failure_reasons = []

        if not content_query_pairs:
            return [], []

        for i, (content, specific_query) in enumerate(content_query_pairs):
            self.progress.emit(f"Validating source {i+1}/{len(content_query_pairs)}...")
            
            url_match = re.search(r'<result url="([^"]+)"', content)
            title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
            source_title = title_match.group(1).strip() if title_match else "Unknown Title"

            validation_prompt = f"USER'S GOAL: {specific_query}\n\nCONTENT TO CHECK:\n{content}"
            
            try:
                validator_messages = self.validator_messages + [{'role': 'user', 'content': validation_prompt}]
                response = ollama.chat(model='qwen3:8b', messages=validator_messages, stream=False)
                validator_output = response['message']['content'].strip()                
                
                # self.log_message.emit(f"--- VALIDATOR RAW OUTPUT FOR '{source_title}' ---\n{validator_output}", "PAYLOAD")

                output_lower = validator_output.lower()

                if '<pass>' in output_lower:
                    passed_content.append(content)
                    self.log_message.emit(f"Source {i+1} PARSED AS: PASS", "INFO")
                elif '<fail>' in output_lower:
                    fail_match = re.search(r'<fail>(.*?)</fail>', validator_output, re.IGNORECASE | re.DOTALL)
                    reason = fail_match.group(1).strip() if fail_match else "Reason not specified."
                    failure_reasons.append(f"{source_title}: {reason}")
                    self.log_message.emit(f"Source {i+1} PARSED AS: FAIL ({reason})", "WARN")
                else:
                    reason = "Ambiguous (No <pass> or <fail> tag found)"
                    failure_reasons.append(f"{source_title}: {reason}")
                    self.log_message.emit(f"Source {i+1} PARSED AS: AMBIGUOUS", "WARN")
                    
            except Exception as e:
                reason = f"Validator agent call failed: {e}"
                failure_reasons.append(f"{source_title}: {reason}")
                self.log_message.emit(f"Source {i+1} FAILED ({source_title}) due to an error: {e}", "ERROR")

        self._log_step(f"Validation complete: {len(passed_content)}/{len(content_query_pairs)} sources passed.")
        return passed_content, failure_reasons

    def _filter_sources_by_passed_content(self, all_sources: List[Dict], passed_content_strings: List[str]) -> List[Dict]:
        passed_urls = set()
        for content in passed_content_strings:
            match = re.search(r'<result url="([^"]+)"', content)
            if match:
                passed_urls.add(match.group(1))
        
        return [source for source in all_sources if source.get('url') in passed_urls]

    def run(self):
        try:
            self.start_time = datetime.now()
            self.last_step_time = self.start_time
            self._log_step("New Request Started")
            self._narrate_step(f"A new request has been initiated for the user's query: '{self.prompt[:80]}...'")
            
            sources_used_for_synthesis = []
            final_response = ""
            search_requests = []
            initial_model_response = "" 

            relevant_history = self.memory.retrieve_relevant_messages(self.prompt, top_k=3, last_n=2)
            sanitized_history = []
            for msg in relevant_history:
                if msg['role'] == 'assistant':
                    clean_content = re.sub(r'<think>.*?</think>', '', msg['content'], flags=re.DOTALL)
                    clean_content = re.sub(r'<search_request>.*?</search_request>', '', clean_content, flags=re.DOTALL).strip()
                    sanitized_history.append({'role': 'assistant', 'content': clean_content})
                else:
                    sanitized_history.append(msg)
            
            self._log_step("Default search mode engaged. Generating search plan.")
            self.progress.emit("Generating search plan...")
            self._narrate_step("A web search is required by default. I will now create a search plan to find the best information.")
            
            # --- MODIFICATION START ---
            # _get_search_plan now returns a tuple (requests, type)
            search_requests, search_type = self._get_search_plan(self.prompt)
            # --- MODIFICATION END ---
            
            if search_requests:
                search_basis = 'generated plan'
                self._log_step(f"Performing targeted search based on {search_basis}.")
                self._narrate_step(f"A search is required. I'm now executing the search plan with {len(search_requests)} topic(s).")
                
                synthesis_system_message = self.synthesis_messages[0]
                current_user_message = {'role': 'user', 'content': self.prompt}

                # --- MODIFICATION START ---
                # Pass the search_type to the execution method
                scraped_content, sources_from_search = self.execute_search_plan(search_requests, search_type)
                # --- MODIFICATION END ---

                if not scraped_content:
                    self.log_message.emit("Search returned no usable content. Responding with available knowledge.", "WARN")
                    self._narrate_step("The web search came up empty. I'll have to answer based on what I already know.")
                    prompt_for_no_search = "The web search failed to return any content. Please answer the user's last question using only your existing knowledge, without mentioning the failed search."
                    
                    messages_for_fallback = [synthesis_system_message] + sanitized_history + [
                        {'role': 'assistant', 'content': initial_model_response},
                        current_user_message,
                        {'role': 'user', 'content': prompt_for_no_search}
                    ]
                    final_response = self.get_ollama_response(messages=messages_for_fallback)
                else:
                    self.progress.emit("Validating search results...")
                    self._narrate_step(f"I've got {len(scraped_content)} potential sources. Now I need to check if they're actually relevant.")
                    
                    passed_content, failure_reasons = self._validate_scraped_content_batch(scraped_content)
                    
                    if passed_content:
                        self._narrate_step(f"Validation complete. {len(passed_content)} source(s) look promising, so I'll extract the key details now.")
                        structured_data = self._structure_scraped_data_batch(self.prompt, passed_content)
                        self.progress.emit("Synthesizing validated response...")
                        self._narrate_step("With the relevant information extracted and structured, I'm ready to compose the final answer.")
                        
                        passed_sources = self._filter_sources_by_passed_content(sources_from_search, passed_content)
                        sources_used_for_synthesis.extend(passed_sources)
                        
                        synthesis_prompt = f"""<task>
                        <user_query>{self.prompt}</user_query>
                        <instructions>
                        You MUST use the provided structured data summary to construct a direct and complete answer to the `user_query` above. Synthesize the information from all sources into a cohesive response.
                        </instructions>
                        </task>
                        <data>
                        {structured_data}
                        </data>
                        """
                        
                        messages_for_synthesis = [synthesis_system_message] + sanitized_history + [
                            current_user_message,
                            {'role': 'assistant', 'content': initial_model_response},
                            {'role': 'user', 'content': synthesis_prompt}
                        ]
                        synthesis_response_1 = self.get_ollama_response(messages=messages_for_synthesis)

                        additional_query = self.extract_additional_search(synthesis_response_1)
                        if additional_query:
                            self._log_step(f"Model requested additional search for: '{additional_query}'")
                            self.progress.emit("Performing additional search requested by model...")
                            self._narrate_step("The initial results weren't quite enough. I'm performing a follow-up search to get more specific details.")
                            
                            # Follow-up search still uses the original search_type for context
                            additional_scraped_content, sources_from_add_search = self.execute_search_plan([(additional_query, None)], search_type)

                            if additional_scraped_content:
                                self.progress.emit("Validating additional search results...")
                                passed_additional_content, _ = self._validate_scraped_content_batch(additional_scraped_content)

                                if passed_additional_content:
                                    self.log_message.emit("Validator: Additional search content passed.", "INFO")
                                    
                                    combined_raw_data = passed_content + passed_additional_content
                                    final_structured_data = self._structure_scraped_data_batch(self.prompt, combined_raw_data)
                                    self.progress.emit("Synthesizing final response with all data...")
                                    
                                    passed_additional_sources = self._filter_sources_by_passed_content(sources_from_add_search, passed_additional_content)
                                    sources_used_for_synthesis.extend(passed_additional_sources)
                                    
                                    final_synthesis_prompt = f"""<task>
                                    <user_query>{self.prompt}</user_query>
                                    <instructions>
                                    You MUST use the provided COMBINED structured data summary to construct a final, direct, and complete answer to the `user_query` above. It is critical to synthesize information from ALL provided sources into a single, cohesive response.
                                    </instructions>
                                    </task>
                                    <data>
                                    {final_structured_data}
                                    </data>
                                    """
                                    messages_for_final_synthesis = [synthesis_system_message] + sanitized_history + [
                                        current_user_message,
                                        {'role': 'assistant', 'content': initial_model_response},
                                        {'role': 'assistant', 'content': synthesis_response_1},
                                        {'role': 'user', 'content': final_synthesis_prompt}
                                    ]
                                    final_response = self.get_ollama_response(messages=messages_for_final_synthesis)
                                else:
                                    self.log_message.emit("Validator: Additional search content FAILED. Using initial results only.", "WARN")
                                    fallback_prompt = f"""<instructions>Your additional search for '{additional_query}' failed validation. Answer the user's original query using ONLY the initial structured data summary provided below.</instructions>
                                    INITIAL STRUCTURED DATA SUMMARY:{structured_data}"""
                                    
                                    messages_for_fallback = [synthesis_system_message] + sanitized_history + [current_user_message, {'role': 'assistant', 'content': synthesis_response_1}, {'role': 'user', 'content': fallback_prompt}]
                                    final_response = self.get_ollama_response(messages=messages_for_fallback)
                            else:
                                self.log_message.emit("Additional search returned no content. Using initial results only.", "WARN")
                                fallback_prompt = f"""<instructions>Your additional search for '{additional_query}' failed to find anything. Answer the user's original query using ONLY the initial structured data summary provided below.</instructions>
                                INITIAL STRUCTURED DATA SUMMARY:{structured_data}"""
                                messages_for_fallback = [synthesis_system_message] + sanitized_history + [current_user_message, {'role': 'assistant', 'content': synthesis_response_1}, {'role': 'user', 'content': fallback_prompt}]
                                final_response = self.get_ollama_response(messages=messages_for_fallback)
                        else:
                            final_response = synthesis_response_1
                    else: 
                        combined_failure_reasons = "; ".join(failure_reasons)
                        self.log_message.emit(f"All sources FAILED validation. Reasons: {combined_failure_reasons}", "WARN")
                        self.progress.emit("Content failed validation, attempting intelligent refinement...")
                        self._narrate_step("None of the initial results were good enough. I need to rethink my search strategy and try again with a better query.")
                        
                        failed_query = search_requests[0][0]
                        refined_plan_queries = self._get_refined_search_plan(failed_query, combined_failure_reasons)
                        
                        refined_content_found = False
                        if refined_plan_queries:
                            for i, refined_search in enumerate(refined_plan_queries):
                                self._log_step(f"Refined Search Attempt {i+1}/{len(refined_plan_queries)}: '{refined_search[0]}'")
                                # Refined search uses original search_type for context
                                refined_content, sources_from_refined = self.execute_search_plan([refined_search], search_type)
                                
                                if refined_content:
                                    passed_refined_content, _ = self._validate_scraped_content_batch(refined_content)
                                    if passed_refined_content:
                                        self.log_message.emit("Validator: Refined search content PASSED.", "INFO")
                                        
                                        refined_structured_data = self._structure_scraped_data_batch(self.prompt, passed_refined_content)
                                        self.progress.emit("Synthesizing refined response...")
                                        
                                        passed_refined_sources = self._filter_sources_by_passed_content(sources_from_refined, passed_refined_content)
                                        sources_used_for_synthesis.extend(passed_refined_sources)
                                        
                                        refined_synthesis_prompt = f"""<task>
                                        <user_query>{self.prompt}</user_query>
                                        <instructions>
                                        The first search failed, but a refined search plan yielded better results. You MUST use this new structured data from the REFINED search to construct a direct and complete answer.
                                        </instructions>
                                        </task>
                                        <data>
                                        {refined_structured_data}
                                        </data>
                                        """
                                        
                                        messages_for_refined_synthesis = [synthesis_system_message] + sanitized_history + [
                                            current_user_message,
                                            {'role': 'assistant', 'content': initial_model_response},
                                            {'role': 'user', 'content': refined_synthesis_prompt}
                                        ]
                                        final_response = self.get_ollama_response(messages=messages_for_refined_synthesis)
                                        refined_content_found = True
                                        break 
                                    else:
                                        self.log_message.emit(f"Validator: Refined attempt {i+1} also FAILED validation.", "WARN")
                                else:
                                     self.log_message.emit(f"Refined attempt {i+1} yielded no content.", "WARN")
                        
                        if not refined_content_found:
                            self.log_message.emit("All primary and refined search attempts failed.", "ERROR")
                            self._narrate_step("My search attempts, even the refined ones, have failed to find good information. I'll have to inform the user and use my own knowledge.")
                            prompt_for_failed_search = "Both the primary and refined web searches failed to return useful content. Please inform the user that you couldn't find relevant information online and answer their last question using only your existing knowledge."
                            
                            messages_for_final_fallback = [synthesis_system_message] + sanitized_history + [
                                current_user_message,
                                {'role': 'assistant', 'content': initial_model_response},
                                {'role': 'user', 'content': prompt_for_failed_search}
                            ]
                            final_response = self.get_ollama_response(messages=messages_for_final_fallback)
            else:
                self.progress.emit("Responding with existing knowledge...")
                self._log_step("Model determined no search needed. Using existing knowledge.")
                self._narrate_step("A web search isn't necessary for this query. I'll generate a response from my internal knowledge base.")
                final_response = initial_model_response

            final_response_with_sources = self._attach_sources_to_response(final_response, sources_used_for_synthesis)

            if sources_used_for_synthesis and final_response.strip():
                summary_for_memory = self._summarize_for_memory(self.prompt, final_response_with_sources)
            else:
                summary_for_memory = re.sub(r'<think>.*?</think>', '', final_response, flags=re.DOTALL).strip()
                summary_for_memory = re.sub(r'<sources>.*?</sources>', '', summary_for_memory, flags=re.DOTALL).strip()
                if not summary_for_memory:
                    summary_for_memory = f"Could not find a relevant answer for the query: '{self.prompt}'"
                self.log_message.emit("Using direct response as memory (no summary needed).", "INFO")

            total_duration = datetime.now() - self.start_time
            self.log_message.emit(f"Request Completed. Total time: {self._format_duration(total_duration)}", "STEP")
            self._narrate_step("The final answer has been assembled and sent. My work here is done.")
            
            self.finished.emit(final_response_with_sources, summary_for_memory)

        except Exception as e:
            import traceback
            error_str = f"An error occurred: {e}\n{traceback.format_exc()}"
            self.log_message.emit(error_str, "ERROR")
            self.error.emit(str(e))

    # --- MODIFICATION START ---
    # Method signature updated to accept search_type
    def execute_search_plan(self, search_requests: List[Tuple[str, str]], search_type: str) -> Tuple[List[Tuple[str, str]], List[Dict]]:
        """Execute search plan and return a list of (content, query) tuples and a list of source dicts."""
        all_scraped_content_with_query = []
        all_sources = []
        
        for query, domain in search_requests:
            self.progress.emit(f"Searching for '{query}'...")
            self.log_message.emit(f"Executing search: '{query}'" + (f" on '{domain}'" if domain else ""), "INFO")
            
            # Pass search_type to the next function in the pipeline
            content_list, success_count, source_quality, sources = self.perform_single_search_and_scrape(query, search_type, domain)
            
            if success_count == 0 and domain:
                self.log_message.emit(f"Domain-specific search failed. Attempting broader search.", "WARN")
                self.progress.emit(f"Broadening search scope...")
                # Pass search_type on fallback as well
                content_list, success_count, source_quality, sources = self.perform_single_search_and_scrape(query, search_type, domain=None)
                self.log_message.emit(f"Fallback completed: {success_count} sources, quality: {source_quality}", "INFO")
            elif success_count > 0:
                self.log_message.emit(f"Search successful: {success_count} sources, quality: {source_quality}", "INFO")
            
            if content_list:
                for content in content_list:
                    all_scraped_content_with_query.append((content, query))
                all_sources.extend(sources)
                
        return all_scraped_content_with_query, all_sources
    # --- MODIFICATION END ---
    
    # --- MODIFICATION START ---
    # Method signature updated to accept search_type
    def perform_single_search_and_scrape(self, query: str, search_type: str, domain: str = None) -> Tuple[List[str], int, str, List[Dict]]:
        """Performs a search and returns a list of content strings, count, quality, and a list of source dicts."""
        try:
            current_year = str(datetime.now().year)
            # Smarter query augmentation: only add year for specific search types, and if no year is present.
            if search_type in ['news', 'tech', 'financial'] and not re.search(r'\b(19[89]\d|20\d{2})\b', query):
                modified_query = f"{query} {current_year}"
                self.log_message.emit(f"Appended current year to '{search_type.upper()}' query for relevance.", "INFO")
            else:
                modified_query = query

            search_q = f"{modified_query} site:{domain}" if domain else modified_query
            self.log_message.emit(f"Searching with DDGS: '{search_q}'", "INFO")
            
            with DDGS() as ddgs:
                search_results = [r for r in ddgs.text(search_q, max_results=self.SCRAPE_TOP_N_RESULTS)]
            
            if not search_results:
                self.log_message.emit(f"No results found for: '{search_q}'", "WARN")
                return [], 0, "none", []

            # Pass the search_type to the ranking function
            ranked_urls = self.rank_urls_by_quality(search_results, query, search_type)
            
            if not ranked_urls:
                self.log_message.emit("No quality URLs found after ranking", "WARN")
                return [], 0, "poor", []

            urls_to_scrape = ranked_urls[:self.MAX_SOURCES_TO_SCRAPE]
            self.log_message.emit(f"Selected {len(urls_to_scrape)} top sources from {len(ranked_urls)} candidates.", "INFO")

            scraped_results_content = []
            scraped_sources_list = []
            success_count = 0
            total_content_length = 0
            
            for i, (url, score) in enumerate(urls_to_scrape):
                self.progress.emit(f"Extracting from source {i+1}/{len(urls_to_scrape)}...")
                self.log_message.emit(f"Scraping '{url}' (Rank Score: {score:.2f})", "INFO")
                scraped_data, success, content_length, source_info = self.scrape_with_enhanced_extraction(url)
                
                if success and content_length > 200:
                    scraped_results_content.append(scraped_data)
                    scraped_sources_list.append(source_info) 
                    success_count += 1
                    total_content_length += content_length
            
            self.log_message.emit(f"Extraction complete. Got content from {success_count}/{len(urls_to_scrape)} sources.", "INFO")

            quality = "poor"
            if success_count >= 2 and total_content_length > 1000: quality = "excellent"
            elif success_count >= 1 and total_content_length > 600: quality = "good"
            elif success_count >= 1 and total_content_length > 300: quality = "fair"

            self.log_message.emit(f"Search Quality: {quality} ({total_content_length} chars from {success_count} sources).", "INFO")
            return scraped_results_content, success_count, quality, scraped_sources_list
            
        except Exception as e:
            self.log_message.emit(f"Search failed for '{query}': {e}", "ERROR")
            return [], 0, "error", []

    def rank_urls_by_quality(self, search_results: List[Dict], query: str, search_type: str) -> List[Tuple[str, float]]:
        """CRITICAL: Intelligent URL ranking driven by the IntentAgent's classified search_type."""
        
        # Domain lists remain, as they are the targets for the classification.
        financial_domains = ['finance.yahoo.com', 'marketwatch.com', 'bloomberg.com', 'reuters.com', 'cnbc.com', 'wsj.com', 'investing.com', 'morningstar.com']
        news_domains = ['reuters.com', 'apnews.com', 'bbc.com', 'cnn.com', 'npr.org', 'theguardian.com', 'nytimes.com', 'wsj.com']
        tech_domains = ['techcrunch.com', 'arstechnica.com', 'theverge.com', 'wired.com', 'engadget.com', 'zdnet.com', 'cnet.com']
        weather_domains = ['weather.com', 'accuweather.com', 'weather.gov', 'wunderground.com']
        historical_domains = ['wikipedia.org', 'britannica.com', 'history.com', 'scholar.google.com', 'jstor.org', 'nationalgeographic.com', 'si.edu', '.edu', 'plato.stanford.edu']
        
        query_lower = query.lower()
        
        ranked_urls = []
        for result in search_results:
            url, title, snippet = result.get('href'), result.get('title', '').lower(), result.get('body', '').lower()
            if not url: continue
            try:
                domain = url.split('/')[2].lower()
            except (IndexError, AttributeError):
                continue
            
            score = 1.0
            

            if search_type == "historical":
                if any(pd in domain for pd in historical_domains): score += 15.0
                if any(word in title + snippet for word in ['today', 'latest', 'breaking news', 'live']): score -= 5.0 # Penalize recency
            elif search_type == "financial":
                if any(pd in domain for pd in financial_domains): score += 10.0
                if any(word in title + snippet for word in ['today', 'latest', 'current', str(datetime.now().year)]): score += 3.0 # Reward recency
            elif search_type == "news":
                if any(pd in domain for pd in news_domains): score += 10.0
                if any(word in title + snippet for word in ['today', 'latest', 'current', str(datetime.now().year)]): score += 3.0 # Reward recency
            elif search_type == "tech":
                if any(pd in domain for pd in tech_domains): score += 10.0
                if any(word in title + snippet for word in ['today', 'latest', 'current', str(datetime.now().year)]): score += 3.0 # Reward recency
            elif search_type == "weather":
                if any(pd in domain for pd in weather_domains): score += 10.0
                if any(word in title + snippet for word in ['today', 'latest', 'current', str(datetime.now().year)]): score += 3.0 # Reward recency
            # 'general' search_type will not get a specific domain bonus but will still benefit from general rules.

            # General scoring rules that apply to all types.
            title_matches = sum(1 for word in query_lower.split() if word in title)
            score += title_matches * 2.0
            
            if any(lq in domain for lq in ['pinterest.com', 'quora.com', 'answers.com', 'wikihow.com', 'ehow.com', 'forum', 'blog']): score -= 5.0
            if url.startswith('https://'): score += 0.5
            
            ranked_urls.append((url, score))
        
        ranked_urls.sort(key=lambda x: x[1], reverse=True)
        return ranked_urls

    def scrape_with_enhanced_extraction(self, url: str) -> Tuple[str, bool, int, Dict]:
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            html_content = response.text
        except requests.RequestException:
            return f"<result url='{url}' error='Failed to download'></result>", False, 0, {}

        metadata = trafilatura.extract_metadata(html_content)
        title = metadata.title if metadata and metadata.title else "Unknown Title"
        date = metadata.date if metadata and metadata.date else "N/A"
        
        main_content = trafilatura.extract(html_content, include_comments=False, include_tables=True, favor_precision=True)

        if not (main_content and len(main_content) > 200):
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style", "nav", "footer", "header"]): script.decompose()
            text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True)).strip()
            if text and len(text) > 200: main_content = text
            else: return f"<result url='{url}' title='{title}' date='{date}' error='Insufficient content'></result>", False, 0, {}

        content_length = len(main_content)
        if content_length < 300: return f"<result url='{url}' title='{title}' date='{date}' error='Content below quality threshold'></result>", False, 0, {}
        if content_length > 12000: main_content = main_content[:12000] + "..."
        
        formatted_string = f"""<result url="{url}" date="{date}"><title>{title}</title><content>{main_content}</content></result>"""
        source_info = {'url': url, 'title': title, 'date': date}
        return formatted_string, True, len(main_content), source_info

    def extract_search_requests(self, text: str) -> List[Tuple[str, str]]:
        pattern = r'<search_request>\s*<query>(.*?)</query>(?:\s*<domain>(.*?)</domain>)?\s*</search_request>'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        
        valid_requests = []
        for query, domain in matches:
            query, domain = query.strip(), domain.strip() if domain else None
            if len(query) < 3 or any(existing_query.lower() == query.lower() for existing_query, _ in valid_requests): continue
            valid_requests.append((query, domain))
        return valid_requests

    def extract_additional_search(self, text: str) -> str:
        pattern = r'<additional_search>\s*<query>(.*?)</query>\s*</additional_search>'
        match = re.search(pattern, text.strip(), re.DOTALL | re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            if text.strip() == match.group(0).strip() and len(query) > 3: return query
        return ""

    def get_ollama_response(self, messages: list) -> str:
        model_name = 'qwen3:14b'
        max_retries = 2
        current_messages = list(messages)
        for attempt in range(max_retries + 1):
            system_prompt = current_messages[0]['content']
            history_messages = current_messages[1:-1]
            final_task = current_messages[-1]['content']

            log_payload = "--- PAYLOAD BEING SENT TO MODEL ---\n"
            if history_messages:
                for msg in history_messages:
                    role = msg.get('role', 'N/A').upper()
                    content = msg.get('content', '').strip().replace('\n', '\\n')
                    log_payload += f"  - [{role}]: {content[:120] + '...' if len(content) > 120 else content}\n"
            else:
                log_payload += "  (None)\n"
            
            self.log_message.emit(f"Data was successfully compiled and sent to the model (Attempt {attempt + 1}/{max_retries + 1})...", "INFO")
            try:
                response = ollama.chat(model=model_name, messages=current_messages, stream=False)
                response_content = response['message']['content']
                
                if '<think>' in response_content and '</think>' in response_content:
                    self.log_message.emit(f"Agents response received and validated for <think> block.", "INFO")
                    return response_content
                else:
                    self.log_message.emit(f"Validation FAILED: <think> block missing in response (Attempt {attempt + 1}).", "WARN")
                    if attempt < max_retries:
                        correction_prompt = {
                            'role': 'user',
                            'content': "Your previous response was invalid because it did not contain the mandatory `<think>...</think>` block explaining your reasoning. You MUST include this block in your response. Please correct this and reply again."
                        }
                        current_messages.append({'role': 'assistant', 'content': response_content}) 
                        current_messages.append(correction_prompt)
                        self.log_message.emit("Retrying with correction prompt...", "STEP")
                    else:
                        self.log_message.emit(f"Max retries reached. Forcing a <think> block into the response.", "ERROR")
                        return f"<think>GENERATION FAILURE: Model failed to produce a valid thinking process after {max_retries + 1} attempts.</think>\n{response_content}"

            except Exception as e:
                self.log_message.emit(f"{model_name} request failed on attempt {attempt + 1}: {e}", "ERROR")
                if attempt == max_retries:
                    raise
        
        return "<think>An unexpected error occurred in the generation loop.</think>Error: Could not get a valid response from the model."

    def _attach_sources_to_response(self, response_text: str, sources: List[Dict]) -> str:
        if not sources:
            return response_text
        clean_response = re.sub(r'<sources>.*?</sources>', '', response_text, flags=re.DOTALL).strip()
        sources_lines = [f'<source url="{s["url"]}" date="{s["date"]}">{s["title"]}</source>' for s in sources]
        sources_block = "<sources>\n" + "\n".join(sources_lines) + "\n</sources>"
        return f"{clean_response}\n\n{sources_block}"

class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent; self.pressing = False; self.setObjectName("customTitleBar")
        layout = QHBoxLayout(self); layout.setContentsMargins(10, 0, 0, 0); layout.setSpacing(10)
        self.title = QLabel("Chorus.Ai"); self.title.setObjectName("windowTitle"); layout.addWidget(self.title); layout.addStretch()
        btn_size = 30
        self.minimize_button = QPushButton("—"); self.minimize_button.setObjectName("windowButton"); self.minimize_button.setFixedSize(btn_size, btn_size); self.minimize_button.clicked.connect(self.parent.showMinimized)
        self.maximize_button = QPushButton("□"); self.maximize_button.setObjectName("windowButton"); self.maximize_button.setFixedSize(btn_size, btn_size); self.maximize_button.clicked.connect(self.toggle_maximize)
        self.close_button = QPushButton("✕"); self.close_button.setObjectName("closeButton"); self.close_button.setFixedSize(btn_size, btn_size); self.close_button.clicked.connect(self.parent.close)
        layout.addWidget(self.minimize_button); layout.addWidget(self.maximize_button); layout.addWidget(self.close_button)
    def toggle_maximize(self): self.parent.showNormal() if self.parent.isMaximized() else self.parent.showMaximized()
    def mousePressEvent(self, event): self.startPos = event.globalPosition().toPoint(); self.pressing = True
    def mouseMoveEvent(self, event):
        if self.pressing: self.endPos = event.globalPosition().toPoint(); self.movement = self.endPos - self.startPos; self.parent.move(self.parent.pos() + self.movement); self.startPos = self.endPos
    def mouseReleaseEvent(self, event): self.pressing = False

class MessageBubble(QWidget):
    def __init__(self, main_text, citations=None, thinking_text=None):
        super().__init__()
        self.is_citations_expanded = False
        self.is_thinking_expanded = False
        self.citations_animation = None
        self.thinking_animation = None
        self.citations_container = None
        self.thinking_container = None
        self.container = QFrame()
        self.container.setObjectName("messageBubbleContainer")
        self.container.setMinimumWidth(450)
        self.container.setMaximumWidth(450)
        self.setProperty("isUser", False)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(8)
        self.message_label = QLabel(main_text)
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName("messageText")
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_label.setOpenExternalLinks(True)
        container_layout.addWidget(self.message_label)

        if thinking_text:
            self.toggle_thinking_button = QPushButton("Thinking Process")
            self.toggle_thinking_button.setObjectName("toggleDetailButton")
            self.toggle_thinking_button.setCheckable(True)
            self.toggle_thinking_button.clicked.connect(self.toggle_thinking)
            container_layout.addWidget(self.toggle_thinking_button, 0, Qt.AlignLeft)
            self.thinking_container = QFrame()
            self.thinking_container.setObjectName("thinkingContainer")
            self.thinking_container.setVisible(False)
            thinking_layout = QVBoxLayout(self.thinking_container)
            thinking_layout.setContentsMargins(8, 8, 8, 8)
            thinking_label = QLabel(thinking_text)
            thinking_label.setWordWrap(True)
            thinking_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            thinking_label.setObjectName("thinkingLabel")
            thinking_layout.addWidget(thinking_label)
            container_layout.addWidget(self.thinking_container)
            self.thinking_animation = QPropertyAnimation(self.thinking_container, b"maximumHeight")
            self.thinking_animation.setDuration(250)
            self.thinking_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.thinking_animation.finished.connect(self._on_thinking_animation_finished)
        
        if citations:
            source_count = len(citations)
            button_text = f"{source_count} Source{'s' if source_count != 1 else ''}"
            self.toggle_citations_button = QPushButton(button_text)
            self.toggle_citations_button.setObjectName("toggleDetailButton")
            self.toggle_citations_button.setCheckable(True)
            self.toggle_citations_button.clicked.connect(self.toggle_citations)
            container_layout.addWidget(self.toggle_citations_button, 0, Qt.AlignLeft)
            self.citations_container = QFrame()
            self.citations_container.setObjectName("citationsContainer")
            self.citations_container.setVisible(False)
            citations_layout = QVBoxLayout(self.citations_container)
            citations_layout.setContentsMargins(8, 8, 8, 8)
            citations_layout.setSpacing(6)
            for i, citation in enumerate(citations, 1):
                date_str = f" • {citation['date']}" if citation['date'] != "N/A" else ""
                citation_html = f"""
                <div style='margin-bottom: 4px;'>
                    <strong style='color: #4EC9B0;'>[{i}]</strong> 
                    <a href='{citation['url']}' style='color: #4EC9B0; text-decoration: none;'>{citation['title']}</a>
                    <span style='color: #888; font-size: 11px;'>{date_str}</span>
                </div>
                """
                citation_label = QLabel(citation_html)
                citation_label.setOpenExternalLinks(True)
                citation_label.setObjectName("citationLabel")
                citation_label.setWordWrap(True)
                citations_layout.addWidget(citation_label)
            container_layout.addWidget(self.citations_container)
            self.citations_animation = QPropertyAnimation(self.citations_container, b"maximumHeight")
            self.citations_animation.setDuration(250)
            self.citations_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.citations_animation.finished.connect(self._on_citations_animation_finished)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def _on_citations_animation_finished(self):
        if not self.is_citations_expanded:
            self.citations_container.setVisible(False)
    def _on_thinking_animation_finished(self):
        if not self.is_thinking_expanded:
            self.thinking_container.setVisible(False)

    def toggle_citations(self):
        if self.citations_animation: self.citations_animation.stop()
        self.is_citations_expanded = not self.is_citations_expanded
        if self.is_citations_expanded:
            self.citations_container.setVisible(True)
            self.citations_container.setMaximumHeight(16777215)
            self.citations_animation.setStartValue(0)
            self.citations_animation.setEndValue(self.citations_container.sizeHint().height())
        else:
            self.citations_animation.setStartValue(self.citations_container.height())
            self.citations_animation.setEndValue(0)
        self.citations_animation.start()

    def toggle_thinking(self):
        if self.thinking_animation: self.thinking_animation.stop()
        self.is_thinking_expanded = not self.is_thinking_expanded
        if self.is_thinking_expanded:
            self.toggle_thinking_button.setText("Hide")
            self.thinking_container.setVisible(True)
            self.thinking_container.setMaximumHeight(16777215)
            self.thinking_animation.setStartValue(0)
            self.thinking_animation.setEndValue(self.thinking_container.sizeHint().height())
        else:
            self.toggle_thinking_button.setText("Thinking Process")
            self.thinking_animation.setStartValue(self.thinking_container.height())
            self.thinking_animation.setEndValue(0)
        self.thinking_animation.start()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.memory = SemanticMemory(log_callback=lambda msg, level="MEMORY": self.update_log(msg, level))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.current_prompt = None
        
        self.worker_timeout_timer = QTimer(self)
        self.worker_timeout_timer.setSingleShot(True)
        self.worker_timeout_timer.setInterval(30 * 60 * 1000) # 30 minutes
        self.worker_timeout_timer.timeout.connect(self.handle_worker_timeout)
        
        self.query_stopwatch_timer = QTimer(self)
        self.query_stopwatch_timer.setInterval(1000) # 1 second tick
        self.query_stopwatch_timer.timeout.connect(self.update_stopwatch)
        self.query_start_time = None
        
        self.init_ui()
        
    def init_ui(self):
        self.setGeometry(100, 100, 1100, 750)
        self.setMinimumSize(800, 600)
        main_container = QFrame(); main_container.setObjectName("mainContainer")
        container_layout = QVBoxLayout(main_container); container_layout.setContentsMargins(1,1,1,1); container_layout.setSpacing(0)
        self.title_bar = CustomTitleBar(self)
        content_splitter = QSplitter(Qt.Horizontal)
        chat_panel = QWidget(); chat_panel_layout = QVBoxLayout(chat_panel); chat_panel_layout.setContentsMargins(10,10,5,10)
        self.chat_scroll = QScrollArea(); self.chat_scroll.setWidgetResizable(True); self.chat_scroll.setObjectName("chatScrollArea")
        self.chat_container = QWidget(); self.chat_layout = QVBoxLayout(self.chat_container); self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_container); chat_panel_layout.addWidget(self.chat_scroll)
        log_panel = QWidget(); log_panel_layout = QVBoxLayout(log_panel); log_panel_layout.setContentsMargins(5,10,10,10)
        log_title = QLabel("Action Log"); log_title.setObjectName("panelTitle")
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True); self.log_display.setObjectName("logDisplay")
        log_panel_layout.addWidget(log_title); log_panel_layout.addWidget(self.log_display)
        content_splitter.addWidget(chat_panel); content_splitter.addWidget(log_panel); content_splitter.setSizes([700, 300])
        footer_frame = QFrame(); footer_frame.setObjectName("footerFrame")
        footer_layout = QVBoxLayout(footer_frame); footer_layout.setContentsMargins(10,10,10,5)
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit(); self.input_field.setObjectName("inputField"); self.input_field.setPlaceholderText("Enter your query..."); self.input_field.setFixedHeight(50)
        self.send_button = QPushButton("➤"); self.send_button.setObjectName("sendButton"); self.send_button.setFixedSize(50, 50); self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_field); input_layout.addWidget(self.send_button)
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready"); self.status_label.setObjectName("statusLabel")
        
        self.timer_label = QLabel(""); self.timer_label.setObjectName("timerLabel"); self.timer_label.setVisible(False)
        
        self.clear_button = QPushButton("New Chat"); self.clear_button.setObjectName("clearButton"); self.clear_button.clicked.connect(self.clear_chat_session)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.timer_label)
        status_layout.addStretch()
        status_layout.addWidget(self.clear_button)
        
        footer_layout.addLayout(input_layout); footer_layout.addLayout(status_layout)
        container_layout.addWidget(self.title_bar, stretch=0); container_layout.addWidget(content_splitter, stretch=1); container_layout.addWidget(footer_frame, stretch=0)
        self.setCentralWidget(main_container)
        self.setStyleSheet(self.get_stylesheet())

    def get_stylesheet(self):
        return """
            #mainContainer { background-color: #1E1E1E; border: 1px solid #3C3C3C; border-radius: 8px; }
            QMainWindow { background-color: transparent; }
            #customTitleBar { background-color: #2D2D2D; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            #windowTitle { color: #CCCCCC; font-size: 14px; font-weight: bold; }
            #windowButton { background-color: transparent; color: #CCCCCC; border: none; font-size: 16px; font-weight: bold; }
            #windowButton:hover { background-color: #4A4A4A; } #closeButton:hover { background-color: #E81123; color: white; }
            QSplitter::handle { background-color: #2D2D2D; width: 3px; } QSplitter::handle:hover { background-color: #007ACC; }
            #panelTitle { color: #4EC9B0; font-size: 13px; font-weight: bold; margin-bottom: 5px; padding-left: 2px; }
            #chatScrollArea { border: none; background: transparent; }
            #logDisplay { border: 1px solid #333333; border-radius: 4px; background-color: #252526; color: #D4D4D4; font-family: Consolas, Courier New, monospace; font-size: 12px; }
            QFrame#messageBubbleContainer { background-color: #2D2D2D; border: 1px solid #3C3C3C; border-radius: 8px; max-width: 650px; }
            QFrame#messageBubbleContainer[isUser="true"] { background-color: #004C8A; border-color: #007ACC; }
            QLabel#messageText { background-color: transparent; border: none; padding: 0; color: #D4D4D4; font-size: 14px; }
            #toggleDetailButton { background-color: #3C3C3C; color: #CCCCCC; border: none; border-radius: 6px; font-size: 12px; padding: 6px 12px; margin-top: 8px; font-weight: 500; }
            #toggleDetailButton:hover { background-color: #4A4A4A; color: #E0E0E0; } 
            #toggleDetailButton:checked { background-color: #555555; color: white; }
            #thinkingContainer, #citationsContainer { background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; margin-top: 4px; }
            #thinkingLabel { font-family: Consolas, 'Courier New', monospace; font-size: 12px; color: #B3B3B3; background-color: transparent; padding: 8px; }
            #citationLabel { font-size: 12px; padding: 4px 6px; line-height: 1.4; background-color: transparent; border: none; } 
            #citationLabel a { color: #4EC9B0; text-decoration: none; } 
            #citationLabel a:hover { text-decoration: underline; color: #6BD4BC; }
            #footerFrame { background-color: #2D2D2D; border-top: 1px solid #3C3C3C; }
            #inputField { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 4px; padding: 8px; color: #F1F1F1; font-size: 14px; }
            #inputField:focus { border: 1px solid #007ACC; }
            #sendButton { background-color: #007ACC; color: white; border: none; border-radius: 25px; font-size: 20px; }
            #sendButton:hover { background-color: #1F9CFD; } 
            #sendButton:disabled { background-color: #4A4A4A; }
            #statusLabel { color: #888888; font-size: 12px; }
            #timerLabel { color: #007ACC; font-size: 12px; font-weight: bold; margin-left: 10px; }
            #clearButton { background-color: #3C3C3C; color: #CCCCCC; border: 1px solid #555; padding: 4px 10px; border-radius: 4px; font-size: 12px; }
            #clearButton:hover { background-color: #4A4A4A; color: white; border-color: #666; }
            QScrollBar:vertical { border: none; background: #252526; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #4A4A4A; border-radius: 5px; min-height: 25px; } 
            QScrollBar::handle:vertical:hover { background: #6A6A6A; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #252526; }
            QScrollBar:horizontal { border: none; background: #252526; height: 10px; margin: 0; }
            QScrollBar::handle:horizontal { background: #4A4A4A; border-radius: 5px; min-width: 25px; }
            QScrollBar::handle:horizontal:hover { background: #6A6A6A; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #252526; }
        """

    def clear_chat_session(self):
        self.memory.clear()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.update_log("--- New Chat Session Started ---", "STEP")
        self.status_label.setText("Ready")
        self.input_field.setFocus()

    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text: return
            
        self.current_prompt = text
            
        self.add_message_to_ui(text, is_user=True)
        self.input_field.clear()
        self.set_ui_enabled(False)
        self.update_log(f"USER QUERY: {text}", "USER")
        self.update_log("MODE: Default Search", "INFO")

        self.worker_timeout_timer.start()
        self.query_start_time = datetime.now()
        self.update_stopwatch()
        self.timer_label.setVisible(True)
        self.query_stopwatch_timer.start()

        self.worker = SearchWorker(text, self.memory)
        self.worker.log_message.connect(self.update_log)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.progress.connect(self.update_status)
        self.worker.start()

    def add_message_to_ui(self, text: str, is_user: bool):
        if is_user:
            bubble = MessageBubble(text)
            bubble.container.setProperty("isUser", True)
        else:
            working_text = text
            thinking_text = None
            citations = None
            think_match = re.search(r'<think>(.*?)</think>', working_text, re.DOTALL)
            if think_match:
                thinking_text = think_match.group(1).strip()
                working_text = re.sub(r'<think>.*?</think>', '', working_text, flags=re.DOTALL).strip()
            sources_match = re.search(r'<sources>(.*?)</sources>', working_text, re.DOTALL)
            if sources_match:
                sources_block = sources_match.group(1)
                working_text = re.sub(r'<sources>.*?</sources>', '', working_text, flags=re.DOTALL).strip()
                citations_found = re.findall(r'<source url="([^"]+)" date="([^"]*)">(.*?)</source>', sources_block)
                if citations_found:
                    citations = []
                    for url, date, title in citations_found:
                        clean_title = title.strip() or "Unknown Title"
                        if len(clean_title) > 80: clean_title = clean_title[:77] + "..."
                        citations.append({'url': url, 'date': date or "N/A", 'title': clean_title})
            main_content_html = markdown2.markdown(working_text, extras=["fenced-code-blocks", "tables", "cuddled-lists"])
            bubble = MessageBubble(main_content_html, citations=citations, thinking_text=thinking_text)
            bubble.container.setProperty("isUser", False)
            bubble.container.setMinimumWidth(650)
            bubble.container.setMaximumWidth(650)
        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(5, 5, 5, 5)
        row_layout.setSpacing(0)
        if is_user: 
            row_layout.addStretch()
            row_layout.addWidget(bubble, 0, Qt.AlignTop)
        else: 
            row_layout.addWidget(bubble, 0, Qt.AlignTop)
            row_layout.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row_container)
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()))

    def handle_response(self, response: str, summary_for_memory: str):
        self.worker_timeout_timer.stop()
        self.query_stopwatch_timer.stop()
        self.timer_label.setVisible(False)
        
        self.add_message_to_ui(response, is_user=False)
        
        if self.current_prompt:
            self.memory.add_message(role='user', content=self.current_prompt)
            self.memory.add_message(role='assistant', content=summary_for_memory)
            self.current_prompt = None
        
        self.set_ui_enabled(True)
        self.update_log("Response delivered to UI.", "INFO")

    def handle_error(self, error: str):
        self.worker_timeout_timer.stop()
        self.query_stopwatch_timer.stop()
        self.timer_label.setVisible(False)
        
        error_msg = f"Error: {error}"
        self.add_message_to_ui(error_msg, is_user=False)
        
        if self.current_prompt:
            self.memory.add_message(role='user', content=self.current_prompt)
            self.memory.add_message(role='assistant', content=error_msg)
            self.current_prompt = None
            
        self.set_ui_enabled(True)
        self.update_log(f"Error handled: {error}", "ERROR")

    def handle_worker_timeout(self):
        self.update_log("WORKER TIMEOUT: Process exceeded 30 minutes and was terminated.", "ERROR")
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.terminate()
        
        if not self.current_prompt:
            self.current_prompt = self.input_field.toPlainText().strip() or "Timed out query"
        
        self.handle_error("The request took too long to process and was cancelled.")

    def update_stopwatch(self):
        if self.query_start_time:
            elapsed = datetime.now() - self.query_start_time
            minutes, seconds = divmod(int(elapsed.total_seconds()), 60)
            self.timer_label.setText(f"Elapsed: {minutes:02d}:{seconds:02d}")

    def update_status(self, status: str):
        self.status_label.setText(status)

    def update_log(self, message: str, level: str = "INFO"):
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
        scrollbar = self.log_display.verticalScrollBar()
        is_dragging = scrollbar.isSliderDown()
        is_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 10)
        should_autoscroll = (not is_dragging) and is_at_bottom
        self.log_display.moveCursor(QTextCursor.End)
        style = LOG_LEVEL_STYLES.get(level, LOG_LEVEL_STYLES["INFO"])
        
        timestamp = datetime.now().strftime('%I:%M:%S %p')

        safe_message = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        content_html = (
            f'<p style="margin: 0; padding: 0; {style}">'
            f'<span style="color:#777;">{timestamp} --- </span>'
            f'{safe_message}'
            f'</p>'
        )
        spacer_html = '<div style="height: 10px; font-size: 2px;">&nbsp;</div>'
        self.log_display.insertHtml(content_html + spacer_html)
        if should_autoscroll:
            QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))

    def set_ui_enabled(self, enabled: bool):
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        if enabled:
            self.status_label.setText("Ready")
            self.input_field.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            if self.send_button.isEnabled(): self.send_message()
        else: super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
