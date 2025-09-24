# --- core_logic.py ---

import sys
import re
import requests
import ollama
import trafilatura
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# --- LIBRARIES for robust scraping ---
from ddgs import DDGS
from bs4 import BeautifulSoup

from PySide6.QtCore import QThread, Signal

# Local Imports
import config
from semantic_memory import SemanticMemory

def load_prompts_from_file(file_path: str, log_callback) -> Dict[str, str]:
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
                log_callback(f"Could not parse prompt header: {header}", "WARN")

        required_prompts = ['NARRATOR_PROMPT', 'SEARCH_INTENT_PROMPT', 'VALIDATOR_PROMPT', 'REFINER_PROMPT', 'ABSTRACTION_PROMPT', 'SYNTHESIS_PROMPT', 'MEMORY_SUMMARY_PROMPT', 'TITLE_PROMPT']
        for p_name in required_prompts:
            if p_name not in prompts:
                raise KeyError(f"Required prompt '{p_name}' not found in the instructions file.")
        
        log_callback(f"Successfully loaded {len(prompts)} system prompts from file.", "INFO")
        return prompts

    except FileNotFoundError:
        error_msg = f"CRITICAL ERROR: The system instructions file was not found at '{file_path}'. The application cannot start."
        log_callback(error_msg, "ERROR")
        print(error_msg)
        sys.exit(1)
    except (ValueError, KeyError) as e:
        error_msg = f"CRITICAL ERROR: Failed to parse system instructions file. Reason: {e}. The application cannot start."
        log_callback(error_msg, "ERROR")
        print(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"An unexpected critical error occurred while loading prompts: {e}"
        log_callback(error_msg, "ERROR")
        print(error_msg)
        sys.exit(1)

class TitleWorker(QThread):
    """A dedicated worker to generate a chat title without blocking the UI."""
    finished = Signal(str, str) # chat_id, title
    log_message = Signal(str, str)

    def __init__(self, chat_id: str, first_message: str, title_prompt: str):
        super().__init__()
        self.chat_id = chat_id
        self.first_message = first_message
        self.messages = [
            {'role': 'system', 'content': title_prompt},
            {'role': 'user', 'content': self.first_message}
        ]
    
    def run(self):
        try:
            self.log_message.emit("Calling TitleAgent to name new chat...", "AGENT_CALL")
            response = ollama.chat(
                model=config.TITLE_GENERATOR_MODEL, 
                messages=self.messages, 
                stream=False
            )
            title = response['message']['content'].strip().replace('"', '')
            if not title:
                title = self.first_message[:30] + "..."
                self.log_message.emit("TitleAgent returned empty title, using fallback.", "WARN")
            self.log_message.emit(f"New chat title generated: '{title}'", "INFO")
            self.finished.emit(self.chat_id, title)
        except Exception as e:
            self.log_message.emit(f"TitleAgent failed: {e}", "ERROR")
            fallback_title = self.first_message[:30]
            self.finished.emit(self.chat_id, fallback_title)


class SearchWorker(QThread):
    finished = Signal(str, str)
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)

    # Note: HEADERS moved to config.py

    def __init__(self, prompt: str, memory: SemanticMemory):
        super().__init__()
        self.prompt = prompt
        self.memory = memory
        self.start_time = None
        self.last_step_time = None

        self.SCRAPE_TOP_N_RESULTS = config.SCRAPE_TOP_N_RESULTS
        self.MAX_SOURCES_TO_SCRAPE = config.MAX_SOURCES_TO_SCRAPE

        self.prompts = load_prompts_from_file(config.PROMPT_FILE_PATH, self.log_message.emit)

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
            response = ollama.chat(model=config.NARRATOR_MODEL, messages=messages_for_narrator, stream=False)
            narration = response['message']['content'].strip()
            
            narration = re.sub(r'["\']', '', narration)
            if not narration.endswith(('.', '!', '?')):
                narration += '.'

            self.log_message.emit(narration, "NARRATOR")
            self.narrator_messages.append({'role': 'assistant', 'content': narration})
        except Exception as e:
            self.log_message.emit(f"Narrator agent failed: {e}", "WARN")

    def _find_url_in_query(self, query: str) -> Optional[str]:
        """Finds the first http/https URL in a given string."""
        url_pattern = r'https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
        urls_found = re.findall(url_pattern, query)
        if urls_found:
            return urls_found[0]
        return None

    def _get_search_plan(self, user_query: str) -> Tuple[List[Tuple[str, None]], str]:
        """
        Determines the search plan. Bypasses IntentAgent for direct URL requests.
        """
        # Hard bypass: If a URL is found, we assume a direct scrape is intended.
        direct_url = self._find_url_in_query(user_query)
        if direct_url:
            self.log_message.emit(f"URL detected. Bypassing IntentAgent for direct scrape of: {direct_url}", "STEP")
            return ([(direct_url, None)], "direct")

        # If no URL is found, proceed with the normal IntentAgent process.
        self.log_message.emit("No URL detected. Calling IntentAgent for a search plan...", "AGENT_CALL")
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
            
            response = ollama.chat(model=config.INTENT_MODEL, messages=messages, stream=False)
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
            response = ollama.chat(model=config.MEMORY_SUMMARY_MODEL, messages=messages, stream=False)
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
            response = ollama.chat(model=config.REFINER_MODEL, messages=messages, stream=False)
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
                response = ollama.chat(model=config.ABSTRACTION_MODEL, messages=messages, stream=False)
                structured_output = response['message']['content'].strip()
                
                match = re.search(r'<structured_data>(.*?)</structured_data>', structured_output, re.DOTALL)
                if match:
                    clean_structured_data = match.group(1).strip()
                    all_structured_summaries.append(clean_structured_data)
                    self.log_message.emit(f"Source {i+1} successfully structured.", "INFO")
                else:
                    self.log_message.emit(f"Source {i+1} response did not contain valid <structured_data> tags. Skipping.", "WARN")

            except Exception as e:
                self.log_message.emit(f"AbstractionAgent failed for source {i+1}: {e}. Skipping.", "ERROR")

        if not all_structured_summaries:
            self.log_message.emit("AbstractionAgent failed to structure any data. Falling back to raw data.", "ERROR")
            return "\n".join(raw_scraped_results)
        
        final_combined_summary = "\n\n".join(all_structured_summaries)
        self.log_message.emit(f"Abstraction complete. {len(all_structured_summaries)}/{len(raw_scraped_results)} sources successfully summarized.", "INFO")
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
                response = ollama.chat(model=config.VALIDATOR_MODEL, messages=validator_messages, stream=False)
                validator_output = response['message']['content'].strip()                

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
            
            search_requests, search_type = self._get_search_plan(self.prompt)
            
            if search_requests:
                search_basis = 'generated plan'
                if search_type == "direct":
                    search_basis = "direct URL request"
                self._log_step(f"Performing targeted search based on {search_basis}.")
                self._narrate_step(f"A search is required. I'm now executing the search plan with {len(search_requests)} topic(s).")
                
                synthesis_system_message = self.synthesis_messages[0]
                current_user_message = {'role': 'user', 'content': self.prompt}

                scraped_content, sources_from_search = self.execute_search_plan(search_requests, search_type)

                if not scraped_content:
                    if search_type == "direct":
                        url = search_requests[0][0]
                        self.log_message.emit(f"Direct URL scrape of '{url}' failed. Informing user.", "WARN")
                        self._narrate_step(f"I tried to access the website '{url}' as requested, but it didn't work. I'll let the user know.")
                        final_response = f"<think>The user requested a direct analysis of the URL '{url}'. My attempt to scrape this URL failed to produce any usable content. I must inform the user of this specific failure.</think>I'm sorry, but I was unable to access or extract any useful information from the requested website: {url}. It might be offline, protected against scraping, or not contain readable text."
                    else:
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
                    # --- MODIFICATION START ---
                    # Bypass validation for direct URL requests, as the user has specified the exact source.
                    if search_type == "direct":
                        self._log_step("Direct URL query: Bypassing validation step.")
                        # The scraped_content is a list of tuples (content, query). We just need the content.
                        passed_content = [item[0] for item in scraped_content]
                        failure_reasons = []
                    else:
                        # For general searches, perform validation as usual.
                        self.progress.emit("Validating search results...")
                        self._narrate_step(f"I've got {len(scraped_content)} potential sources. Now I need to check if they're actually relevant.")
                        passed_content, failure_reasons = self._validate_scraped_content_batch(scraped_content)
                    # --- MODIFICATION END ---
                    
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

    def execute_search_plan(self, search_requests: List[Tuple[str, str]], search_type: str) -> Tuple[List[Tuple[str, str]], List[Dict]]:
        """Execute search plan and return a list of (content, query) tuples and a list of source dicts."""
        if search_type == "direct" and search_requests:
            url = search_requests[0][0]
            self.progress.emit(f"Scraping direct URL '{url}'...")
            self.log_message.emit(f"Executing direct scrape: '{url}'", "INFO")
            
            scraped_data, success, content_length, source_info = self.scrape_with_enhanced_extraction(url)
            
            if success and content_length > 200:
                return ([(scraped_data, self.prompt)], [source_info])
            else:
                return ([], [])

        all_scraped_content_with_query = []
        all_sources = []
        
        for query, domain in search_requests:
            self.progress.emit(f"Searching for '{query}'...")
            self.log_message.emit(f"Executing search: '{query}'" + (f" on '{domain}'" if domain else ""), "INFO")
            
            content_list, success_count, source_quality, sources = self.perform_single_search_and_scrape(query, search_type, domain)
            
            if success_count == 0 and domain:
                self.log_message.emit(f"Domain-specific search failed. Attempting broader search.", "WARN")
                self.progress.emit(f"Broadening search scope...")
                content_list, success_count, source_quality, sources = self.perform_single_search_and_scrape(query, search_type, domain=None)
                self.log_message.emit(f"Fallback completed: {success_count} sources, quality: {source_quality}", "INFO")
            elif success_count > 0:
                self.log_message.emit(f"Search successful: {success_count} sources, quality: {source_quality}", "INFO")
            
            if content_list:
                for content in content_list:
                    all_scraped_content_with_query.append((content, query))
                all_sources.extend(sources)
                
        return all_scraped_content_with_query, all_sources
    
    def perform_single_search_and_scrape(self, query: str, search_type: str, domain: str = None) -> Tuple[List[str], int, str, List[Dict]]:
        """Performs a search and returns a list of content strings, count, quality, and a list of source dicts."""
        try:
            current_year = str(datetime.now().year)
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

            title_matches = sum(1 for word in query_lower.split() if word in title)
            score += title_matches * 2.0
            
            if any(lq in domain for lq in ['pinterest.com', 'quora.com', 'answers.com', 'wikihow.com', 'ehow.com', 'forum', 'blog']): score -= 5.0
            if url.startswith('https://'): score += 0.5
            
            ranked_urls.append((url, score))
        
        ranked_urls.sort(key=lambda x: x[1], reverse=True)
        return ranked_urls

    def scrape_with_enhanced_extraction(self, url: str) -> Tuple[str, bool, int, Dict]:
        try:
            response = requests.get(url, headers=config.HEADERS, timeout=10)
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
        model_name = config.SYNTHESIS_MODEL # Using Synthesis model as a default
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