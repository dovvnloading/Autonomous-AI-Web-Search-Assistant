UPDATE LOG
---

---------------------
9_22_25
---------------------



### **Change Log: Project Refactoring**

The single-file application was refactored into a modular, four-file structure to separate concerns and improve maintainability.

#### **Old Structure:**
*   `monolithic_app.py` (Contained all UI, logic, and configuration)

#### **New Structure:**
*   `main.py`
*   `uimain_window.py`
*   `core_logic.py`
*   `config.py`

---

### **New File Responsibilities:**

1.  **`main.py` (Entry Point)**
    *   Starts the application. Its only job is to launch the UI from `uimain_window.py`.

2.  **`uimain_window.py` (User Interface)**
    *   Contains all UI code: the `MainWindow`, message bubbles, and stylesheet. Manages everything the user sees and interacts with.

3.  **`core_logic.py` (Backend Logic)**
    *   The application's "brain." Contains the `SearchWorker` class, which handles all backend processing: web scraping, agent orchestration, and LLM communication.

4.  **`config.py` (Configuration)**
    *   A centralized file for all settings and constants. Model names, the universal `PROMPT_FILE_PATH`, and other parameters are defined here for easy modification.
---
---



------------------------------------------
9_22_25
------------------------------------------



Update Ai_Web_Search.py
### High-Level Summary of Changes

The new code represents a significant architectural evolution, moving from a flexible but complex "decide-then-search" model to a more streamlined and robust "always-search-intelligently" paradigm. The core philosophy has shifted to assume that every user query benefits from a fresh, context-aware web search.

Key improvements focus on three main areas:
1.  **Intelligence & Context:** The system no longer just decides *if* it should search, but now analyzes *how* to search. By classifying the user's intent into categories (e.g., `financial`, `news`, `historical`), it can perform much smarter, domain-specific searches and ranking.
2.  **Efficiency & Performance:** A new Memory Summarization Agent has been introduced to keep the long-term semantic memory lean and effective. Detailed performance timing has been added to the logs, and the UI now includes a stopwatch for user feedback.
3.  **Robustness & User Experience:** The "Force Search" toggle has been removed to simplify the user experience and the core logic. A 30-minute worker timeout has been implemented to prevent hung processes, and the overall code flow is more linear and predictable.

---

### Ⅰ. Architectural & Core Logic Changes

#### **1. Removal of "Force Search" and "Search Decision" Logic**
The most fundamental change is the elimination of the initial decision-making step. In the old version, the application would first ask a general-purpose LLM if a web search was even necessary, a decision the user could bypass with a "Force Search" toggle. This entire dual-path logic has been removed. The new architecture operates on the principle that a targeted web search is always the optimal starting point. This simplifies the `run()` method, makes the application's behavior consistent and predictable, and streamlines the user interface by removing the toggle button.

#### **2. Introduction of "Search Type" Classification Pipeline**
This is the most significant intelligence upgrade. Previously, the IntentAgent only extracted search *topics*. Now, it performs a crucial second task: classifying the user query's intent into a specific `search_type` (e.g., `financial`, `news`, `historical`, `tech`). This classification is then passed down through the entire search pipeline, from execution to scraping to ranking. This enables highly contextual ranking (preferring financial sites for stock queries, academic sites for historical queries) and smarter query augmentation (e.g., only adding the current year to time-sensitive searches).

#### **3. Addition of a Memory Summarization Agent**
To improve long-term context and efficiency, a new agent has been introduced. The old system stored the full, verbose AI response in the semantic memory. The new system, after generating a final answer, calls a `MemorySummaryAgent`. This agent creates a concise, third-person summary of the interaction (e.g., "Answered the user's query about the Q2 2024 earnings of NVIDIA by summarizing financial reports from Bloomberg and Reuters."). This lean summary is then stored in the semantic memory. This keeps the memory efficient, reduces noise, and improves the quality of semantic recall for future conversations.

---

### Ⅱ. Detailed `SearchWorker` Class Changes

*   **Constructor (`__init__`)**
    *   **Old:** Accepted a `force_search: bool` parameter and initialized a `main_messages` list based on the `MAIN_SEARCH_PROMPT`.
    *   **New:** The `force_search` parameter is removed. It now initializes specialized prompt lists for `synthesis_messages` and `memory_summary_messages`. New attributes `start_time` and `last_step_time` are added to track performance. The `SEARCH_INTENT_PROMPT` is now dynamically formatted with richer temporal context (time, date, timezone).
    *   **Impact:** This aligns the constructor with the new, specialized agent architecture and introduces performance logging capabilities from the very start of a request.

*   **`finished` Signal**
    *   **Old:** Defined as `Signal(str)`, emitting only the final response text.
    *   **New:** Defined as `Signal(str, str)`, now emitting both the full response for the UI and the condensed summary for the semantic memory.
    *   **Impact:** This change is crucial for implementing the new memory summarization workflow, decoupling what the user sees from what the system remembers.

*   **`_get_search_plan` Method**
    *   **Old:** Returned a single string containing the search plan.
    *   **New:** Now returns a tuple containing two items: the list of search topics and the classified `search_type` string (e.g., "financial").
    *   **Impact:** This is a major enhancement. The method's new output drives the entire intelligent ranking pipeline by providing the necessary context for subsequent steps.

*   **`_validate_scraped_content_batch` Method**
    *   **Old:** Took a list of scraped content and validated every piece against the single, original user prompt.
    *   **New:** Now takes a list of `(content, query)` pairs. It validates each piece of scraped content against the *specific sub-query that found it*.
    *   **Impact:** This provides a massive improvement in validation accuracy. Content is judged on its relevance to the precise topic it was searched for, not the broader, original query.

*   **`execute_search_plan` Method**
    *   **Old:** Returned a simple list of scraped content strings.
    *   **New:** Now accepts the `search_type` as a parameter to pass down to its child functions. It returns a list of `(content, query)` tuples.
    *   **Impact:** This method now acts as a critical conduit, passing the `search_type` to the ranking function and bundling the resulting content with its source query for the improved validation method.

*   **`rank_urls_by_quality` Method**
    *   **Old:** Relied on generic keyword matching (e.g., "news", "stock") within the user's query to guess at priorities.
    *   **New:** Directly accepts the classified `search_type` from the IntentAgent. It uses a large `if/elif` block to apply different, highly specific ranking rules and prioritize authoritative domains based on this type.
    *   **Impact:** This is the core of the intelligence upgrade, leading to far more relevant and trustworthy source selection.

*   **`run` Method**
    *   **Old:** Contained a large, complex `if/else` block to handle the "force search" vs. "model-decided search" paths.
    *   **New:** The logic is now a single, linear "always search" path. It starts timers for performance tracking and concludes by calling the new `_summarize_for_memory` method before emitting the `finished` signal.
    *   **Impact:** The workflow is significantly more robust, predictable, and easier to debug. It now measures its own performance and populates the memory with high-quality summaries.

*   **New Helper Methods**
    *   **`_summarize_for_memory()`:** Implements the call to the new Memory Summary Agent.
    *   **`_log_step()` & `_format_duration()`:** These methods were added to provide detailed, timed logging. Each major step in the Action Log is now appended with the time it took to complete (e.g., "Validation complete (took 15.2s)").

---

### Ⅲ. UI & User Experience (`MainWindow`) Changes

*   **Search Toggle Button**
    *   **Old:** The UI featured a "Force Search" (`⌕`) button next to the send button.
    *   **New:** This button and its associated logic have been completely removed.
    *   **Impact:** The UI is cleaner and simpler. The user no longer needs to make a decision about how the application should behave, as it now follows a single, optimized process.

*   **In-Progress Feedback**
    *   **Old:** A simple status label updated with the current step (e.g., "Searching...").
    *   **New:** In addition to the status label, a stopwatch timer (`Elapsed: 00:00`) now appears while a query is running.
    *   **Impact:** This gives the user clear, real-time feedback on how long their request is taking, which greatly improves the user experience for complex queries that may take more time.

*   **Process Robustness and Timeout**
    *   **Old:** There was no explicit timeout. A long-running or hung process could leave the application in an unresponsive state indefinitely.
    *   **New:** A 30-minute `worker_timeout_timer` is now implemented. If a request exceeds this limit, the worker thread is terminated, and a clear error message is displayed to the user.
    *   **Impact:** This makes the application significantly more stable and prevents it from becoming permanently frozen due to a network or model issue.

*   **Memory Handling in UI**
    *   **Old:** The `handle_response` function received the original user prompt and the full, verbose AI response, storing the latter directly into memory.
    *   **New:** The `handle_response` function now receives two arguments from the worker's `finished` signal: the full response (for display) and the `summary_for_memory` (for storage). It now stores the concise summary in the semantic memory.
    *   **Impact:** This completes the implementation of the new memory summarization architecture on the client side.



------------------------------------------
9_23_25
------------------------------------------



### Summary of Changes

The application underwent a major refactoring from a single, monolithic script into a well-structured, modular application. This overhaul introduced significant new features, most notably **persistent chat history**, and greatly improved maintainability, configuration, and portability. The core agent-based search logic remains similar but has been refined with better model selection and configuration management.

---

### I. Project Structure & Modularization (Major Refactoring)

The single-file application was broken down into multiple Python modules, each with a specific responsibility. This is the most significant change, improving code organization and scalability.

*   **Old Structure:** A single Python script containing all UI, logic, and data classes.
*   **New Structure:**
    *   `chorus.py` / `main.py`: A clean, minimal entry point to launch the application.
    *   `config.py`: A centralized module for all constants, model names, file paths, and application settings.
    *   `core_logic.py`: Contains the primary business logic, including the `SearchWorker` and the new `TitleWorker`.
    *   `history_manager.py`: A new module with the `HistoryManager` class, responsible for saving, loading, and managing chat sessions to a JSON file.
    *   `semantic_memory.py`: The `SemanticMemory` class was extracted into its own dedicated module.
    *   `ui/main_window.py`: The main UI class `MainWindow` was moved here.
    *   `ui/widgets.py`: Reusable UI components like `CustomTitleBar` and `MessageBubble` were extracted into this module.

---

### II. Major New Features & Functionality

*   **Persistent Chat History:**
    *   The application now saves all chat conversations to a `chat_history.json` file in the user's application data directory.
    *   A new `HistoryManager` class was introduced to handle all file I/O for creating, reading, updating, and deleting chats.
    *   The UI now features a **collapsible left-side panel** that lists all saved chat sessions, sorted by date.
    *   Users can click on a past session to load it back into the chat window.
    *   A context menu (right-click) on chat history items allows users to **Rename** or **Delete** conversations.

*   **Asynchronous Chat Titling:**
    *   A new `TitleWorker` class (in `core_logic.py`) was created.
    *   When a new chat is started, this worker runs in the background to generate a concise title for the conversation based on the first user message, preventing any UI lag.
    *   The generated title is then displayed in the history panel.

---

### III. UI Enhancements

*   **Redesigned Main Window Layout:**
    *   The UI now has a three-panel layout: a collapsible **History Panel** on the left, the main **Chat Panel** in the center, and the **Action Log** on the right.
    *   The `CustomTitleBar` was updated with a new toggle button (`❮`/`➤`) to show/hide the history panel with a smooth animation.
    *   The "New Chat" button was moved from the bottom status bar to the header of the new History Panel.
    *   A `QSizeGrip` was added to the bottom-right corner of the window for easier resizing.

*   **Chat Management:**
    *   The old "New Chat" (`clear_button`) functionality, which simply cleared the screen, has been replaced. The new "＋ New Chat" button now creates a proper new, unsaved chat session, ready to be saved upon the first message.

---

### IV. Core Logic & Agent Refinements

*   **Centralized Configuration:**
    *   All hardcoded values (model names, search parameters, file paths, UI styles) have been moved to `config.py`.
    *   This allows for easy tuning of parameters like `SCRAPE_TOP_N_RESULTS` (increased from 5 to 8) and `MAX_SOURCES_TO_SCRAPE` (increased from 2 to 3).

*   **Improved Model Management:**
    *   Specific models are now assigned to specific tasks in `config.py` (e.g., `NARRATOR_MODEL`, `INTENT_MODEL`, `SYNTHESIS_MODEL`).
    *   Smaller, faster models (e.g., `qwen2.5:3b`) are used for simpler tasks like narration and title generation, improving performance and reducing resource usage.
    *   The core logic now references these config variables instead of hardcoded model strings, making it easy to swap out models.

*   **Enhanced Portability:**
    *   The hardcoded Windows-specific file path for `System_Instructions.txt` has been replaced. The application now correctly locates this file relative to its own script directory, allowing it to run from any location on any OS.
    *   The chat history file is now stored in the standard user application data directory (`AppData`, `~/.local/share`, etc.), which is the correct cross-platform approach.

---

### V. Semantic Memory & Data Handling

*   **Separation of Memory vs. Display Content:**
    *   The `SemanticMemory.add_message` method was fundamentally changed. It now accepts `memory_content` and `display_content` separately.
    *   This allows the system to store a concise, semantically rich summary of an AI's response in memory for better future context, while still saving the full, formatted response for display in the UI.
    *   `add_message` now returns a serializable dictionary, which is then passed to the `HistoryManager` to be saved to disk.

*   **State Hydration:**
    *   A new `SemanticMemory.load_memory` method was added. This is crucial for the new history feature, as it repopulates the live semantic memory with the data from a selected chat session.

*   **Increased Robustness:**
    *   The `load_memory` method includes checks to prevent the application from crashing if it encounters corrupted or malformed message entries in the `chat_history.json` file.

---

### VI. Code-Level Changes & Fixes

*   **Dependencies:** The `pathlib` module is now used for more robust and modern path manipulation.
*   **Prompt Loading:** The `_load_prompts_from_file` method in `SearchWorker` was updated to include a check for the new `TITLE_PROMPT`.
*   **Message Handling:** The `add_message_to_ui` method in `MainWindow` now includes a check for empty `text` to avoid creating empty message bubbles.
*   **Session Management:** The `current_chat_id` state is now managed in `MainWindow` to track which conversation is active. Logic was added to `send_message`, `handle_response`, and `handle_error` to ensure messages are saved to the correct chat session.
*   **Styling:** A custom-styled `QMenu` (`QWidgetActionMenu`) was created for the history panel's context menu to match the application's theme.



------------------------
-------continue---------
------------------------



System Instructions Prompt Changes: 

### Overall Summary of Prompt Changes

The evolution from the old to the new system instructions represents a significant leap in agent sophistication and strategic depth. The core theme is a shift from simple, direct commands to establishing **stronger agent personas with highly structured, transparent thinking processes**.

*   **From Functional to Strategic:** The old prompts were functional but brittle. The new prompts force the agents to adopt specific personas (e.g., "Master Research Strategist," "Hyper-efficient Data Abstraction Agent") and follow detailed internal deliberation workflows. This results in more robust, reasoned, and debuggable outputs.
*   **Introduction of Metadata & Classification:** The new `SEARCH_INTENT_PROMPT` introduces a critical `<search_type>` classification, allowing downstream processes (like URL ranking) to become context-aware and more effective.
*   **Increased Flexibility and Intelligence:** The `VALIDATOR_PROMPT` was intentionally softened, moving from a "ruthless" filter to a more intelligent one that can recognize the value of contextually relevant information, preventing the premature rejection of useful data.
*   **New Capabilities:** A new `TITLE_PROMPT` was added to support the application's new feature of automatically titling chat sessions.

---

### Prompt-by-Prompt Change Log

#### 1. `NARRATOR_PROMPT`
*   **Status:** Minor Refinement
*   **Changes:**
    *   The prompt now explicitly mentions the application name, "Chorus," to ground the agent's identity.
    *   A new instruction was added to clarify the persona's purpose: `your persona is not overly technical, but instead to break down how the process is flowing and working to enhance the overall UX while user is waiting on the final end results.`
*   **Impact:** This refines the narrator's role from a simple technical logger to a UX-focused component. The goal is to make the action log more reassuring and understandable for a non-technical user, improving the user experience during the wait time.

---

#### 2. `SEARCH_INTENT_PROMPT`
*   **Status:** Major Overhaul
*   **Changes:**
    *   **Persona Change:** The persona was elevated from a "Research Strategist AI" to a "Master Research Strategist and Planner," emphasizing a more authoritative and strategic role.
    *   **Mandatory `<search_type>` Classification:** This is a major new requirement. The agent must now classify the user's intent into one of several categories (`historical`, `financial`, `news`, etc.).
    *   **Structured Thinking Block:** The old prompt had a vague "internal deliberation process." The new prompt mandates a highly detailed, seven-part `<thinking>` block that requires the agent to explicitly state the User Intent, Key Entities, Classification, Strategy, Constraints, Pitfalls, and Validation Method.
    *   **Strategic Principles:** The old principles were simple instructions ("be specific"). The new "Guiding Principles" are more strategic, emphasizing efficiency, logical progression, and actionability.
    *   **Temporal Context:** The new prompt is now injected with the current date and time, enabling the agent to accurately handle time-sensitive queries (e.g., "what happened yesterday?").
    *   **Topic Quantity Guidance:** New, explicit rules were added to guide the agent on generating an appropriate number of search topics (typically 4-7, but up to 12 for follow-up queries), discouraging lazy or overly complex plans.
*   **Impact:** This is the most significant change in the entire prompt suite. It transforms the agent from a simple keyword generator into a true strategic planner. The structured thinking process makes its reasoning transparent and forces a higher quality of output, while the `search_type` classification enables more intelligent search execution and source ranking in the main application logic.

---

#### 3. `VALIDATOR_PROMPT`
*   **Status:** Significant Philosophical Shift
*   **Changes:**
    *   **Softened Strictness:** The core change is the addition of bolded, capitalized instructions explicitly telling the agent **NOT** to fail content just because it isn't a direct answer. It is now instructed to `BE WISE AND USE INTELECT` and pass data that could be `ONE PIECE OF A LARGER PUZZLE`.
    *   **Temporal Awareness:** An instruction was added to account for the current year (`THE YEAR IS 2025`), preventing the agent from incorrectly failing content it perceives as "too new" based on its own knowledge cutoff.
*   **Impact:** This change fundamentally alters the validator's role from a "ruthless" binary filter to an intelligent gatekeeper. The old prompt could easily discard valuable, context-rich articles that weren't a perfect match for a specific sub-query. The new prompt allows for more nuance, improving the richness of the data that gets passed to the final synthesis agent and preventing false negatives.

---

#### 4. `REFINER_PROMPT`
*   **Status:** Unchanged
*   **Changes:** No significant changes were made.
*   **Impact:** This indicates that the original prompt for refining failed searches was already performing its function effectively and did not require modification.

---

#### 5. `ABSTRACTION_PROMPT`
*   **Status:** Heavily Overhauled
*   **Changes:**
    *   **Stronger Persona & Principles:** The persona is now a "hyper-efficient, specialized Data Abstraction Agent," and new "Core Principles" (Query-Centric, Information Density, Aggressive Noise Rejection) were added to frame the task more strictly.
    *   **More Forceful Instructions:** Vague instructions were replaced with more aggressive ones like `Ruthlessly extract` and `Discard all irrelevant information`.
    *   **New "What to AVOID" Section:** This section provides clear negative constraints, explicitly telling the agent to avoid redundancy, vague language, and opinions.
    *   **Enhanced Example with Meta-Instruction:** The example in the new prompt cleverly includes a commented-out `<!-- THOUGHT PROCESS -->` block. This shows the model *how to reason* about the task—why certain information was kept while other details (like the "new campus in Austin") were ignored.
*   **Impact:** These changes are designed to produce much cleaner, denser, and more fact-based structured data. The meta-instruction in the example is a powerful technique that significantly improves the model's ability to distinguish between signal and noise, leading to higher quality input for the final synthesis agent.

---

#### 6. `SYNTHESIS_PROMPT`
*   **Status:** Heavily Modified (Replaces implicit instruction)
*   **Changes:**
    *   The old system did not have a dedicated `SYNTHESIS_PROMPT`; this task was given implicitly after the search. The new prompt formalizes this critical step.
    *   **Explicit Prohibition:** A new rule explicitly forbids the agent from discussing the data acquisition process (e.g., "I searched the web...").
    *   **Guidance on Detail:** A new note was added at the end encouraging the agent to be `much more detailed and verbose` and not `overly simple or short`, using all the data provided to craft a comprehensive answer.
*   **Impact:** This prompt creates a more reliable and focused synthesis agent. By preventing it from talking about the search process, the final answer is cleaner and more direct. The guidance on verbosity pushes back against the tendency of LLMs to give overly concise answers, resulting in a more informative and satisfying user experience.

---

#### 7. `MEMORY_SUMMARY_PROMPT`
*   **Status:** Minor Refinement
*   **Changes:**
    *   The persona is slightly strengthened to be a "Memory Condenser agent."
    *   The explanation of its purpose is clarified to include the goal of reducing token count while retaining the core information.
*   **Impact:** A minor change that reinforces the agent's purpose, leading to slightly more consistent and concise summaries for long-term memory.

---

#### 8. `TITLE_PROMPT`
*   **Status:** New
*   **Changes:** This prompt did not exist in the old version.
*   **Impact:** This is a net-new capability that supports the new feature of automatically generating titles for chat sessions based on the user's first message, which is then displayed in the persistent history panel.

---

#### 9. `MAIN_SEARCH_PROMPT`
*   **Status:** Removed
*   **Changes:** This prompt existed in the old system but is absent in the new one.
*   **Impact:** The functionality of this prompt—deciding whether to search the web or answer from internal knowledge—has been completely absorbed and dramatically improved by the new, superior `SEARCH_INTENT_PROMPT`. The new system correctly assumes a search is the default action and focuses all its effort on creating the best possible plan from the outset, streamlining the logic.



------------------------------------------
9_25_25
------------------------------------------



### High-Level Summary of Changes

This update introduces significant new user-facing features and major under-the-hood enhancements focused on **robustness, performance, and user control**.

The two headline features are:
1.  **User-Selectable Modes:** A new UI toggle allows users to switch between the default "Search Mode" (with the full RAG pipeline) and a new "Chat Mode" for direct, search-free interaction with the LLM.
2.  **Direct URL Analysis:** Users can now paste a URL directly into the input field to have the system scrape, analyze, and answer questions about that specific page, bypassing the search planning phase.

Under the hood, the application has been hardened significantly with the implementation of **timeouts and retry mechanisms for all Ollama API calls**, preventing hangs and improving reliability. Configuration has also been expanded for finer control over performance.

---

### I. Major New Features

#### 1. Search vs. Chat Mode
A user-selectable mode has been introduced, allowing for two distinct types of interaction:
*   **Search Mode (Default):** The standard, multi-agent RAG pipeline that plans, searches the web, validates, and synthesizes information.
*   **Chat Mode:** A direct-to-LLM mode that bypasses the entire search and retrieval pipeline. This is ideal for general conversation, creative tasks, or querying the model's internal knowledge without web access.
    *   **Implementation:**
        *   **UI (`uimain_window.py`):** A new toggle button (`mode_toggle_button`) has been added to the footer, allowing users to switch between "🌐 Search Mode" and "💬 Chat Mode". The input field placeholder text updates accordingly.
        *   **State Management (`uimain_window.py`):** A new state variable, `self.current_mode`, tracks the selected mode.
        *   **Core Logic (`core_logic.py`):** The `SearchWorker` now accepts a `mode` parameter. Its `run()` method contains a new primary conditional branch: if `mode` is "chat", it skips directly to knowledge-based generation; if `mode` is "search", it executes the full RAG pipeline.

#### 2. Direct URL Analysis
The system can now automatically detect when a user provides a URL, triggering a specialized workflow.
*   **Functionality:** If a user's prompt contains a URL, the system will bypass the `IntentAgent` and directly scrape the content of that single URL. It will then proceed with the abstraction and synthesis steps to answer questions about the page's content.
    *   **Implementation:**
        *   **URL Detection (`core_logic.py`):** A new `_find_url_in_query()` helper function was added.
        *   **Intent Bypass (`core_logic.py`):** The `_get_search_plan()` method now first checks for a URL. If found, it immediately returns a plan with `search_type="direct"`, skipping the expensive call to the `IntentAgent`.
        *   **Specialized Execution (`core_logic.py`):** The `execute_search_plan()` method now has a specific handler for `search_type="direct"` to perform a single scrape instead of a web search. The `run()` method also bypasses the validation step for direct URL scrapes.

---

### II. Robustness & Performance Enhancements

This update introduces major stability improvements, making the application far more resilient to model or network issues.

#### 1. Timeout and Retry Logic for All Ollama Calls
All blocking calls to the Ollama API have been wrapped in robust handlers to prevent the application from hanging indefinitely.
*   **Implementation (`core_logic.py`):**
    *   The `concurrent.futures` library is now used to run Ollama API calls in a separate thread with a configurable timeout.
    *   **`get_ollama_response()`:** Now uses `ThreadPoolExecutor` with a `OLLAMA_DEFAULT_TIMEOUT` (10 minutes). It will retry up to 2 times on timeout or failure.
    *   **`_validate_scraped_content_batch()`:** The validator, which is more prone to issues, now has a much shorter `OLLAMA_VALIDATION_TIMEOUT` (90 seconds) and will retry up to 3 times per source. This prevents a single faulty source validation from stalling the entire process.
    *   **`_structure_scraped_data_batch()`:** The abstraction agent now includes a retry loop (2 attempts) to handle intermittent failures.

#### 2. More Nuanced Validation Logic
The logic for determining if a search was "successful" after validation has been improved.
*   **Implementation (`core_logic.py`):**
    *   The condition for proceeding to synthesis is now more flexible: `(num_passed >= 2) or (num_scraped <= 2 and num_passed >= 1)`. This means the process can continue if it finds at least one good source when only one or two were scraped, which is a common scenario. This logic is applied to both the initial and refined search steps.

#### 3. Optimized Scraping Content Length
*   **Implementation (`core_logic.py`):** In `scrape_with_enhanced_extraction()`, the maximum number of characters scraped from a single page has been reduced from `12000` to `4000`. This reduces the token load on the abstraction and synthesis models, improving performance and helping to stay within context limits.

---

### III. UI & UX Improvements

#### 1. Redesigned Footer
The footer area has been redesigned for better organization and to accommodate the new mode toggle.
*   **Implementation (`uimain_window.py`):**
    *   The `status_label` and `timer_label` have been moved up into a new `mode_status_layout` alongside the new mode toggle button.
    *   A new `bottom_bar_layout` was created at the very bottom of the window to house a new disclaimer message and the `QSizeGrip`.
    *   **Disclaimer:** A small, italicized label now sits in the footer: *"Please double check vital details. We strive for reliability but no system is perfect."*

---

### IV. Core Logic & Pipeline Refinements

#### 1. Prompt Loading Refactored
*   **Implementation:** The `load_prompts_from_file` function was moved out of the `SearchWorker` class and into the top level of `core_logic.py`. It is now called once at startup in `MainWindow.__init__`, and the loaded prompts are passed to workers as needed. This is more efficient as the file is now read only once per application launch, not once per query.

#### 2. Improved Memory Summarization
*   **Implementation (`core_logic.py`):** The logic in the `run()` method for creating the `summary_for_memory` is now smarter. If a response was generated without web sources (e.g., in Chat Mode), it creates a simpler, more direct summary of the conversation turn instead of invoking the `MemorySummaryAgent`.

#### 3. Better Context in Chat History
*   **Implementation (`core_logic.py`):** In the `run()` method, the `retrieve_relevant_messages` call now requests the `last_n=4` messages instead of 2, providing slightly more conversational context to the agents.

---

### V. Configuration Changes (`config.py`)

*   **Model Upgrade:**
    *   `SYNTHESIS_MODEL` has been upgraded from `qwen3:8b` to **`qwen3:14b`**, dedicating more power to generating the final, high-quality answer.
*   **Increased Search Scope:**
    *   `SCRAPE_TOP_N_RESULTS` was increased from `8` to **`10`**.
    *   `MAX_SOURCES_TO_SCRAPE` was increased from `3` to **`5`**.
    This allows the system to consider a wider pool of information before validation.
*   **New Timeout Constants:**
    *   `OLLAMA_VALIDATION_TIMEOUT = 90`
    *   `OLLAMA_DEFAULT_TIMEOUT = 600`
    These new constants centralize the timeout values used in the new robustness features.
