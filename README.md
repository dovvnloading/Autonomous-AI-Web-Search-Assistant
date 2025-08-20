# Autonomous AI Web Search Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/Qt-PySide6-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)


---

This repository contains the source code for a sophisticated, locally-run Autonomous AI Web Search Assistant. Built with Python and PySide6, this application leverages a multi-agent system powered by local language models via Ollama to provide real-time, context-aware, and verifiable answers to user queries by actively searching the web.

Unlike traditional chatbots, this assistant uses an internal chain of thought to plan, execute, validate, and synthesize information from web sources, providing users with accurate, up-to-date responses complete with source citations.

![Untitled video - Made with Clipchamp (3)](https://github.com/user-attachments/assets/68b44701-85b0-4450-9deb-4b97a1113e66)

<img width="1226" height="816" alt="Screenshot 2025-08-15 142825" src="https://github.com/user-attachments/assets/bfdab3b5-ed80-4af1-b15d-ecd889886f05" />

## Features

-   **Agentic Architecture:** Utilizes a multi-agent system where specialized AI agents collaborate to handle different stages of a request: query analysis, search planning, content validation, and response synthesis.
-   **Real-Time Web Access:** Integrates with DuckDuckGo Search to fetch live information from the internet, ensuring answers are current and not limited to the model's training data.
-   **Content Validation & Refinement:** An independent Validator Agent assesses the quality and relevance of scraped web content. If the content is poor, the system can automatically trigger a refined search to find better information.
-   **Verifiable Source Citations:** Every web-sourced answer is accompanied by a list of the exact URLs used, including the article title and publication date, promoting transparency and allowing for fact-checking.
-   **Advanced Hybrid Memory:** The assistant possesses both guaranteed short-term memory for conversational follow-ups and semantic long-term memory for recalling context from earlier in the conversation. This allows for natural dialogue and effective error correction (e.g., "That result wasn't good enough, try looking for a more recent source").
-   **100% Local and Private:** All AI processing is handled locally through Ollama. Your conversations and data never leave your machine.
-   **Transparent Operation:** A detailed Action Log in the user interface provides a real-time stream of the agent's internal monologue, decisions, search queries, and validation results.

## Core Architecture

The assistant's intelligence comes from a structured, multi-step workflow orchestrated between several specialized agents.

#### The Multi-Agent System

1.  **Search Intent Agent (Planner):** This agent acts as the initial strategist. It receives the user's query *and* the recent conversational context. Its sole job is to analyze the user's true intent and decompose it into a clear, actionable `<search_plan>`. For conversational commands like "try again," it uses the provided history to understand what to retry.
2.  **Main Search Agent (Orchestrator):** The core agent that manages the entire process. It uses the `<search_plan>` to formulate precise search requests, interacts with the search and scrape tools, receives the data, and synthesizes the final, user-facing response.
3.  **Validator Agent (Quality Control):** After web content is scraped, this agent critically evaluates it against the original user query. It provides a simple `<pass>` or `<fail>` judgment, ensuring that only relevant, high-quality information is used for the final answer.

#### The Workflow: From Query to Answer

1.  **User Input:** The user submits a query. The "Force Search" toggle can be used to compel the system to access the web.
2.  **Intent Analysis:** The Search Intent Agent receives the query and chat history, then produces a structured search plan.
3.  **Search Execution:** The Main Agent executes the search plan, using intelligent ranking to prioritize reliable domains (e.g., reputable news sites for current events, financial sites for stock data).
4.  **Content Extraction:** The system scrapes and cleans the content from the top-ranked source URLs using `trafilatura` for high-precision text extraction.
5.  **Validation:** The Validator Agent inspects the scraped content. If it fails validation, the system can automatically attempt a refined search.
6.  **Synthesis:** Once validated content is available, the Main Agent synthesizes all the information into a comprehensive, well-formatted Markdown answer.
7.  **Citation:** The final response is appended with a list of all sources used in the `<sources>` tag.

## Technology Stack

-   **Backend:** Python 3
-   **GUI:** PySide6
-   **LLM Engine:** Ollama
-   **Web Search:** `duckduckgo-search`
-   **Web Scraping & Extraction:** `requests`, `BeautifulSoup`, `trafilatura`
-   **Vector Math:** `numpy`

## Getting Started

Follow these instructions to get the AI assistant running on your local machine.

#### Prerequisites

1.  **Python:** Ensure you have Python 3.8 or newer installed.
2.  **Ollama:** You must have [Ollama](https://ollama.com/) installed and running.

3.  **Required Ollama Models:** The application relies on specific models for its agentic stack. Pull them using the following commands:

    ```bash
    # For the main agent (synthesis and reasoning)
    ollama pull qwen3:14b

    # For the support agents (planning and validation)
    ollama pull qwen3:8b

    # For generating embeddings for semantic memory
    ollama pull nomic-embed-text
    ```

#### Installation

1.  Clone the repository to your local machine:
    ```bash
    git clone https://github.com/dovvnloading/Autonomous-AI-Web-Search-Assistant.git
    cd Autonomous-AI-Web-Search-Assistant
    ```

2.  Install the required Python packages directly using pip:
    ```bash
    pip install PySide6 ollama numpy requests duckduckgo_search beautifulsoup4 trafilatura markdown2
    ```

#### Running the Application

Once the prerequisites and dependencies are installed, you can start the application by running:

```bash
python Ai_Web_Search.py
```

## Usage

-   **Chat Interface:** The main window on the left is the chat interface. Your messages appear on the right, and the AI's responses appear on the left.
-   **Action Log:** The panel on the right provides a detailed, real-time log of the AI's actions, thoughts, and the data it's processing. This is invaluable for understanding its decision-making process.
-   **Force Search Toggle:** The magnifying glass button (`⌕`) next to the input field is the Force Search toggle.
    -   **Disabled (Default):** The AI decides whether a search is necessary based on the query.
    -   **Enabled (Highlighted):** Forces the AI to use the Search Intent Agent and perform a web search, even if it thinks it knows the answer. This is useful for getting the absolute latest information.
-   **New Chat:** The "New Chat" button clears the conversation history and the AI's semantic memory, allowing you to start a fresh topic.

## Contributing

Contributions are welcome. If you have suggestions for improvements or encounter any bugs, please feel free to open an issue or submit a pull request.

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature`).
3.  Commit your changes (`git commit -m 'Add some feature'`).
4.  Push to the branch (`git push origin feature/YourFeature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License.
