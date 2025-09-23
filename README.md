# Chorus: A Multi-Agent AI Research Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/Qt-PySide6-brightgreen.svg)
![Ollama](https://img.shields.io/badge/LLM-Ollama-252526.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

---
Audio Overview: https://notebooklm.google.com/notebook/cbf76f05-313c-47a9-8a30-3beaf7f34610?artifactId=029bfd23-4d50-479d-a819-7a53a285b060
---

An open-source, privacy-first alternative to Perplexity & ChatGPT’s web search mode, powered by local models, a multi-agent architecture, and real-time web access.

Chorus doesn’t just answer questions—it *reasons*. It operates a sophisticated workflow where a **chorus of specialized AI agents** collaborate to plan, search, validate, abstract, and narrate the entire process of finding and synthesizing information. It runs entirely on your local machine, ensuring every interaction is secure, private, and radically transparent.

-   **Current, Factual Answers:** Fetches and synthesizes information from live web searches.
-   **Verifiable & Trustworthy:** Provides deterministic, accurate source citations for every answer.
-   **100% Private:** No data, queries, or conversations ever leave your computer.
-   **Radical Transparency:** A unique **Narrator Agent** provides a human-like, running commentary on the AI's internal thought process.
-   **Hybrid Contextual Memory:** Remembers both short-term conversational flow and long-term semantic context.

Think of it as your own **local, autonomous research team**: more accurate than a standard chatbot, more transparent than any commercial alternative, and completely in your control.

![Untitled video - Made with Clipchamp (8)](https://github.com/user-attachments/assets/76ea27e0-7fe4-403f-b42e-70216015570e)
<img width="1100" height="750" alt="Screenshot 2025-09-23 080920" src="https://github.com/user-attachments/assets/85e58262-07a6-4b9f-af8a-75c9832b7782" />
<img width="1100" height="750" alt="Screenshot 2025-09-23 080937" src="https://github.com/user-attachments/assets/d1055259-b290-4e95-9848-1a7089ec0515" />
<img width="1100" height="750" alt="Screenshot 2025-09-23 081020" src="https://github.com/user-attachments/assets/c9ca44bd-c18b-4e20-9bcb-7190a5ef36eb" />
<img width="1100" height="750" alt="Screenshot 2025-09-23 083635" src="https://github.com/user-attachments/assets/fadd90fa-fed6-4b11-ba5b-c0669e341c69" />
<img width="1100" height="750" alt="Screenshot 2025-09-23 083653" src="https://github.com/user-attachments/assets/c2f85053-5fb6-4fb9-81a9-a69f647db5de" />





---

## Architectural Deep Dive: The Journey of a Query

The sophistication of Chorus lies in its multi-agent, sequential, and recursive pipeline. Each user query initiates a journey through a series of specialized agents and logic gates, ensuring that the final output is the product of a rigorous, verifiable process.

### Step 1: Strategic Deconstruction & Planning

Before any action is taken, the system first seeks to understand the user's true intent. This is handled by a dedicated **`IntentAgent`**, which acts as a strategic mission planner.

-   **Deep Conversational Context:** The agent is provided with a rich, hybrid context from the `SemanticMemory`. This includes a guaranteed, verbatim recall of the last two conversational turns and a semantically-retrieved selection of older, relevant messages. This allows the system to accurately resolve ambiguous follow-up commands like "go deeper on that".
-   **Intelligent Abstraction:** The conversational history given to the `IntentAgent` is deliberately sanitized. Internal "thinking" processes (`<think>` blocks) from previous answers are stripped away, focusing the agent on the tangible information that was delivered to the user.
-   **Task Decomposition:** The `IntentAgent`'s primary output is a structured plan. It deconstructs a complex query into a series of discrete, machine-friendly search topics, transforming a nuanced human request into an actionable set of research objectives.

### Step 2: Intelligent & Adaptive Information Retrieval

With a clear plan, the framework deploys its "scout" capabilities. This stage is designed to be adaptive and discerning, prioritizing signal over noise from the open web.

-   **Heuristic-Based Source Ranking:** The system uses a sophisticated ranking algorithm to prioritize search results *before* attempting to scrape them, applying a weighted score based on domain authority, information recency, and quality filtering against known low-signal domains.
-   **Resilient Search Strategy:** The system employs a "narrow-to-broad" fallback mechanism. If a highly-specific, domain-targeted search fails, it automatically re-executes the search on the wider web, ensuring resilience.
-   **Robust Content Extraction:** A two-stage extraction process uses a high-precision library (`trafilatura`) first, then falls back to a more aggressive HTML parser, guaranteeing that usable text is extracted from various web page structures.

### Step 3: Autonomous Quality Control

Chorus operates on a "zero-trust" principle: all information is considered unreliable until it passes a rigorous, independent validation stage.

-   **The Dedicated `ValidatorAgent`:** A specialized agent with a single, uncompromising purpose: to validate content. Each scraped source is passed to this agent to be checked for relevance, depth, and alignment with the user's query.
-   **The Unforgiving Gate:** The validation process is binary. The `ValidatorAgent` must return a definitive `<pass>` tag. Any source that fails this check is immediately and irrevocably discarded from the data pool.
-   **Guaranteed Data-Source Integrity:** A crucial filtering function ensures that the final list of citations perfectly mirrors the data that was actually validated and used, making every reference directly traceable.

### Step 4: Multi-Stage Synthesis & Self-Correction

The system is not a linear pipeline; it is a dynamic framework with internal feedback loops that allow it to adapt and recover from failure.

-   **The Refinement Loop (Failure Recovery):** If the Quality Control gate rejects *all* initial sources, the system triggers a recovery protocol, invoking a **`RefinerAgent`**. This agent is given the original failed query *and the specific reasons why sources were rejected* to construct a new, more intelligent search plan.
-   **The Augmentation Loop (Information Gaps):** The final **`SynthesisAgent`** can request more information. If it determines a critical piece of information is missing, it can pause its own process and issue a request for an `<additional_search>`, which triggers a new, targeted search-and-validate cycle.

### Step 5: Persistent Contextual Awareness

Underpinning the entire process is the `SemanticMemory` class, which serves as the system's working memory and long-term knowledge base.

-   **Hybrid Memory Model:** Combines the perfect recall of a short-term conversational queue with the power of long-term semantic retrieval, grounding every action in both immediate and broader context.
-   **Conceptual Retrieval:** By using vector embeddings, the memory operates on conceptual meaning, not just keywords, allowing it to connect ideas across multiple conversational turns.

## The Chorus of Agents

Chorus's intelligence comes from a structured workflow orchestrated between several specialized AI agents.

1.  **Intent Agent (The Planner):** Analyzes the user's query and conversational context to produce a clear, actionable search plan.
2.  **Validator Agent (The Quality Gatekeeper):** Critically evaluates each scraped web source individually to return a `<pass>` or `<fail>` judgment.
3.  **Refiner Agent (The Problem Solver):** If all initial results are rejected, this agent analyzes the failure feedback and generates an improved search plan.
4.  **Abstraction Agent (The Summarizer):** Processes each *validated* source, extracting key facts and structuring the raw text into a clean format.
5.  **Synthesis Agent (The Author):** The main agent that receives the structured data from all validated sources and synthesizes it into a final, cohesive, user-facing answer.
6.  **Narrator Agent (The Commentator):** A unique feature for transparency. This lightweight agent observes the entire process, providing a running, human-like monologue in the Action Log that explains what the system is doing at each step.

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
3.  **Required Ollama Models:** The application relies on specific models for its agentic stack. Pull them using the following commands in your terminal. **Note:** The application can run effectively on a single GPU with ~16GB of VRAM (e.g., RTX 3090).

    ```bash
    # For main synthesis and high-powered agents
    ollama pull qwen3:14b

    # For planning, abstraction, and validation agents
    ollama pull qwen3:8b

    # For the fast, lightweight Narrator agent
    ollama pull qwen2.5:7b-instruct

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
# (Or whatever you have named the main script)
```

## Usage Guide

-   **Chat Interface:** The main window on the left is where you interact with the AI.
-   **Action Log:** The panel on the right provides a detailed, real-time log of the AI's internal state. Look for the *italic blue entries* from the **Narrator Agent** for a high-level summary.
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
