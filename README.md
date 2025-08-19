# Autonomous AI Web Search Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/Qt-PySide6-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

An intelligent desktop application that enhances local LLMs with real-time, autonomous web search capabilities. This project implements a sophisticated Retrieval-Augmented Generation (RAG) system using a **multi-agent architecture** to deliver accurate, up-to-date, and fully cited answers.

 
<img width="1272" height="804" alt="Screenshot 2025-08-19 072814" src="https://github.com/user-attachments/assets/32b76a4f-eaf3-46a8-b6c5-183a97f2b671" />


## About The Project

This application transforms a standard local Large Language Model (like Qwen3, Llama, or Mistral) into a powerful research assistant. It goes beyond simple context-stuffing by employing a team of specialized AI agents that collaborate to understand user intent, plan searches, validate information quality, and synthesize comprehensive answers.

The core principle is **autonomy**: the AI decides *when* to search the web, *what* to search for, and whether the information it finds is trustworthy and relevant.

---

## Key Features

🧠 **Multi-Agent Autonomous System**
*   **Search Intent Agent**: Decomposes complex user queries into a clear, structured search plan.
*   **Main Search Agent**: The orchestrator that analyzes queries, manages conversation history, and decides whether to use its base knowledge or execute a web search.
*   **Content Validator Agent**: Acts as a quality gatekeeper, programmatically reading scraped web content and rejecting it if it's off-topic, outdated, or low-quality.

🔍 **Intelligent Web RAG (Retrieval-Augmented Generation)**
*   **Dynamic Search**: Automatically triggers web searches for queries involving current events, news, stock prices, or recent data.
*   **Smart Source Ranking**: Prioritizes authoritative domains (e.g., Reuters for news, Yahoo Finance for stocks) to improve the quality of search results.
*   **High-Fidelity Content Scraping**: Uses `trafilatura` to precisely extract the main article content, filtering out ads and boilerplate.
*   **Self-Correcting Search**: If the initial search fails the validation step, the system automatically attempts a refined search with a modified query.

✍️ **Semantic Memory**
*   Utilizes `nomic-embed-text` to create vector embeddings for every message in the conversation.
*   Performs a cosine similarity search to retrieve the most contextually relevant past messages, giving the AI a robust long-term memory.

🖥️ **Modern Desktop UI**
*   Built with **PySide6** (Qt for Python) for a responsive, cross-platform experience.
*   **Fully Asynchronous**: All AI processing and web scraping runs on a background thread, keeping the UI smooth and responsive.
*   **Interactive & Transparent**:
    *   Collapsible sections for viewing the AI's detailed **"Thinking Process"**.
    *   Clickable, neatly formatted **source citations** for every web-augmented answer.
*   **Live Action Log**: A dedicated panel shows the step-by-step internal monologue and actions of the entire agentic system.

---

## How it Works: The Agentic Workflow

The application follows a structured chain of thought to answer a query that may require web access.

1.  **Query Input**: The user submits a query.
2.  **Intent Decomposition**: If "Search Mode" is enabled, the `Search Intent Agent` first breaks down the query into a `<search_plan>` of distinct topics.
3.  **Planning Phase**: The `Main Agent` receives the query (and the plan), consults the semantic memory for context, and decides if a search is needed. It formulates a precise query inside `<search_request>` tags.
4.  **Execution**: The application parses the `<search_request>` and uses `ddgs` to search the web, then scrapes the top-ranked URLs.
5.  **Validation**: The scraped content is passed to the `Content Validator Agent`, which checks its relevance against the original user query and returns a `<pass>` or `<fail>` judgment.
6.  **Refinement (if needed)**: If validation fails, the system triggers a new, refined search. If it still fails, it defaults to using the LLM's base knowledge.
7.  **Synthesis**: With validated content, the `Main Agent` synthesizes a comprehensive, Markdown-formatted answer, embedding the sources directly in the response.

---

## Tech Stack

*   **Backend**: Python
*   **AI/LLM**: `ollama` for local model hosting.
    *   **Chat Models**: `qwen3:14b` (Main Synthesis), `qwen3:8b` (Agents)
    *   **Embedding Model**: `nomic-embed-text`
*   **GUI**: `PySide6` (Qt6)
*   **Web Scraping**: `requests`, `trafilatura`, `BeautifulSoup4`
*   **Search**: `ddgs` (DuckDuckGo Search)
*   **Data Handling**: `NumPy`

---

## Getting Started

Follow these steps to get the application running on your local machine.

### Prerequisites

1.  **Python**: Ensure you have Python 3.9+ installed.
2.  **Ollama**: You must have [Ollama](https://ollama.com/) installed and running.
3.  **Required Models**: Pull the necessary models from the Ollama library.
    ```sh
    ollama pull qwen3:14b
    ollama pull qwen3:8b
    ollama pull nomic-embed-text
    ```

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/autonomous-ai-search.git
    cd autonomous-ai-search
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```sh
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  **Install the required Python packages:**
    ```sh
    pip install PySide6 ollama numpy markdown2 trafilatura beautifulsoup4 ddgs requests
    ```
4.  **Run the application:**
    ```sh
    python app.py 
    ```
    *(Assuming you have saved the code as `app.py`)*

## Usage

*   **Ask a Question**: Type your query in the input box and press Enter or the send button.
*   **Toggle Search Mode**: Click the search icon (**⌕**) to enable "Force Search Mode." When enabled (glowing green), every query will be analyzed by the `Search Intent Agent` for a more thorough, decomposed search. When disabled, the `Main Agent` decides on its own whether to search.
*   **View Sources**: For answers generated from web content, click the "Sources" button to expand a list of clickable links.
*   **Inspect Thinking**: Click the "Thinking Process" button to see the AI's internal monologue and plan before it acted.
*   **New Chat**: Click "✨ New Chat" to clear the conversation history and semantic memory.
