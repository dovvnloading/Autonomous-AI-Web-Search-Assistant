
### **Project Title: Autonomous AI Web Search Assistant**

### **High-Level Summary**

This is a sophisticated, standalone desktop AI chat application built with Python and PySide6. It enhances a local Large Language Model (LLM) with a powerful, real-time web search capability, functioning as an intelligent Retrieval-Augmented Generation (RAG) system. The application employs a **multi-agent architecture** where specialized AI agents collaborate to understand user intent, plan and execute targeted web searches, validate the relevance of scraped content, and synthesize comprehensive, cited answers. This transforms a standard LLM into a dynamic research assistant capable of providing up-to-the-minute information.

### **Key Features**

*   **Multi-Agent Autonomous System:** The application uses a "chain of thought" process distributed across multiple specialized AI agents, each with a distinct role:
    *   **Search Intent Agent:** Intercepts complex user queries to decompose them into a structured, actionable `<search_plan>`, ensuring highly relevant and targeted searches.
    *   **Main Search Agent:** Analyzes the user's query, contextual history, and the search plan to decide if a web search is necessary, formulate precise search queries, and synthesize the final answer.
    *   **Content Validator Agent:** A critical quality control step; this agent programmatically evaluates scraped web content against the original user query, passing only relevant information and rejecting outdated, generic, or off-topic results.

*   **Semantic Memory with Vector Search:**
    *   Implements a long-term conversation memory that stores not just text but its semantic meaning.
    *   Uses the `nomic-embed-text` model via Ollama to generate vector embeddings for each message.
    *   When responding, it performs a cosine similarity search to retrieve the most contextually relevant past messages, providing the AI with a deeper understanding of the ongoing conversation.

*   **Intelligent Retrieval-Augmented Generation (RAG):**
    *   **Dynamic Search Decision-Making:** The AI autonomously determines when to use its internal knowledge versus when to search the web for topics requiring current information (e.g., news, stock prices, recent events).
    *   **Domain-Prioritized URL Ranking:** After getting search results from DuckDuckGo, the system intelligently ranks URLs based on the query type, prioritizing authoritative domains for financial, news, or technical topics to improve source quality.
    *   **Robust Content Extraction:** Utilizes `trafilatura` and `BeautifulSoup` for high-precision extraction of main article content from URLs, filtering out ads, navigation, and boilerplate.
    *   **Automated Content Validation & Refinement:** If the initial search results are deemed irrelevant by the Validator Agent, the system automatically triggers a refined search with modified queries to find better information.

*   **Rich, Asynchronous Desktop UI (PySide6):**
    *   **Non-Blocking Operations:** All AI processing and web scraping runs in a separate `QThread`, ensuring the user interface remains responsive at all times.
    *   **Modern Chat Interface:** Features a custom frameless window, message bubbles, and automatic rendering of Markdown for well-formatted responses.
    *   **Interactive Components:** Includes collapsible sections for viewing the AI's "Thinking Process" and clickable, neatly formatted "Sources," providing transparency and traceability for every answer.
    *   **Developer-Focused Action Log:** A live-updating log panel displays the detailed step-by-step actions of the multi-agent system, offering deep insight into the application's internal state.

### **Core Architecture & Technical Stack**

*   **Programming Language:** Python
*   **AI/LLM Integration:** `ollama`
    *   **Chat Models:** `qwen3:14b` (Main Synthesis), `qwen3:8b` (Agents)
    *   **Embedding Model:** `nomic-embed-text`
*   **GUI Framework:** `PySide6` (the official Python bindings for Qt)
    *   Leverages `QThread` for asynchronous background tasks, `QPropertyAnimation` for smooth UI effects, and a custom-styled, modern interface.
*   **Web Scraping & Data Extraction:**
    *   **Search Engine API:** `ddgs` (DuckDuckGo Search)
    *   **Content Scraping:** `requests`
    *   **HTML Parsing & Content Extraction:** `trafilatura`, `BeautifulSoup4`
*   **Data Handling & Numerics:** `NumPy` for vector operations (cosine similarity).
*   **Text Processing:** `markdown2` for rendering AI responses into rich text.
