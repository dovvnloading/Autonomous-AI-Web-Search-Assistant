# Chorus: A Multi-Agent AI Research Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/Qt-PySide6-brightgreen.svg)
![Ollama](https://img.shields.io/badge/LLM-Ollama-252526.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

---

An open-source, privacy-first alternative to Perplexity & ChatGPT’s web search mode, powered by local models, a multi-agent architecture, and real-time web access.

Chorus doesn’t just answer questions—it *reasons*. It operates a sophisticated workflow where a **chorus of specialized AI agents** collaborate to plan, search, validate, abstract, and narrate the entire process of finding and synthesizing information. It runs entirely on your local machine, ensuring every interaction is secure, private, and radically transparent.

-   **Current, Factual Answers:** Fetches and synthesizes information from live web searches.
-   **Verifiable & Trustworthy:** Provides deterministic, accurate source citations for every answer.
-   **100% Private:** No data, queries, or conversations ever leave your computer.
-   **Radical Transparency:** A unique **Narrator Agent** provides a human-like, running commentary on the AI's internal thought process.
-   **Hybrid Contextual Memory:** Remembers both short-term conversational flow and long-term semantic context.

Think of it as your own **local, autonomous research team**: more accurate than a standard chatbot, more transparent than any commercial alternative, and completely in your control.

![Untitled video - Made with Clipchamp (7)](https://github.com/user-attachments/assets/bce07038-1c9c-4994-8557-1cf9ace0fc66)

---

<img width="1100" height="750" alt="Screenshot 2025-08-22 134740" src="https://github.com/user-attachments/assets/e90fd8c2-a75f-48fc-910a-3fdd421cbe0a" />


---


<img width="1100" height="750" alt="Screenshot 2025-08-22 134815" src="https://github.com/user-attachments/assets/65ddf6bc-3279-48af-94f6-f0edcd84889e" />

---

<img width="1100" height="750" alt="Screenshot 2025-08-22 135904" src="https://github.com/user-attachments/assets/aea72000-3b65-44a4-b98e-1f62192fb1a8" />


---

<img width="1100" height="750" alt="Screenshot 2025-09-18 120239" src="https://github.com/user-attachments/assets/74048279-2126-4088-ab89-2b4dbdfdbc59" />


---

<img width="1100" height="750" alt="Screenshot 2025-09-19 115835" src="https://github.com/user-attachments/assets/b37e5328-43e2-468b-8c73-9d3b2302fe4a" />

---

<img width="1100" height="750" alt="Screenshot 2025-09-19 120054" src="https://github.com/user-attachments/assets/302c1778-2fa9-485e-8688-8aa4ebbd2dc5" />


---

<img width="1100" height="750" alt="Screenshot 2025-09-19 120025" src="https://github.com/user-attachments/assets/d66a5a33-bebf-4a93-82f7-4c35d03957b2" />


---

## Key Innovations

-    **You can run this on a single 3090 with less than 16gb Ram!!**

-   **The Chorus of Agents:** This is not a monolithic AI. Chorus operates a sophisticated system where specialized AI agents collaborate to handle each stage of a request. This division of labor leads to more intelligent, robust, and reliable outcomes.

-   **The Narrator Agent:** A groundbreaking feature for transparency. A dedicated, lightweight AI agent observes the entire workflow and provides a running, human-like commentary in the Action Log (e.g., *"Okay, the initial search brought back a few hits; now I'll sift through them for quality."*). This turns the "black box" of AI reasoning into an observable story.

-   **Granular Batch Processing:** Instead of treating all web results as one giant block of text, Chorus processes each source individually. This allows the **Validator Agent** to approve or reject sources one by one and the **Abstraction Agent** to summarize them with greater focus and accuracy, dramatically improving the quality of the data used for the final answer.

-   **Adaptive Content Validation:** An intelligent Validator Agent first analyzes the *user's intent* (e.g., "are they asking a specific factual question or for a broad overview?"). It then applies a different set of validation rules accordingly, making smarter decisions about which sources are truly useful.

-   **Advanced Hybrid Memory:** The assistant leverages a dual-memory system:
    -   **Short-Term:** Guarantees recall of the last few turns of conversation for immediate context.
    -   **Long-Term Semantic:** Embeds the chat history into a vector space, allowing it to recall semantically relevant information from much earlier in the conversation.

-   **Deterministic Source Citation:** The application **programmatically tracks and injects citations**. Source data (URL, title, date) is captured during scraping and attached to the final response by the application code, guaranteeing 100% accuracy.

## How It Works: The Agentic Workflow

Chorus's intelligence comes from a structured, multi-step workflow orchestrated between several specialized AI agents.

#### The Chorus of Agents

1.  **Intent Agent (The Planner):** Analyzes the user's query and conversational context to produce a clear, actionable `<search_plan>`.
2.  **Validator Agent (The Quality Gatekeeper):** Critically evaluates each scraped web source individually. It uses adaptive, intent-aware rules to return a `<pass>` or `<fail>` judgment, ensuring only relevant information proceeds.
3.  **Refiner Agent (The Problem Solver):** If the initial search results are all rejected by the Validator, this agent analyzes the failure and generates a new, improved search plan to overcome the dead end.
4.  **Abstraction Agent (The Summarizer):** Processes each *validated* source, extracting key facts and structuring the raw text into a clean, summarized format.
5.  **Synthesis Agent (The Author):** The main agent that receives the structured data from the Abstraction Agent and synthesizes it into a final, cohesive, user-facing answer.
6.  **Narrator Agent (The Commentator):** Observes the entire process from start to finish, providing a running monologue in the Action Log that explains what the system is doing at each step.

#### From Query to Answer: A Step-by-Step Breakdown

1.  **User Input:** The user submits a query.
2.  **Narration & Intent Analysis:** The **Narrator Agent** announces the start of the process. The **Intent Agent** analyzes the query and produces a search plan.
3.  **Search Execution:** The **Synthesis Agent** (acting as orchestrator) executes the plan, using an intelligent URL ranking system to prioritize reliable domains.
4.  **Content Extraction & Validation:** The system scrapes content from top URLs. The **Validator Agent** inspects each source individually. If all fail, the **Refiner Agent** is triggered to create a new plan.
5.  **Abstraction:** For each source that passes validation, the **Abstraction Agent** is called to extract and structure the key information.
6.  **Synthesis:** The **Synthesis Agent** receives the clean, structured data from all validated sources and composes a comprehensive, well-formatted Markdown answer.
7.  **Deterministic Citation:** Finally, the application code itself—**not the LLM**—appends a perfectly formatted `<sources>` block to the response, guaranteeing accuracy.

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
3.  **Required Ollama Models:** The application relies on specific models for its agentic stack. Pull them using the following commands in your terminal:

    ```bash
    # For main synthesis, planning, and abstraction agents
    ollama pull qwen3:8b

    # For the high-powered Validator agent
    ollama pull qwen3:14b

    # For the fast, lightweight Narrator agent
    ollama pull qwen2.5:7b

    # For generating vector embeddings for semantic memory
    ollama pull nomic-embed-text
    ```

#### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/Chorus-AI-Research-Assistant.git
    cd Chorus-AI-Research-Assistant
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
python main.py 
# (Or whatever you have named the main script, e.g., Ai_Web_Search.py)
```

## Usage Guide

-   **Chat Interface:** The main window on the left is where you interact with the AI.
-   **Action Log:** The panel on the right provides a detailed, real-time log of the AI's internal state. Look for the *italic blue entries* from the **Narrator Agent** for a high-level summary of the process.
-   **Force Search Toggle:** The magnifying glass button (`⌕`) forces a web search, guaranteeing the most current information.
-   **Expandable Details:** Responses may include "Thinking Process" and "Sources" buttons. Click these to see the agent's reasoning and view the source citations.
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
