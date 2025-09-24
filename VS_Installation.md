# Chorus AI - Visual Studio Installation Guide (Direct Download)

This guide provides step-by-step instructions for setting up and running the Chorus AI project in Microsoft Visual Studio by downloading the files directly from the GitHub website.

## 1. Prerequisites

Before you start, ensure the following are installed and configured on your system:

*   **Microsoft Visual Studio**: The **"Python development"** workload is required.
    *   To install, open the "Visual Studio Installer," click "Modify," go to the "Workloads" tab, and select "Python development."
*   **Ollama**: The application's AI backbone.
    *   Download and install Ollama from [ollama.ai](https://ollama.ai/).
    *   **Important:** The Ollama application must be running in the background before you launch Chorus.

## 2. Pull Required AI Models

The application requires several specific AI models to function. Open a **PowerShell** or **Command Prompt** and run the following commands one by one to download them into Ollama.

```powershell
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b-instruct
ollama pull qwen3:8b
ollama pull qwen3:14b
```

## 3. Project Setup in Visual Studio

### Step 3.1: Download and Extract Project Files

1.  Navigate to the project's GitHub page in your web browser:
    [https://github.com/dovvnloading/Autonomous-AI-Web-Search-Assistant](https://github.com/dovvnloading/Autonomous-AI-Web-Search-Assistant)

2.  Click the green **`< > Code`** button on the right side of the page.

3.  In the dropdown menu, select **Download ZIP**. Save the file to your computer (e.g., your Downloads folder).

4.  Locate the downloaded ZIP file (e.g., `Autonomous-AI-Web-Search-Assistant-main.zip`) and extract its contents. You can do this by right-clicking the file and selecting **"Extract All..."**.

5.  After extraction, you will have a folder named `Autonomous-AI-Web-Search-Assistant-main`. Open this folder. Inside, you will find the **`Chorus`** folder which contains all the necessary project files.

### Step 3.2: Open the Project in Visual Studio

1.  Launch Visual Studio.
2.  On the start screen, select **Open a local folder**.
3.  Navigate to the location where you extracted the files and select the **`Chorus`** sub-folder.
4.  Visual Studio will open the folder and list all the project files in the **Solution Explorer**.

### Step 3.3: Create Environment & Install Dependencies

We will now create a dedicated Python environment for this project and install the required libraries.

1.  In the **Solution Explorer**, right-click on the empty space and select **Add > New Folder**. Name it `.venv`.
2.  Now, right-click on **Python Environments** in the Solution Explorer and select **Add Environment...**.
3.  In the "Add Environment" window:
    *   Select **Virtual environment**.
    *   Ensure the "Location" field points to the `.venv` folder you just created (e.g., `<your_project_path>\Chorus\.venv`).
    *   Check the box for "Make this the default environment for the project".
4.  Click **Create**. Visual Studio will set up an empty virtual environment.
5.  Once the environment is created, right-click on it in the **Python Environments** list and select **Open in PowerShell**.
6.  A PowerShell terminal will open, already activated in your new environment. Copy and paste the following command and press Enter to install all required libraries:
    ```powershell
    pip install PySide6 requests ollama trafilatura numpy duckduckgo-search beautifulsoup4 markdown2
    ```
7.  Wait for the installation to complete successfully.

### Step 3.4: Set the Startup File

Tell Visual Studio which script is the main entry point for the application.

1.  In the **Solution Explorer**, find and right-click on `chorus.py`.
2.  Select **Set as Startup Item**. The filename `chorus.py` will become **bold**.

## 4. Running the Application

You are now ready to launch Chorus AI.

1.  **Crucially, ensure the Ollama application is running in the background.**
2.  In Visual Studio, press **F5** to start the application with the debugger attached, or press **Ctrl+F5** to run it without debugging.

The Chorus AI application window should now appear on your screen.
