import sys
import re
import requests
from datetime import datetime
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
from PySide6.QtCore import Qt, QThread, Signal, QPropertyAnimation, QEasingCurve

# --- NEW: SEMANTIC MEMORY CLASS ---
class SemanticMemory:
    """Handles storing and retrieving chat messages using embeddings for semantic recall."""
    def __init__(self, model='nomic-embed-text', log_callback=None):
        self.model = model
        self.memory = []
        self.log_callback = log_callback

    def _log(self, message):
        if self.log_callback:
            # MODIFICATION: Removed emoji for cleaner logs
            self.log_callback(f"[SemanticMemory] {message}")

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generates an embedding for a given text."""
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return np.array(response['embedding'])
        except Exception as e:
            self._log(f"Error generating embedding: {e}")
            return np.zeros(768) # Assuming nomic-embed-text has a dimension of 768

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

        self._log(f"Retrieving contextual history: {top_k} semantic messages + last {last_n} guaranteed messages.")

        # Step 1: Guarantee the last 'n' messages for immediate conversational context.
        actual_last_n = min(last_n, len(self.memory))
        guaranteed_messages = self.memory[-actual_last_n:]
        if guaranteed_messages:
            self._log(f"  -> Guaranteed retrieval of last {len(guaranteed_messages)} messages.")

        # Step 2: Perform semantic search on the *rest* of the history for long-term context.
        searchable_memory = self.memory[:-actual_last_n] if len(self.memory) > actual_last_n else []
        
        semantic_messages = []
        if searchable_memory and top_k > 0:
            self._log(f"Searching for {top_k} semantically relevant messages in remaining {len(searchable_memory)} memories...")
            query_embedding = self._get_embedding(query)

            scored_messages = []
            for mem in searchable_memory:
                similarity = self._cosine_similarity(query_embedding, mem['embedding'])
                scored_messages.append({'message': mem, 'score': similarity})

            scored_messages.sort(key=lambda x: x['score'], reverse=True)

            for item in scored_messages[:top_k]:
                message_content = item['message']['content']
                self._log(f"  -> Retrieved semantically (Score: {item['score']:.4f}): '{message_content[:60]}...'")
                semantic_messages.append(item['message'])
        elif top_k <= 0:
             self._log("Semantic search skipped (top_k=0).")
        else:
            self._log("No older messages available for semantic search.")

        # Step 3: Combine the two lists.
        combined_messages = semantic_messages + guaranteed_messages

        # Step 4: Format the final list for output
        final_history = []
        for msg in combined_messages:
            final_history.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        self._log(f"  -> Final contextual history contains {len(final_history)} messages.")
        return final_history

    def clear(self):
        """Clears all messages from the semantic memory."""
        self.memory = []
        self._log("Memory has been cleared.")

# --- SEARCH INTENT AGENT SYSTEM PROMPT ---
SEARCH_INTENT_PROMPT = """You are a Search Query Decomposer. Your sole purpose is to analyze a user's query and break it down into a structured list of distinct, searchable topics.

## CONVERSATIONAL CONTEXT:
- You will be provided with the recent chat history before the user's latest query.
- Use this history to understand the user's intent. For example, if the user says "that wasn't good enough," look at the previous AI response to understand what topic they are referring to and create a better, more specific search plan.
- Your primary focus is always the *last user query*, but the history provides the necessary context to interpret it correctly.

## YOUR TASK:
1.  Read the chat history to understand the context.
2.  Analyze the user's final query in light of that context.
3.  Identify the individual questions or concepts that need to be searched to provide a comprehensive answer.
4.  For each identified item, formulate a clear, concise search topic.
5.  Output these topics in a structured `<search_plan>`.
6.  Your output should be concise and directly to the point.

## OUTPUT FORMAT:
You MUST respond with ONLY the `<search_plan>` format. Do not add any commentary or explanation.

<search_plan>
<topic>[First distinct searchable topic]</topic>
<topic>[Second distinct searchable topic]</topic>
<topic>[Third distinct searchable topic, if applicable]</topic>
</search_plan>

## EXAMPLES:

User Query: "What's the latest on the new US-EU trade agreement, and how does it affect German car manufacturers?"
Your Response:
<search_plan>
<topic>latest news on new US-EU trade agreement</topic>
<topic>impact of new US-EU trade agreement on German car manufacturers</topic>
</search_plan>

User Query: "Tell me about the recent meeting between the US president and the Russian leader in Alaska."
Your Response:
<search_plan>
<topic>details of recent meeting between US president and Russian leader in Alaska</topic>
<topic>key outcomes and agreements from US-Russia Alaska summit</topic>
</search_plan>
"""

# --- VALIDATOR AGENT SYSTEM PROMPT ---
VALIDATOR_PROMPT = """You are a Content Validation Agent. Your sole job is to determine if scraped web content is relevant and useful for answering a user's specific query.

## YOUR INPUTS:
1. USER QUERY: The original question the user asked
2. SCRAPED CONTENT: Web content that was retrieved from search results

## YOUR TASK:
Analyze whether the scraped content can adequately answer the user's query. Consider:

**PASS Criteria (output <pass>):**
- Content directly addresses the user's question
- Information is relevant and on-topic
- Content contains specific, actionable data the user needs
- Information appears current/recent for time-sensitive queries
- Content quality is sufficient to generate a good answer
- NEVER BE OVERLY VERBOSE! - GET STRAIGHT TO THE POINT! - YOUR OUTPUT SHOULD NOT BE LONG OR EXTENSIVE! 

**FAIL Criteria (output <fail>):**
- Content is off-topic or unrelated to the query
- Information is too generic/vague to be useful
- Content is clearly outdated for current information requests
- Scraped content is mostly navigation text, ads, or junk
- Content doesn't contain the specific information requested

## OUTPUT FORMAT:
You must respond with ONLY one of these formats:

For relevant content:
<pass>Content adequately addresses the query about [brief topic]</pass>

For irrelevant content:
<fail>Content is [specific reason - off-topic/outdated/generic/insufficient]</fail>
"""

# --- MAIN SEARCH AGENT SYSTEM PROMPT ---
MAIN_SEARCH_PROMPT = """You are a web search AI assistant. You have access to real-time web search and should use it intelligently. You will be given a user's query and a semantically relevant chat history.

## NEW INSTRUCTION: SEARCH PLAN
- If the user's query is preceded by a `<search_plan>` block, this is a high-priority directive from a pre-analysis agent.
- You MUST use the `<topic>` items within that plan as a strong guide for formulating your `<search_request>`. The plan is a decomposed analysis of the user's true intent.

## YOUR PROCESS (Chain of Thought):
1.  **Analyze the User's Query & History:** Understand the user's immediate intent from their latest query. If a `<search_plan>` is present, prioritize it. Use the provided relevant history to understand the broader context.
2.  **Formulate a Search Plan:** Decide on the best search query based on the user's request and any provided `<search_plan>`.
    - **Use a target domain** for queries about specific data like stock prices, weather forecasts, or official announcements where a known authoritative source exists (e.g., finance.yahoo.com, weather.com, reuters.com).
    - **Omit the domain for a general search** when the query is broad, exploratory, or seeks opinions/reviews from multiple sources (e.g., "reviews of the new Rivian R2", "what are the latest theories on dark matter?").
3.  **Output Your Plan:** Before the main answer, explain your reasoning and search plan inside <think>...</think> tags. This is your internal monologue.
4.  **Execute Search (if needed):** Use the <search_request> tool.
5.  **Synthesize and Cite:** After getting search results, construct a final answer, citing sources using the <sources> format.

## WHEN TO SEARCH:
Search for queries that benefit from current, recent, or specific information including:
- Stock prices, market data, financial news
- Recent news, breaking news, current events  
- Weather forecasts, current conditions
- Product reviews, public opinions, and broad exploratory topics
- "Today", "latest", "recent", "current" queries

## SEARCH FORMAT:
The <domain> tag is OPTIONAL. Only use it when you have high confidence in a specific authoritative source.
<search_request><query>specific targeted query</query><domain>[optional-domain.com]</domain></search_request>

## NEW: ABILITY TO CONDUCT AN ADDITIONAL SEARCH
- After you receive the initial search results, you must evaluate them.
- If you determine the information is INSUFFICIENT to provide a high-quality answer (e.g., the user wants local gems, but results are only large chains), you can request ONE additional search to get more specific information.
- To do this, your response must consist **ONLY** of the `<additional_search>` tag. Do not add any other text, thoughts, or formatting.
- The system will see this request, perform the new search, and then provide you with the combined results from BOTH searches to generate a final, complete answer.

ADDITIONAL SEARCH FORMAT (Your entire response must be only this):
<additional_search><query>your new, refined, and specific search query</query></additional_search>

## RESPONSE FORMATTING:
- You MUST use Markdown for all formatting (e.g., **bold**, *italics*, bullet points with `*` or `-`).
- This is not optional. Your final output to the user must be well-formatted Markdown.
- Do not wrap your response in a code block unless you are showing a code example.

Current date: {current_date}

"""

class SearchWorker(QThread):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str)

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def __init__(self, prompt: str, memory: SemanticMemory, force_search: bool = False):
        super().__init__()
        self.prompt = prompt
        self.memory = memory
        self.force_search = force_search

        self.SCRAPE_TOP_N_RESULTS = 5
        self.MAX_SOURCES_TO_SCRAPE = 2

        formatted_main_prompt = MAIN_SEARCH_PROMPT.format(
            current_date=datetime.now().strftime('%A, %B %d, %Y')
        )
        self.main_messages = [{'role': 'system', 'content': formatted_main_prompt}]
        self.validator_messages = [{'role': 'system', 'content': VALIDATOR_PROMPT}]

    def _get_search_plan(self, user_query: str) -> str:
        """Calls the Search Intent Agent to decompose the user query, now WITH conversational context."""
        self.log_message.emit("\n" + "="*25 + "\n[IntentAgent] Calling with conversational context...\n" + "="*25)
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
            
            self.log_message.emit(f"[IntentAgent] Providing {len(sanitized_history)} contextual messages.")
            
            system_message = {'role': 'system', 'content': SEARCH_INTENT_PROMPT}
            current_user_message = {'role': 'user', 'content': user_query}
            
            messages = [system_message] + sanitized_history + [current_user_message]
            
            response = ollama.chat(model='qwen3:8b', messages=messages, stream=False)
            plan = response['message']['content'].strip()
            self.log_message.emit(f"[IntentAgent] Plan received:\n{plan}\n")
            return plan
        except Exception as e:
            self.log_message.emit(f"[IntentAgent] Failed: {e}. Proceeding without plan.\n")
            return ""

    def run(self):
        try:
            self.log_message.emit("\n" + "─"*15 + " New Request Started " + "─"*15)
            
            # MODIFICATION: This list will hold the ground truth for all sources used.
            sources_used_for_synthesis = []
            final_response = ""

            if self.force_search:
                search_plan = self._get_search_plan(self.prompt)
                if search_plan:
                    self.prompt = f"{search_plan}\n\nOriginal Query: {self.prompt}"
            
            self.log_message.emit(f"User Prompt (with plan if any):\n{self.prompt}")

            system_message = self.main_messages[0]
            
            relevant_history = self.memory.retrieve_relevant_messages(self.prompt, top_k=3, last_n=2)
            
            sanitized_history = []
            for msg in relevant_history:
                if msg['role'] == 'assistant':
                    clean_content = re.sub(r'<think>.*?</think>', '', msg['content'], flags=re.DOTALL)
                    clean_content = re.sub(r'<search_request>.*?</search_request>', '', clean_content, flags=re.DOTALL).strip()
                    sanitized_history.append({'role': 'assistant', 'content': clean_content})
                else:
                    sanitized_history.append(msg)
            
            current_user_message = {'role': 'user', 'content': self.prompt}
            
            messages_for_planning = [system_message] + sanitized_history + [current_user_message]
            self.log_message.emit(f"Building context with {len(sanitized_history)} SANITIZED relevant messages.")

            self.progress.emit("Analyzing query and planning response...")
            initial_model_response = self.get_ollama_response(messages=messages_for_planning)
            search_requests = self.extract_search_requests(initial_model_response)

            if len(search_requests) > 1:
                self.log_message.emit(f"Model attempted {len(search_requests)} searches. Limiting to 1 for quality.")
                search_requests = search_requests[:1]

            if search_requests:
                self.log_message.emit(f"[Search] Performing targeted search based on model analysis.")
                # MODIFICATION: `execute_search_plan` now returns sources.
                scraped_content, sources_from_search = self.execute_search_plan(search_requests)

                if not scraped_content.strip():
                    self.log_message.emit("[Search] No usable content. Responding with available knowledge.")
                    prompt_for_no_search = "The web search failed to return any content. Please answer the user's last question using only your existing knowledge, without mentioning the failed search."
                    messages_for_fallback = messages_for_planning + [
                        {'role': 'assistant', 'content': initial_model_response},
                        {'role': 'user', 'content': prompt_for_no_search}
                    ]
                    final_response = self.get_ollama_response(messages=messages_for_fallback)
                else:
                    self.progress.emit("Validating search results...")
                    validation_result = self.validate_scraped_content(self.prompt, scraped_content)
                    
                    if validation_result == "pass":
                        self.log_message.emit("[Validator] Content passed relevance check.")
                        self.progress.emit("Synthesizing validated response...")
                        
                        # MODIFICATION: Add the verified sources to our ground-truth list.
                        sources_used_for_synthesis.extend(sources_from_search)

                        synthesis_prompt = f"""<think>
                        The initial search was successful and the validator confirmed the content is relevant. Now I will synthesize this information into a clear, concise answer for the user, making sure to include citations from the provided content.
                        </think>

                        VALIDATED SEARCH RESULTS:
                        {scraped_content}

                        Instructions: Based on the provided search results, please give a comprehensive answer to the user's last question. 
                        """
                        messages_for_synthesis = messages_for_planning + [
                            {'role': 'assistant', 'content': initial_model_response},
                            {'role': 'user', 'content': synthesis_prompt}
                        ]
                        synthesis_response_1 = self.get_ollama_response(messages=messages_for_synthesis)

                        additional_query = self.extract_additional_search(synthesis_response_1)
                        if additional_query:
                            self.log_message.emit(f"[Model] Requested additional search for: '{additional_query}'")
                            self.progress.emit("Performing additional search requested by model...")
                            
                            additional_scraped_content, sources_from_add_search = self.execute_search_plan([(additional_query, None)])

                            if additional_scraped_content and additional_scraped_content.strip():
                                self.progress.emit("Validating additional search results...")
                                additional_validation = self.validate_scraped_content(self.prompt, additional_scraped_content)

                                if additional_validation == "pass":
                                    self.log_message.emit("[Validator] Additional search content passed.")
                                    self.progress.emit("Synthesizing final response with all data...")
                                    
                                    # MODIFICATION: Add the new sources to our ground-truth list.
                                    sources_used_for_synthesis.extend(sources_from_add_search)

                                    final_synthesis_prompt = f"""<think>
                                    My first search provided some information, but I determined it was insufficient and requested an additional search for '{additional_query}'. That search was successful. Now I have the results from both searches and will combine them into a single, comprehensive final answer.
                                    </think>

                                    INITIAL SEARCH RESULTS:
                                    {scraped_content}

                                    ADDITIONAL SEARCH RESULTS:
                                    {additional_scraped_content}

                                    Instructions: Based on the combined information from BOTH sets of search results, please give a final, comprehensive answer to the user's last question. It is critical to synthesize information from both contexts 
                                    """
                                    messages_for_final_synthesis = messages_for_synthesis + [
                                        {'role': 'assistant', 'content': synthesis_response_1},
                                        {'role': 'user', 'content': final_synthesis_prompt}
                                    ]
                                    final_response = self.get_ollama_response(messages=messages_for_final_synthesis)
                                else:
                                    self.log_message.emit("[Validator] Additional search content FAILED validation. Using initial results only.")
                                    fallback_prompt = f"""<think>
                                    I attempted an additional search for '{additional_query}', but the results were not relevant. I must now answer using only the initial search results. I will answer the user's question as best I can with the information I have.
                                    </think>
                                    INITIAL SEARCH RESULTS:{scraped_content}
                                    Instructions: Your additional search failed validation. Answer the user's question using ONLY the initial search results provided above."""
                                    messages_for_fallback = messages_for_synthesis + [{'role': 'assistant', 'content': synthesis_response_1}, {'role': 'user', 'content': fallback_prompt}]
                                    final_response = self.get_ollama_response(messages=messages_for_fallback)
                            else:
                                self.log_message.emit("[Search] Additional search returned no content. Using initial results only.")
                                fallback_prompt = f"""<think>
                                I attempted an additional search for '{additional_query}', but it returned no usable content. I must now answer using only the initial search results. I will answer the user's question as best I can with the information I have.
                                </think>
                                INITIAL SEARCH RESULTS:{scraped_content}
                                Instructions: Your additional search failed to find anything. Answer the user's question using ONLY the initial search results provided above."""
                                messages_for_fallback = messages_for_synthesis + [{'role': 'assistant', 'content': synthesis_response_1}, {'role': 'user', 'content': fallback_prompt}]
                                final_response = self.get_ollama_response(messages=messages_for_fallback)
                        else:
                            final_response = synthesis_response_1
                    else:
                        self.log_message.emit(f"[Validator] Content failed: {validation_result}")
                        self.progress.emit("Content failed validation, attempting refined search...")
                        
                        refined_content, sources_from_refined = self.retry_search_with_refinement(search_requests[0])
                        if refined_content:
                            # MODIFICATION: Add the refined sources to our ground-truth list.
                            sources_used_for_synthesis.extend(sources_from_refined)
                            refined_synthesis_prompt = f"""<think>
                            The first search failed validation. I have conducted a refined search which yielded better results. I will now synthesize this new content into the final answer.
                            </think>

                            REFINED SEARCH RESULTS:
                            {refined_content}

                            Instructions: Based on these new search results, please give a comprehensive answer to the user's last question. Include proper source citations."""
                            messages_for_refined_synthesis = messages_for_planning + [
                                {'role': 'assistant', 'content': initial_model_response},
                                {'role': 'user', 'content': refined_synthesis_prompt}
                            ]
                            final_response = self.get_ollama_response(messages=messages_for_refined_synthesis)
                        else:
                            self.log_message.emit("[Search] Primary and refined searches failed validation.")
                            prompt_for_failed_search = "Both the primary and refined web searches failed to return useful content. Please inform the user that you couldn't find relevant information online and answer their last question using only your existing knowledge."
                            messages_for_final_fallback = messages_for_planning + [
                                {'role': 'assistant', 'content': initial_model_response},
                                {'role': 'user', 'content': prompt_for_failed_search}
                            ]
                            final_response = self.get_ollama_response(messages=messages_for_final_fallback)
            else:
                self.progress.emit("Responding with existing knowledge...")
                self.log_message.emit("Model determined no search needed. Using existing knowledge.")
                final_response = initial_model_response

            # MODIFICATION: The final, deterministic attachment step.
            final_response_with_sources = self._attach_sources_to_response(final_response, sources_used_for_synthesis)

            self.log_message.emit("─"*17 + " Request Completed " + "─"*16 + "\n")
            self.finished.emit(final_response_with_sources)

        except Exception as e:
            import traceback
            error_str = f"An error occurred: {e}\n{traceback.format_exc()}"
            self.log_message.emit(f"ERROR: {error_str}")
            self.error.emit(str(e))

    def execute_search_plan(self, search_requests: List[Tuple[str, str]]) -> Tuple[str, List[Dict]]:
        """Execute search plan and return content string and a list of source dicts."""
        all_scraped_content = []
        all_sources = []
        
        for query, domain in search_requests:
            self.progress.emit(f"Searching for '{query}'...")
            self.log_message.emit(f"Executing search: '{query}'" + (f" on '{domain}'" if domain else ""))
            
            # MODIFICATION: Function now returns sources list.
            content, success_count, source_quality, sources = self.perform_single_search_and_scrape(query, domain)
            
            if success_count == 0 and domain:
                self.log_message.emit(f"Domain-specific search failed. Attempting broader search.")
                self.progress.emit(f"Broadening search scope...")
                content, success_count, source_quality, sources = self.perform_single_search_and_scrape(query, domain=None)
                self.log_message.emit(f"Fallback completed: {success_count} sources, quality: {source_quality}")
            elif success_count > 0:
                self.log_message.emit(f"Search successful: {success_count} sources, quality: {source_quality}")
            
            if content.strip():
                all_scraped_content.append(content)
                all_sources.extend(sources)
                
        return "\n\n".join(all_scraped_content), all_sources

    def perform_single_search_and_scrape(self, query: str, domain: str = None) -> Tuple[str, int, str, List[Dict]]:
        """Performs a search and returns content, count, quality, and a list of source dicts."""
        try:
            search_q = f"{query} site:{domain}" if domain else query
            self.log_message.emit(f"Searching: '{search_q}'")
            
            with DDGS() as ddgs:
                search_results = [r for r in ddgs.text(search_q, max_results=self.SCRAPE_TOP_N_RESULTS)]
            
            if not search_results:
                self.log_message.emit(f"No results found for: '{search_q}'")
                return "", 0, "none", []

            ranked_urls = self.rank_urls_by_quality(search_results, query.lower())
            
            if not ranked_urls:
                self.log_message.emit("No quality URLs found after ranking")
                return "", 0, "poor", []

            urls_to_scrape = ranked_urls[:self.MAX_SOURCES_TO_SCRAPE]
            self.log_message.emit(f"[Search] Selected {len(urls_to_scrape)} top sources from {len(ranked_urls)} candidates.")

            scraped_results_content = []
            scraped_sources_list = []
            success_count = 0
            total_content_length = 0
            
            for i, (url, score) in enumerate(urls_to_scrape):
                self.progress.emit(f"Extracting from source {i+1}/{len(urls_to_scrape)}...")
                # MODIFICATION: Scraper now returns a source dictionary.
                scraped_data, success, content_length, source_info = self.scrape_with_enhanced_extraction(url)
                
                if success and content_length > 200:
                    scraped_results_content.append(scraped_data)
                    scraped_sources_list.append(source_info) # Capture the ground truth.
                    success_count += 1
                    total_content_length += content_length
                    self.log_message.emit(f"[Scraper] Extracted: {url} ({content_length} chars, rank score: {score:.1f})")
                else:
                    self.log_message.emit(f"[Scraper] Poor extraction: {url} (content too short or failed).")
            
            if success_count >= 2 and total_content_length > 1000:
                quality = "excellent"
            elif success_count >= 1 and total_content_length > 600:
                quality = "good"
            elif success_count >= 1 and total_content_length > 300:
                quality = "fair"
            else:
                quality = "poor"
            
            self.log_message.emit(f"[Search] Quality: {quality} ({total_content_length} chars from {success_count}/{len(urls_to_scrape)} sources).")
            return "\n".join(scraped_results_content), success_count, quality, scraped_sources_list
            
        except Exception as e:
            self.log_message.emit(f"Search failed for '{query}': {e}")
            return f"<e>Search failed: {e}</e>", 0, "error", []

    def rank_urls_by_quality(self, search_results: List[Dict], query: str) -> List[Tuple[str, float]]:
        """CRITICAL: Intelligent URL ranking for different query types"""
        
        financial_domains = [
            'finance.yahoo.com', 'marketwatch.com', 'bloomberg.com', 'reuters.com',
            'cnbc.com', 'wsj.com', 'investing.com', 'morningstar.com'
        ]
        news_domains = [
            'reuters.com', 'apnews.com', 'bbc.com', 'cnn.com', 'npr.org',
            'bloomberg.com', 'wsj.com', 'cnbc.com'
        ]
        tech_domains = [
            'techcrunch.com', 'arstechnica.com', 'theverge.com', 'wired.com',
            'engadget.com', 'zdnet.com'
        ]
        weather_domains = [
            'weather.com', 'accuweather.com', 'weather.gov', 'wunderground.com'
        ]
        
        query_lower = query.lower()
        priority_domains = []
        
        if any(word in query_lower for word in ['stock', 'market', 'trading', 'nasdaq', 'dow', 'price', 'shares']):
            priority_domains = financial_domains
        elif any(word in query_lower for word in ['news', 'breaking', 'latest', 'today', 'current']):
            priority_domains = news_domains  
        elif any(word in query_lower for word in ['tech', 'technology', 'software', 'ai', 'computer']):
            priority_domains = tech_domains
        elif any(word in query_lower for word in ['weather', 'forecast', 'temperature', 'rain', 'snow']):
            priority_domains = weather_domains
        
        ranked_urls = []
        
        for result in search_results:
            url = result['href']
            title = result.get('title', '').lower()
            snippet = result.get('body', '').lower()
            
            try:
                domain = url.split('/')[2].lower()
            except (IndexError, AttributeError):
                continue
            
            score = 1.0
            
            if any(pd in domain for pd in priority_domains):
                score += 10.0
            
            if any(word in title + snippet for word in ['today', 'latest', 'current', '2025', 'live']):
                score += 3.0
            
            query_words = query_lower.split()
            title_matches = sum(1 for word in query_words if word in title)
            score += title_matches * 2.0
            
            low_quality = ['pinterest.com', 'quora.com', 'answers.com', 'wikihow.com', 'ehow.com']
            if any(lq in domain for lq in low_quality):
                score -= 5.0
            
            if url.startswith('https://'):
                score += 0.5
                
            ranked_urls.append((url, score))
        
        ranked_urls.sort(key=lambda x: x[1], reverse=True)
        
        return ranked_urls

    def scrape_with_enhanced_extraction(self, url: str) -> Tuple[str, bool, int, Dict]:
        """Improved scraping that returns structured source info."""
        self.log_message.emit(f"Scraping: {url}")
        
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            html_content = response.text
        except requests.RequestException as e:
            self.log_message.emit(f"Download failed for {url}: {e}")
            return f"<result url='{url}' error='Failed to download'></result>", False, 0, {}

        metadata = trafilatura.extract_metadata(html_content)
        title = metadata.title if metadata and metadata.title else "Unknown Title"
        date = metadata.date if metadata and metadata.date else "N/A"
        
        main_content = trafilatura.extract(
            html_content, 
            include_comments=False, 
            include_tables=True,
            favor_precision=True
        )

        if main_content and len(main_content) > 200:
            content_to_use = main_content
        else:
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            
            if text and len(text) > 200:
                content_to_use = text
            else:
                return f"<result url='{url}' title='{title}' date='{date}' error='Insufficient content'></result>", False, 0, {}

        content_length = len(content_to_use)
        
        if content_length < 300:
            return f"<result url='{url}' title='{title}' date='{date}' error='Content below quality threshold'></result>", False, 0, {}
        
        if content_length > 8000:
            content_to_use = content_to_use[:8000] + "..."
        
        formatted_string = f"""<result url="{url}" date="{date}">
        <title>{title}</title>
        <content>
        {content_to_use}
        </content>
        </result>"""
        
        source_info = {'url': url, 'title': title, 'date': date}
        
        return formatted_string, True, len(content_to_use), source_info

    def extract_search_requests(self, text: str) -> List[Tuple[str, str]]:
        """Extract search requests with improved validation"""
        pattern = r'<search_request>\s*<query>(.*?)</query>(?:\s*<domain>(.*?)</domain>)?\s*</search_request>'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        
        valid_requests = []
        for query, domain in matches:
            query = query.strip()
            domain = domain.strip() if domain else None
            
            if len(query) < 3:
                continue
                
            if any(existing_query.lower() == query.lower() for existing_query, _ in valid_requests):
                continue
                
            valid_requests.append((query, domain))
            
            if len(valid_requests) >= 1:
                break
                
        return valid_requests

    def extract_additional_search(self, text: str) -> str:
        """NEW: Extracts the query from an <additional_search> tag."""
        pattern = r'<additional_search>\s*<query>(.*?)</query>\s*</additional_search>'
        match = re.search(pattern, text.strip(), re.DOTALL | re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            # Ensure the response is ONLY the tag, with maybe some whitespace
            if text.strip() == match.group(0).strip() and len(query) > 3:
                return query
        return ""

    def validate_scraped_content(self, user_query: str, scraped_content: str) -> str:
        """Validator agent to check content relevance"""
        self.log_message.emit("Running validator agent on scraped content...")
        
        validation_prompt = f"""USER QUERY: {user_query}

        SCRAPED CONTENT TO VALIDATE:
        {scraped_content}
        """
        try:
            validator_messages = self.validator_messages + [{'role': 'user', 'content': validation_prompt}]
            response = ollama.chat(model='qwen3:8b', messages=validator_messages, stream=False)
            validator_output = response['message']['content'].strip()
            
            if '<pass>' in validator_output.lower():
                return "pass"
            elif '<fail>' in validator_output.lower():
                fail_match = re.search(r'<fail>(.*?)</fail>', validator_output, re.IGNORECASE | re.DOTALL)
                return fail_match.group(1).strip() if fail_match else "Content failed validation"
            else:
                return "pass"
                
        except Exception as e:
            self.log_message.emit(f"Validator agent failed: {e}")
            return "pass"

    def retry_search_with_refinement(self, original_search: Tuple[str, str]) -> Tuple[str, List[Dict]]:
        """Retry search and return content string and a list of source dicts."""
        original_query, original_domain = original_search
        
        self.log_message.emit("Attempting refined search...")
        
        refined_queries = []
        
        if "recent" not in original_query.lower():
            refined_queries.append((f"{original_query} recent latest 2024", original_domain))
            
        if original_domain:
            if "finance.yahoo.com" in original_domain:
                refined_queries.append((original_query, "marketwatch.com"))
            elif "reuters.com" in original_domain:
                refined_queries.append((original_query, "apnews.com"))
        
        refined_queries.append((f"{original_query} news update", None))
        
        for refined_query, refined_domain in refined_queries[:6]:
            self.log_message.emit(f"Trying refined search: '{refined_query}'" + (f" on {refined_domain}" if refined_domain else ""))
            
            content, success_count, quality, sources = self.perform_single_search_and_scrape(refined_query, refined_domain)
            
            if success_count > 0:
                validation_result = self.validate_scraped_content(self.prompt, content)
                if validation_result == "pass":
                    self.log_message.emit("[Validator] Refined search passed validation.")
                    return content, sources
                else:
                    self.log_message.emit(f"[Validator] Refined search also failed: {validation_result}")
            
        self.log_message.emit("[Search] All refined search attempts failed.")
        return "", []

    def get_ollama_response(self, messages: list) -> str:
        """Get response from the main Ollama model using a list of messages."""
        model_name = 'qwen3:14b'
        
        log_parts = ["\n" + "--- PAYLOAD BEING SENT TO MODEL ---"]
        system_prompt = messages[0]['content']
        history_messages = messages[1:-1]
        final_task = messages[-1]['content']

        log_parts.append("\n[SYSTEM PROMPT]:")
        log_parts.append(f'"{system_prompt[:150].strip().replace(chr(10), " ")}..."')

        log_parts.append("\n[SEMANTIC HISTORY RETRIEVED]:")
        if history_messages:
            for msg in history_messages:
                role = msg.get('role', 'N/A').upper()
                content = msg.get('content', '').strip().replace('\n', '\\n')
                if len(content) > 120:
                    content = content[:120] + "..."
                log_parts.append(f"  - [{role}]: {content}")
        else:
            log_parts.append("  (None)")

        log_parts.append("\n[CURRENT USER TASK]:")
        log_parts.append(f'"{final_task.strip().replace(chr(10), " ")}"')
        
        log_parts.append("\n" + "--- END OF PAYLOAD ---" + "\n")
        self.log_message.emit("\n".join(log_parts))

        self.log_message.emit(f"Requesting response from {model_name} with {len(messages)} messages in context...")
        try:
            response = ollama.chat(model=model_name, messages=messages, stream=False)
            self.log_message.emit(f"[Ollama] {model_name} response received.")
            return response['message']['content']
        except Exception as e:
            self.log_message.emit(f"[Ollama] {model_name} request failed: {e}")
            raise

    def _attach_sources_to_response(self, response_text: str, sources: List[Dict]) -> str:
        """
        Deterministically attaches a <sources> block to the response using the
        ground-truth list of sources, removing any model-generated block.
        """
        if not sources:
            return response_text

        # Remove any <sources> block the model might have generated.
        clean_response = re.sub(r'<sources>.*?</sources>', '', response_text, flags=re.DOTALL).strip()

        # Build the new, guaranteed-correct sources block.
        sources_lines = []
        for source in sources:
            sources_lines.append(f'<source url="{source["url"]}" date="{source["date"]}">{source["title"]}</source>')
        
        sources_block = "<sources>\n" + "\n".join(sources_lines) + "\n</sources>"

        return f"{clean_response}\n\n{sources_block}"

class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent; self.pressing = False; self.setObjectName("customTitleBar")
        layout = QHBoxLayout(self); layout.setContentsMargins(10, 0, 0, 0); layout.setSpacing(10)
        self.title = QLabel("Web.ai"); self.title.setObjectName("windowTitle"); layout.addWidget(self.title); layout.addStretch()
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
            
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def toggle_citations(self):
        self.is_citations_expanded = not self.is_citations_expanded
        try:
            self.citations_animation.finished.disconnect()
        except (RuntimeError, TypeError):
            pass

        if self.is_citations_expanded:
            self.citations_container.setVisible(True)
            self.citations_container.setMaximumHeight(16777215)
            target_height = self.citations_container.sizeHint().height()
            self.citations_animation.setStartValue(0)
            self.citations_animation.setEndValue(target_height)
        else:
            current_height = self.citations_container.height()
            self.citations_animation.setStartValue(current_height)
            self.citations_animation.setEndValue(0)
            self.citations_animation.finished.connect(lambda: self.citations_container.setVisible(False))
        self.citations_animation.start()

    def toggle_thinking(self):
        self.is_thinking_expanded = not self.is_thinking_expanded
        try:
            self.thinking_animation.finished.disconnect()
        except (RuntimeError, TypeError):
            pass

        if self.is_thinking_expanded:
            self.toggle_thinking_button.setText("Hide")
            self.thinking_container.setVisible(True)
            self.thinking_container.setMaximumHeight(16777215)
            target_height = self.thinking_container.sizeHint().height()
            self.thinking_animation.setStartValue(0)
            self.thinking_animation.setEndValue(target_height)
        else:
            self.toggle_thinking_button.setText("Thinking Process")
            self.thinking_animation.setStartValue(self.thinking_container.height())
            self.thinking_animation.setEndValue(0)
            self.thinking_animation.finished.connect(lambda: self.thinking_container.setVisible(False))
        self.thinking_animation.start()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.memory = SemanticMemory(log_callback=lambda msg: self.update_log(msg))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.init_ui()
        
    def init_ui(self):
        self.setGeometry(100, 100, 1100, 750)
        self.setMinimumSize(800, 600)
        
        main_container = QFrame()
        main_container.setObjectName("mainContainer")
        
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(1,1,1,1)
        container_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        
        content_splitter = QSplitter(Qt.Horizontal)
        
        chat_panel = QWidget()
        chat_panel_layout = QVBoxLayout(chat_panel)
        chat_panel_layout.setContentsMargins(10,10,5,10)
        
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setObjectName("chatScrollArea")
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.addStretch()
        
        self.chat_scroll.setWidget(self.chat_container)
        chat_panel_layout.addWidget(self.chat_scroll)
        
        log_panel = QWidget()
        log_panel_layout = QVBoxLayout(log_panel)
        log_panel_layout.setContentsMargins(5,10,10,10)
        
        log_title = QLabel("Action Log")
        log_title.setObjectName("panelTitle")
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setObjectName("logDisplay")
        
        log_panel_layout.addWidget(log_title)
        log_panel_layout.addWidget(self.log_display)
        
        content_splitter.addWidget(chat_panel)
        content_splitter.addWidget(log_panel)
        content_splitter.setSizes([700, 300])
        
        footer_frame = QFrame()
        footer_frame.setObjectName("footerFrame")
        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10,10,10,5)
        
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit()
        self.input_field.setObjectName("inputField")
        self.input_field.setPlaceholderText("Enter your query...")
        self.input_field.setFixedHeight(50)
        
        self.send_button = QPushButton("➤")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(50, 50)
        self.send_button.clicked.connect(self.send_message)
        
        self.force_search_toggle = QPushButton("⌕")
        self.force_search_toggle.setObjectName("forceSearchButton")
        self.force_search_toggle.setCheckable(True)
        self.force_search_toggle.setFixedSize(50, 50)
        self.force_search_toggle.setToolTip("Enable/Disable Search Mode")
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.force_search_toggle)
        
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        
        self.clear_button = QPushButton("✨ New Chat")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self.clear_chat_session)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.clear_button)
        
        footer_layout.addLayout(input_layout)
        footer_layout.addLayout(status_layout)
        
        container_layout.addWidget(self.title_bar, stretch=0)
        container_layout.addWidget(content_splitter, stretch=1)
        container_layout.addWidget(footer_frame, stretch=0)
        
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
            #logDisplay { border: 1px solid #333333; border-radius: 4px; background-color: #252526; color: #888888; font-family: Consolas, Courier New, monospace; font-size: 12px; }
            QFrame#messageBubbleContainer { background-color: #2D2D2D; border: 1px solid #3C3C3C; border-radius: 8px; max-width: 650px; }
            QFrame#messageBubbleContainer[isUser="true"] { background-color: #004C8A; border-color: #007ACC; }
            QLabel#messageText { background-color: transparent; border: none; padding: 0; color: #D4D4D4; font-size: 14px; }
            
            #toggleDetailButton { 
                background-color: #3C3C3C; color: #CCCCCC; border: none; border-radius: 6px; 
                font-size: 12px; padding: 6px 12px; margin-top: 8px; font-weight: 500;
            }
            #toggleDetailButton:hover { background-color: #4A4A4A; color: #E0E0E0; } 
            #toggleDetailButton:checked { background-color: #555555; color: white; }

            #thinkingContainer, #citationsContainer { 
                background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; 
                margin-top: 4px;
            }
            #thinkingLabel {
                font-family: Consolas, 'Courier New', monospace; font-size: 12px;
                color: #B3B3B3; background-color: transparent; padding: 8px;
            }
            #citationLabel { 
                font-size: 12px; padding: 4px 6px; line-height: 1.4;
                background-color: transparent; border: none;
            } 
            #citationLabel a { color: #4EC9B0; text-decoration: none; } 
            #citationLabel a:hover { text-decoration: underline; color: #6BD4BC; }
            #footerFrame { background-color: #2D2D2D; border-top: 1px solid #3C3C3C; }
            #inputField { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 4px; padding: 8px; color: #F1F1F1; font-size: 14px; }
            #inputField:focus { border: 1px solid #007ACC; }
            #sendButton { 
                background-color: #007ACC; color: white; border: none; border-radius: 25px; font-size: 20px; 
            }
            #sendButton:hover { background-color: #1F9CFD; } 
            #sendButton:disabled { background-color: #4A4A4A; }
            
            #forceSearchButton {
                background-color: #3C3C3C;
                color: #888;
                border: 1px solid #555;
                border-radius: 25px;
                font-size: 20px;
            }
            #forceSearchButton:hover {
                background-color: #4A4A4A;
            }
            #forceSearchButton:checked {
                background-color: #2a5c3d;
                color: #90ee90;
                border: 1px solid #4EC9B0;
            }
            #forceSearchButton:disabled {
                background-color: #252526;
                color: #666;
            }
            
            #statusLabel { color: #888888; font-size: 12px; }
            #clearButton { background-color: #3C3C3C; color: #CCCCCC; border: 1px solid #555; padding: 4px 10px; border-radius: 4px; font-size: 12px; }
            #clearButton:hover { background-color: #4A4A4A; color: white; border-color: #666; }
            QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #4A4A4A; border-radius: 5px; min-height: 25px; } 
            QScrollBar::handle:vertical:hover { background-color: #6A6A6A; }
        """

    def clear_chat_session(self):
        """Clears the semantic memory and the visual chat display."""
        self.memory.clear()

        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.log_display.append(f"\n{datetime.now().strftime('%H:%M:%S')} - --- New Chat Session Started ---\n")
        self.status_label.setText("Ready")
        self.input_field.setFocus()

    def send_message(self):
        """Handles the main send action, checking the state of the force search toggle."""
        text = self.input_field.toPlainText().strip()
        if not text:
            return
            
        self.add_message_to_ui(text, is_user=True)
        
        self.input_field.clear()
        self.set_ui_enabled(False)
        
        is_force_search_enabled = self.force_search_toggle.isChecked()
        
        self.log_display.append(f"{datetime.now().strftime('%H:%M:%S')} - USER QUERY: {text}")
        if is_force_search_enabled:
            self.log_display.append(f"{datetime.now().strftime('%H:%M:%S')} - MODE: Force Search Enabled")

        self.worker = SearchWorker(text, self.memory, force_search=is_force_search_enabled)
        self.worker.finished.connect(lambda response: self.handle_response(response, original_prompt=text))
        self.worker.error.connect(lambda error: self.handle_error(error, original_prompt=text))
        self.worker.progress.connect(self.update_status)
        self.worker.log_message.connect(self.update_log)
        self.worker.start()

    def add_message_to_ui(self, text: str, is_user: bool):
        """Adds a message bubble to the chat display, but does NOT save to memory."""
        main_text, citations, thinking_text = text, None, None
        
        if not is_user:
            think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
            if think_match:
                thinking_text = think_match.group(1).strip()
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

            sources_match = re.search(r'<sources>(.*?)</sources>', text, re.DOTALL)
            if sources_match:
                sources_block = sources_match.group(1)
                main_text = re.sub(r'<sources>.*?</sources>', '', text, flags=re.DOTALL).strip()
                
                citations_found = re.findall(r'<source url="([^"]+)" date="([^"]*)">(.*?)</source>', sources_block)
                if citations_found:
                    citations = []
                    for url, date, title in citations_found:
                        clean_title = title.strip()
                        if not clean_title: clean_title = "Unknown Title"
                        if len(clean_title) > 80: clean_title = clean_title[:77] + "..."
                        citations.append({'url': url, 'date': date if date else "N/A", 'title': clean_title})
            else:
                main_text = text
            
            main_text = markdown2.markdown(main_text, extras=["fenced-code-blocks", "tables", "cuddled-lists"])
        
        bubble = MessageBubble(main_text if not is_user else text, citations=citations, thinking_text=thinking_text)
        bubble.container.setProperty("isUser", is_user)

        if not is_user:
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
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()))

    def handle_response(self, response: str, original_prompt: str):
        """Handles a successful response from the worker."""
        self.add_message_to_ui(response, is_user=False)
        
        self.memory.add_message(role='user', content=original_prompt)
        self.memory.add_message(role='assistant', content=response)
        
        self.set_ui_enabled(True)
        self.log_display.append(f"{datetime.now().strftime('%H:%M:%S')} - RESPONSE DELIVERED")

    def handle_error(self, error: str, original_prompt: str):
        """Handles an error from the worker."""
        # MODIFICATION: Removed emoji for cleaner UI/logs
        error_msg = f"Error: {error}"
        self.add_message_to_ui(error_msg, is_user=False)
        
        self.memory.add_message(role='user', content=original_prompt)
        self.memory.add_message(role='assistant', content=error_msg)
        
        self.set_ui_enabled(True)
        self.log_display.append(f"{datetime.now().strftime('%H:%M:%S')} - ERROR: {error}")

    def update_status(self, status: str):
        self.status_label.setText(status)

    def update_log(self, message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_display.append(f"{timestamp} - {message}")
        
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_ui_enabled(self, enabled: bool):
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.force_search_toggle.setEnabled(enabled)
        
        if enabled:
            self.status_label.setText("Ready")
            self.input_field.setFocus()
        else:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            if self.send_button.isEnabled():
                self.send_message()
        else:
            super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
