# Chorus AI - System Prerequisites

This document outlines the necessary hardware, software, and AI models required to run the Chorus AI application. Please review and install these components before proceeding with the main installation guide.

## 1. Hardware Requirements

Your system should meet these minimum specifications to ensure the application and its AI models run smoothly. The primary constraints are RAM (for running the models) and disk space (for storing them).

*   **RAM:** **12 GB minimum**. While smaller models can run on 8 GB, the `qwen3:14b` model used for high-quality refinement requires 12 GB of dedicated RAM.
*   **Disk Space:** **25 GB of free space** is recommended. The models combined require approximately 20 GB, and extra space is needed for the application, Python environment, and chat history.
*   **GPU (Recommended):** A modern NVIDIA GPU with at least 8 GB of VRAM is highly recommended for significantly faster AI model performance. The application will still run on the CPU, but responses will be much slower.

## 2. Software Requirements

You will need to install Visual Studio, a supported version of Python, and the Ollama platform.

### A. Visual Studio Community

This is the integrated development environment (IDE) we will use to run the project.

*   **What it is:** A free, full-featured code editor from Microsoft.
*   **Download Link:** [**Visual Studio Community Edition**](https://visualstudio.microsoft.com/vs/community/)
*   **Key Installation Step:**
    1.  Run the Visual Studio Installer.
    2.  Navigate to the **"Workloads"** tab.
    3.  You **must** check the box for **"Python development"**. This installs all the necessary tools for managing Python projects.

### B. Python

The programming language the application is written in.

*   **What it is:** Python interpreter and standard libraries.
*   **Required Version:** 3.8 or newer.
*   **Download Link:** [**Python Official Downloads**](https://www.python.org/downloads/)
*   **Key Installation Step:**
    1.  Run the Python installer.
    2.  On the very first screen, you **must** check the box at the bottom that says **"Add python.exe to PATH"**. This is crucial for Visual Studio and the command line to find and use Python correctly.

### C. Ollama

This is the platform that runs the AI models locally on your machine.

*   **What it is:** A lightweight, extensible framework for running large language models.
*   **Download Link:** [**Ollama Official Website**](https://ollama.com/)
*   **Key Installation Step:**
    1.  Download and run the installer for your operating system (Windows, macOS, or Linux).
    2.  After installation, **ensure the Ollama application is running in the background**. You should see an icon for it in your system tray or menu bar. Chorus AI cannot function without it.

## 3. AI Model Requirements

The application uses five different models, each optimized for a specific task. You must download all of them using Ollama. Below are the details for each model, with all data sourced directly from the official Ollama library.

---

*   **Model:** **`nomic-embed-text`**
    *   **Size (on disk):** 275 MB
    *   **Recommended RAM:** 4 GB
    *   **Download Command:** `ollama pull nomic-embed-text`

*   **Model:** **`qwen2.5:3b`**
    *   **Size (on disk):** 2.0 GB
    *   **Recommended RAM:** 4 GB
    *   **Download Command:** `ollama pull qwen2.5:3b`

*   **Model:** **`qwen2.5:7b-instruct`**
    *   **Size (on disk):** 4.1 GB
    *   **Recommended RAM:** 8 GB
    *   **Download Command:** `ollama pull qwen2.5:7b-instruct`

*   **Model:** **`qwen3:8b`**
    *   **Size (on disk):** 4.7 GB
    *   **Recommended RAM:** 8 GB
    *   **Download Command:** `ollama pull qwen3:8b`

*   **Model:** **`qwen3:14b`**
    *   **Size (on disk):** 8.2 GB
    *   **Recommended RAM:** 12 GB
    *   **Download Command:** `ollama pull qwen3:14b`

---
**In total, the models require approximately 12 GB of disk space.** The peak RAM usage will be determined by the largest model, requiring a system with at least **12 GB of RAM**.

**How to Download the Models:**
1.  Open a **PowerShell** or **Command Prompt**.
2.  Copy and paste each `ollama pull ...` command listed above, one at a time, and press Enter.
3.  Wait for each download to complete before starting the next one.

Once all hardware and software prerequisites are met and all AI models are downloaded, you are ready to proceed with the project setup instructions.
