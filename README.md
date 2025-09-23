# Chorus: A Multi-Agent AI Research Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/Qt-PySide6-brightgreen.svg)
![Ollama](https://img.shields.io/badge/LLM-Ollama-252526.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

---
Audio Overview of Original Version: https://notebooklm.google.com/notebook/cbf76f05-313c-47a9-8a30-3beaf7f34610?artifactId=029bfd23-4d50-479d-a819-7a53a285b060
---

An open-source, privacy-first alternative to Perplexity & ChatGPT’s web search mode, powered by local models, a multi-agent architecture, and real-time web access. It can run effectively on consumer-grade hardware with as little as 12GB of VRAM (e.g., a single GEFORCE RTX 3060 GPU).

Chorus doesn’t just answer questions—it *reasons*. It operates a sophisticated workflow where a **chorus of specialized AI agents** collaborate to plan, search, validate, abstract, and synthesize information. It runs entirely on your local machine, ensuring every interaction is secure, private, and radically transparent.

-   **Persistent Chat History:** Automatically saves all conversations. Load, rename, or delete past chats from a dedicated history panel.
-   **Current, Factual Answers:** Fetches and synthesizes information from live web searches for up-to-the-minute accuracy.
-   **Verifiable & Trustworthy:** Provides source citations for every answer, allowing you to trace information back to its origin.
-   **100% Private:** No data, queries, or conversations ever leave your computer.
-   **Radical Transparency:** A unique **Narrator Agent** provides a human-like, running commentary on the AI's internal thought process in a live-updating action log.
-   **Hybrid Contextual Memory:** Remembers both short-term conversational flow and long-term semantic context within each chat session.

Think of it as your own **local, autonomous research team**: more accurate than a standard chatbot, more transparent than any commercial alternative, and completely in your control.

**[NOTE: The screenshots and GIF below are from a previous version. Please update them to reflect the new UI with the history panel.]**

![Untitled video - Made with Clipchamp (9)](https://github.com/user-attachments/assets/1c3b0b4f-a18c-4712-95c7-d76377671aae)
<img width="1468" height="850" alt="Screenshot 2025-09-23 134620" src="https://github.com/user-attachments/assets/65d8d6f2-ef53-477a-9656-75045cec0f74" />
<img width="1468" height="850" alt="Screenshot 2025-09-23 134636" src="https://github.com/user-attachments/assets/b935a702-144d-4637-8fe8-efa4971a44c6" />

---

## Architectural Deep Dive: The Journey of a Query

The sophistication of Chorus lies in its modular, multi-agent pipeline. Each user query initiates a journey through a series of specialized agents and logic gates, ensuring the final output is the product of a rigorous, verifiable process, with all interactions saved for future reference.

### Step 1: Strategic Deconstruction & Planning

Before any action is taken, the **`IntentAgent`** acts as a master strategist.

-   **Deep Conversational Context:** The agent is provided with a rich, hybrid context from the `SemanticMemory`, loaded specifically for the active chat session. This includes a guaranteed recall of the last few turns and semantically-retrieved relevant messages from the session's history.
-   **Search Type Classification:** The agent doesn't just generate search terms; it first classifies the user's intent (e.g., `historical`, `financial`, `tech`). This crucial metadata allows the search process to prioritize the most relevant types of sources.
-   **Structured Plan Generation:** The `IntentAgent`'s primary output is a structured plan. It deconstructs a complex query into a series of discrete, machine-friendly search topics, transforming a nuanced human request into an actionable research strategy.

### Step 2: Intelligent & Adaptive Information Retrieval

With a clear plan, the framework deploys its "scout" capabilities, prioritizing signal over noise from the open web.

-   **Context-Aware Source Ranking:** Using the `search_type` from the planning phase, the system uses a sophisticated ranking algorithm to prioritize search results, applying a weighted score based on domain authority and relevance to the query's classification.
-   **Resilient Search Strategy:** The system employs a "narrow-to-broad" fallback mechanism. If a domain-targeted search fails, it automatically re-executes the search on the wider web.
-   **Robust Content Extraction:** A two-stage extraction process uses a high-precision library (`trafilatura`) first, then falls back to a more aggressive HTML parser to guarantee text is extracted from various web page structures.

### Step 3: Intelligent Quality Control

Chorus operates on a "trust but verify" principle: all information is considered unreliable until it passes an intelligent validation stage.

-   **The Dedicated `ValidatorAgent`:** Each scraped source is passed to this agent to be checked for relevance and depth.
-   **Nuanced Filtering:** The validation process is no longer a ruthless binary gate. The `ValidatorAgent` is now instructed to pass content that, while not a direct answer, provides valuable context that contributes to the larger puzzle, preventing the premature rejection of useful data.

### Step 4: Multi-Stage Synthesis & Self-Correction

The system is a dynamic framework with internal feedback loops that allow it to adapt and recover from failure.

-   **The Refinement Loop (Failure Recovery):** If all initial sources are rejected, the system invokes a **`RefinerAgent`**. This agent is given the failed query and the specific reasons for rejection to construct a new, more intelligent search plan.
-   **The Augmentation Loop (Information Gaps):** The final **`SynthesisAgent`** can request more information. If it determines a critical detail is missing, it can issue a request for an `<additional_search>`, triggering a new, targeted search-and-validate cycle.

### Step 5: Persistent & Semantic Memory

Underpinning the entire application is a dual-component memory system that provides both long-term persistence and powerful in-session context.

-   **`HistoryManager` (The Librarian):** This new class is responsible for all file I/O, saving every chat session—including user prompts, AI responses, and memory summaries—to a local JSON file. It manages the creation, loading, and deletion of conversations.
-   **`SemanticMemory` (The Working Memory):** When a chat is loaded, its history is used to "hydrate" the `SemanticMemory` class. This class uses vector embeddings to operate on conceptual meaning, not just keywords, allowing it to provide deep contextual understanding for the agents working on the current query.

## The Chorus of Agents

Chorus's intelligence comes from a structured workflow orchestrated between several specialized AI agents.

1.  **Intent Agent (The Planner):** Analyzes the user's query and context to produce a classified, actionable search plan.
2.  **Validator Agent (The Intelligent Filter):** Critically evaluates each scraped web source, passing content that is either directly relevant or provides valuable context.
3.  **Refiner Agent (The Problem Solver):** If all initial results are rejected, this agent analyzes the failure feedback to generate an improved search plan.
4.  **Abstraction Agent (The Data Extractor):** Processes each *validated* source, ruthlessly extracting key facts and structuring the raw text into a clean, dense format.
5.  **Synthesis Agent (The Author):** Receives structured data from all validated sources and synthesizes it into a final, cohesive, user-facing answer.
6.  **Narrator Agent (The Commentator):** Provides a running, human-like monologue in the Action Log, transparently explaining what the system is doing at each step.
7.  **Title Agent (The Archivist):** A new, lightweight agent that runs in the background to generate a concise title for new conversations, keeping the chat history organized.

## Technology Stack

-   **Backend:** Python 3.10+
-   **GUI Framework:** PySide6
-   **LLM Engine:** Ollama
-   **Web Search:** `duckduckgo-search`
-   **Web Scraping & Extraction:** `requests`, `BeautifulSoup4`, `trafilatura`
-   **Vector Math (for Semantic Memory):** `numpy`

## Getting Started

Follow these instructions to get Chorus running on your local machine.

#### Prerequisites

1.  **Python:** Ensure you have Python 3.10 or newer installed.
2.  **Ollama:** You must have [Ollama](https://ollama.com/) installed and running on your system.
3.  **Required Ollama Models:** The application relies on a specific set of models for its agentic stack. Pull them using the following commands. **Note:** A GPU with ~12GB of VRAM is recommended to run the full stack smoothly.

    ```bash
    # For main synthesis and refinement agents (largest model)
    ollama pull qwen3:14b

    # For planning, abstraction, and validation agents (medium model)
    ollama pull qwen3:8b
    
    # For memory summaries (medium model)
    ollama pull qwen2.5:7b-instruct

    # For fast, lightweight narration and title generation (smallest model)
    ollama pull qwen2.5:3b

    # For generating vector embeddings for semantic memory
    ollama pull nomic-embed-text
    ```

#### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/Chorus.git
    cd Chorus
    ```

2.  **Install Dependencies:**
    It is highly recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

    # Install the required packages
    pip install -r requirements.txt
    ```
    If a `requirements.txt` file is not available, install packages directly:
    ```bash
    pip install PySide6 ollama numpy requests duckduckgo-search beautifulsoup4 trafilatura markdown2
    ```

#### Running the Application

Once the prerequisites are met and dependencies are installed, start the application:

```bash
python chorus.py 
```

## Usage Guide

-   **Three-Panel Layout:**
    -   **History Panel (Left):** Lists all your saved conversations. Click an item to load the chat. Right-click for options to **Rename** or **Delete**.
    -   **Chat Interface (Center):** The main window where you interact with the AI.
    -   **Action Log (Right):** Provides a detailed, real-time log of the AI's internal process. Look for the *italic blue entries* from the **Narrator Agent** for a high-level summary.
-   **Starting a New Chat:** Click the "**＋ New Chat**" button in the history panel header to begin a new, unsaved conversation. The chat will be automatically saved and titled after you send your first message.
-   **Expandable Details:** Responses may include "Thinking Process" and "Sources" buttons. Click these to see the agent's reasoning and view the source citations.

## Contributing

Contributions are welcome! If you have suggestions for improvements or encounter any bugs, please feel free to open an issue or submit a pull request.

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/NewFeature`).
3.  Commit your changes (`git commit -m 'Add a new feature'`).
4.  Push to the branch (`git push origin feature/NewFeature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
