# Autonomous AI Web Search Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/Qt-PySide6-brightgreen.svg)
![Ollama](https://img.shields.io/badge/LLM-Ollama-252526.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

---

An open-source, privacy-first alternative to Perplexity & ChatGPT’s web search mode, powered by local models, a multi-agent architecture, and real-time web access.

This assistant doesn’t just answer questions—it reasons. It operates a chain of thought involving **planning, searching, validating, and citing** its sources for every web-enabled query. It runs entirely on your local machine, ensuring that every interaction is secure, private, and transparent.

-   **Current, Factual Answers:** Fetches and synthesizes information from live web searches.
-   **Verifiable & Trustworthy:** Provides deterministic, accurate source citations for every answer.
-   **100% Private:** No data, queries, or conversations ever leave your computer.
-   **Agentic Reasoning:** Specialized AI agents collaborate to plan, execute, and validate information.
-   **Hybrid Contextual Memory:** Remembers both short-term conversational flow and long-term semantic context.

Think of it as your own **local, autonomous research agent**: more accurate than a standard chatbot and completely in your control.

![Demo Video](https://github.com/user-attachments/assets/68b44701-85b0-4450-9deb-4b97a1113e66)
<br>
<img alt="Screenshot of the Application" src="https://github.com/user-attachments/assets/fb98b86d-7b24-4217-9b84-fe3b0c5ed064" width="1100" />

---

## Key Innovations

-   **Multi-Agent Architecture:** A system of specialized AI agents collaborates to handle different stages of a request: query analysis, search planning, content validation, and response synthesis. This division of labor leads to more accurate and reliable outcomes.

-   **Deterministic Source Citation:** Unlike other systems that ask the LLM to cite its sources (often leading to errors or omissions), this application **programmatically tracks and injects citations**. Source data (URL, title, date) is captured during the scraping phase and attached to the final response by the application code, guaranteeing 100% accuracy and reliability.

-   **Content Validation & Refinement Loop:** An independent Validator Agent assesses the quality and relevance of scraped web content. If the information is deemed insufficient or off-topic, the system automatically triggers a refined search to find better sources, improving the quality of the final answer.

-   **Advanced Hybrid Memory:** The assistant leverages a dual-memory system:
    -   **Short-Term:** Guarantees recall of the last few turns of conversation for immediate context.
    -   **Long-Term Semantic:** Embeds the chat history into a vector space, allowing it to recall semantically relevant information from much earlier in the conversation. This enables natural dialogue and effective error correction (e.g., *"That result wasn't good enough, find a more recent source."*).

-   **Transparent Reasoning:** The UI includes a detailed **Action Log** that provides a real-time stream of the agent's internal monologue, decisions, search queries, and validation results, offering complete transparency into its operational process.

## How It Works: The Agentic Workflow

The assistant's intelligence comes from a structured, multi-step workflow orchestrated between several specialized AI agents.

#### The Multi-Agent System

1.  **Search Intent Agent (The Planner):** This agent acts as the strategist. It receives the user's query and the conversational context. Its sole purpose is to analyze the user's true intent and decompose it into a clear, actionable `<search_plan>`.
2.  **Main Search Agent (The Orchestrator):** The core agent that manages the entire workflow. It uses the `<search_plan>` to formulate precise search requests, interacts with search tools, processes the data, and synthesizes the final, user-facing response.
3.  **Validator Agent (The Quality Controller):** After web content is scraped, this agent critically evaluates it against the original user query. It returns a simple `<pass>` or `<fail>` judgment, ensuring that only relevant, high-quality information is used to generate the answer.

#### From Query to Answer: A Step-by-Step Breakdown

1.  **User Input:** The user submits a query. The "Force Search" toggle can be used to compel the system to access the web.
2.  **Intent Analysis:** The **Search Intent Agent** analyzes the query and chat history, then produces a structured search plan.
3.  **Search Execution:** The **Main Agent** executes the plan, using an intelligent URL ranking system to prioritize reliable domains (e.g., reputable news sites for current events, financial sites for market data).
4.  **Content Extraction:** The system scrapes and cleans the content from the top-ranked URLs using `trafilatura` for high-precision text extraction. During this step, it saves the **ground-truth source information** (URL, title, date) as structured data.
5.  **Validation:** The **Validator Agent** inspects the scraped content. If it fails, the system attempts a refined search to find better sources.
6.  **Synthesis:** Once validated content is available, the **Main Agent** synthesizes the information into a comprehensive, well-formatted Markdown answer.
7.  **Deterministic Citation:** Finally, the application code itself—**not the LLM**—appends a perfectly formatted `<sources>` block to the response, using the ground-truth data captured in step 4.

## Technology Stack

-   **Backend:** Python 3.10+
-   **GUI Framework:** PySide6
-   **LLM Engine:** Ollama
-   **Web Search:** `duckduckgo-search`
-   **Web Scraping & Extraction:** `requests`, `BeautifulSoup4`, `trafilatura`
-   **Vector Math (for Semantic Memory):** `numpy`

## Getting Started

Follow these instructions to get the AI assistant running on your local machine.

#### Prerequisites

1.  **Python:** Ensure you have Python 3.10 or newer installed.
2.  **Ollama:** You must have [Ollama](https://ollama.com/) installed and running on your system.
3.  **Required Ollama Models:** The application relies on specific models for its agentic stack. Pull them using the following commands in your terminal:

    ```bash
    # For the main orchestrator agent (synthesis and reasoning)
    ollama pull qwen2:7b

    # For the specialized support agents (planning and validation)
    ollama pull qwen2:1.5b

    # For generating vector embeddings for semantic memory
    ollama pull nomic-embed-text
    ```

#### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/Autonomous-AI-Web-Search-Assistant.git
    cd Autonomous-AI-Web-Search-Assistant
    ```

2.  **Install Dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment (optional but recommended)
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
python Ai_Web_Search.py
```

## Usage Guide

-   **Chat Interface:** The main window on the left is where you interact with the AI. Your messages appear on the right; the AI's responses appear on the left.
-   **Action Log:** The panel on the right provides a detailed, real-time log of the AI's internal state, including agent handoffs, search queries, validation results, and memory access.
-   **Force Search Toggle:** The magnifying glass button (`⌕`) next to the input field forces a web search.
    -   **Disabled (Default):** The AI decides if a search is needed.
    -   **Enabled (Highlighted Green):** Forces the AI to use its search agents, guaranteeing the most current information.
-   **Expandable Details:** Responses may include "Thinking Process" and "Sources" buttons. Click these to see the agent's internal monologue and view the source citations.
-   **New Chat:** The "New Chat" button clears the conversation and the AI's memory, allowing you to start a fresh session.

## Contributing

Contributions are welcome! If you have suggestions for improvements or encounter any bugs, please feel free to open an issue or submit a pull request.

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/NewFeature`).
3.  Commit your changes (`git commit -m 'Add a new feature'`).
4.  Push to the branch (`git push origin feature/NewFeature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
