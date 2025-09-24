# --- ui/main_window.py ---
import re
import markdown2
from datetime import datetime
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QPushButton, QLabel,
                             QFrame, QScrollArea, QSplitter, QListWidget,
                             QListWidgetItem, QInputDialog, QMessageBox,
                             QSizePolicy, QSizeGrip)
from PySide6.QtCore import QTimer, Qt, QSize, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QTextCursor, QIcon, QPixmap

# Local Imports
import config
from semantic_memory import SemanticMemory
from history_manager import HistoryManager
from core_logic import SearchWorker, TitleWorker, load_prompts_from_file
from uiwidgets import CustomTitleBar, MessageBubble


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.current_prompt = None
        self.current_chat_id = None
        
        self.worker_timeout_timer = QTimer(self)
        self.worker_timeout_timer.setSingleShot(True)
        self.worker_timeout_timer.setInterval(config.WORKER_TIMEOUT_MS)
        self.worker_timeout_timer.timeout.connect(self.handle_worker_timeout)
        
        self.query_stopwatch_timer = QTimer(self)
        self.query_stopwatch_timer.setInterval(1000) # 1 second tick
        self.query_stopwatch_timer.timeout.connect(self.update_stopwatch)
        self.query_start_time = None
        
        # Initialize UI first to ensure all widgets exist
        self.init_ui()

        # Load prompts once at startup and log to the UI
        self.prompts = load_prompts_from_file(config.PROMPT_FILE_PATH, self.update_log)
        
        # Now that UI elements like log_display exist, initialize managers
        self.history_manager = HistoryManager(log_callback=lambda msg, level="INFO": self.update_log(msg, level))
        self.memory = SemanticMemory(log_callback=lambda msg, level="MEMORY": self.update_log(msg, level))
        
        # Proceed with the rest of the setup
        self.populate_history_list()
        self.start_new_chat_session()
        
    def init_ui(self):
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(900, 650)
        main_container = QFrame(); main_container.setObjectName("mainContainer")
        # --- Main Vertical Layout ---
        container_layout = QVBoxLayout(main_container); container_layout.setContentsMargins(1,1,1,1); container_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        self.title_bar.toggle_button.clicked.connect(self.toggle_history_panel)

        # --- Main Content Area (Horizontal Layout with Panels) ---
        content_layout = QHBoxLayout(); content_layout.setSpacing(0); content_layout.setContentsMargins(0,0,0,0)

        # --- History Panel (Left) ---
        self.history_panel = QFrame(); self.history_panel.setObjectName("historyPanel"); self.history_panel.setMaximumWidth(240)
        history_layout = QVBoxLayout(self.history_panel); history_layout.setContentsMargins(10,10,5,10)
        
        history_header_layout = QHBoxLayout()
        history_title = QLabel("Chat History"); history_title.setObjectName("panelTitle")
        self.new_chat_button = QPushButton("＋ New Chat"); self.new_chat_button.setObjectName("newChatButton"); self.new_chat_button.clicked.connect(self.start_new_chat_session)
        history_header_layout.addWidget(history_title); history_header_layout.addStretch(); history_header_layout.addWidget(self.new_chat_button)
        
        self.history_list = QListWidget(); self.history_list.setObjectName("historyList"); self.history_list.itemClicked.connect(self.on_history_item_clicked)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)

        history_layout.addLayout(history_header_layout); history_layout.addWidget(self.history_list)

        # --- Main Content Splitter (Chat + Log) ---
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setObjectName("mainSplitter")

        # --- Chat Panel (Center) ---
        chat_panel_container = QFrame(); chat_panel_container.setObjectName("chatPanelContainer")
        chat_panel_layout = QVBoxLayout(chat_panel_container)
        chat_panel_layout.setContentsMargins(5,10,5,10)
        self.chat_scroll = QScrollArea(); self.chat_scroll.setWidgetResizable(True); self.chat_scroll.setObjectName("chatScrollArea")
        self.chat_container = QWidget(); self.chat_layout = QVBoxLayout(self.chat_container); self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_container); 
        chat_panel_layout.addWidget(self.chat_scroll)
        
        # --- Log Panel (Right) ---
        log_panel = QWidget(); log_panel_layout = QVBoxLayout(log_panel); log_panel_layout.setContentsMargins(5,10,10,10)
        log_title = QLabel("Action Log"); log_title.setObjectName("panelTitle")
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True); self.log_display.setObjectName("logDisplay")
        log_panel_layout.addWidget(log_title); log_panel_layout.addWidget(self.log_display)
        
        main_splitter.addWidget(chat_panel_container); main_splitter.addWidget(log_panel); main_splitter.setSizes([700, 300])

        content_layout.addWidget(self.history_panel); content_layout.addWidget(main_splitter)

        # --- Footer (Input bar, etc.) ---
        footer_frame = QFrame(); footer_frame.setObjectName("footerFrame")
        footer_layout = QVBoxLayout(footer_frame); footer_layout.setContentsMargins(10,10,10,5)
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit(); self.input_field.setObjectName("inputField"); self.input_field.setPlaceholderText("Enter your query..."); self.input_field.setFixedHeight(50)
        self.send_button = QPushButton("➤"); self.send_button.setObjectName("sendButton"); self.send_button.setFixedSize(50, 50); self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_field); input_layout.addWidget(self.send_button)
        
        # --- Status Layout with Size Grip ---
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready"); self.status_label.setObjectName("statusLabel")
        self.timer_label = QLabel(""); self.timer_label.setObjectName("timerLabel"); self.timer_label.setVisible(False)
        self.size_grip = QSizeGrip(footer_frame) # Attach grip to footer
        status_layout.addWidget(self.status_label); status_layout.addWidget(self.timer_label); status_layout.addStretch()
        status_layout.addWidget(self.size_grip, 0, Qt.AlignBottom | Qt.AlignRight)
        
        footer_layout.addLayout(input_layout); footer_layout.addLayout(status_layout)

        # --- Add all main widgets to the container ---
        container_layout.addWidget(self.title_bar, stretch=0)
        container_layout.addLayout(content_layout, stretch=1) # History, Chat, Log
        container_layout.addWidget(footer_frame, stretch=0)    # Input Bar at the bottom
        
        self.setCentralWidget(main_container)
        self.setStyleSheet(self.get_stylesheet())
        
        self.history_panel_animation = QPropertyAnimation(self.history_panel, b"maximumWidth")
        self.history_panel_animation.setDuration(300)
        self.history_panel_animation.setEasingCurve(QEasingCurve.InOutCubic)

    def get_stylesheet(self):
        resize_grip_svg_base64 = "PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTUgOSBMOSAxNSIgc3Ryb2tlPSIjODg4ODg4IiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjxwYXRoIGQ9Ik0xNSAxMyBMMTMgMTUiIHN0cm9rZT0iIzg4ODg4OCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4="

        return f"""
            #mainContainer {{ background-color: #1E1E1E; border: 1px solid #3C3C3C; border-radius: 8px; }}
            QMainWindow {{ background-color: transparent; }}
            #customTitleBar {{ background-color: #2D2D2D; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
            #windowTitle {{ color: #CCCCCC; font-size: 14px; font-weight: bold; }}
            #windowButton {{ background-color: transparent; color: #CCCCCC; border: none; font-size: 16px; font-weight: bold; }}
            #windowButton:hover {{ background-color: #4A4A4A; }} #closeButton:hover {{ background-color: #E81123; color: white; }}
            #mainSplitter::handle {{ background-color: #2D2D2D; width: 3px; }} #mainSplitter::handle:hover {{ background-color: #007ACC; }}
            #historyPanel {{ background-color: #252526; border-right: 1px solid #3C3C3C; }}
            #newChatButton {{ font-size: 12px; background-color: #3C3C3C; color: #CCCCCC; border: 1px solid #555; padding: 4px 10px; border-radius: 4px; }}
            #newChatButton:hover {{ background-color: #4A4A4A; }}
            #historyList {{ border: none; background: transparent; color: #D4D4D4; font-size: 13px; }}
            #historyList::item {{ padding: 8px 10px; border-radius: 4px; }}
            #historyList::item:selected {{ background-color: #007ACC; color: white; }}
            #historyList::item:hover:!selected {{ background-color: #3C3C3C; }}
            #chatPanelContainer {{ border: none; background-color: #252526; }}
            #panelTitle {{ color: #4EC9B0; font-size: 13px; font-weight: bold; margin-bottom: 5px; padding-left: 2px; }}
            #chatScrollArea {{ border: none; background: transparent; }}
            #logDisplay {{ border: 1px solid #333333; border-radius: 4px; background-color: #252526; color: #D4D4D4; font-family: Consolas, Courier New, monospace; font-size: 12px; }}
            QFrame#messageBubbleContainer {{ background-color: #2D2D2D; border: 1px solid #3C3C3C; border-radius: 8px; max-width: 650px; }}
            QFrame#messageBubbleContainer[isUser="true"] {{ background-color: #004C8A; border-color: #007ACC; }}
            QLabel#messageText {{ background-color: transparent; border: none; padding: 0; color: #D4D4D4; font-size: 14px; }}
            #toggleDetailButton {{ background-color: #3C3C3C; color: #CCCCCC; border: none; border-radius: 6px; font-size: 12px; padding: 6px 12px; margin-top: 8px; font-weight: 500; }}
            #toggleDetailButton:hover {{ background-color: #4A4A4A; color: #E0E0E0; }} 
            #toggleDetailButton:checked {{ background-color: #555555; color: white; }}
            #thinkingContainer, #citationsContainer {{ background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; margin-top: 4px; }}
            #thinkingLabel {{ font-family: Consolas, 'Courier New', monospace; font-size: 12px; color: #B3B3B3; background-color: transparent; padding: 8px; }}
            #citationLabel {{ font-size: 12px; padding: 4px 6px; line-height: 1.4; background-color: transparent; border: none; }} 
            #citationLabel a {{ color: #4EC9B0; text-decoration: none; }} 
            #citationLabel a:hover {{ text-decoration: underline; color: #6BD4BC; }}
            #footerFrame {{ background-color: #2D2D2D; border-top: 1px solid #3C3C3C; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;}}
            #inputField {{ background-color: #3C3C3C; border: 1px solid #555555; border-radius: 4px; padding: 8px; color: #F1F1F1; font-size: 14px; }}
            #inputField:focus {{ border: 1px solid #007ACC; }}
            #sendButton {{ background-color: #007ACC; color: white; border: none; border-radius: 25px; font-size: 20px; }}
            #sendButton:hover {{ background-color: #1F9CFD; }} 
            #sendButton:disabled {{ background-color: #4A4A4A; }}
            #statusLabel {{ color: #888888; font-size: 12px; }}
            #timerLabel {{ color: #007ACC; font-size: 12px; font-weight: bold; margin-left: 10px; }}
            QSizeGrip {{
                image: url(data:image/svg+xml;base64,{resize_grip_svg_base64});
                width: 16px;
                height: 16px;
            }}
            QScrollBar:vertical {{ border: none; background: #252526; width: 10px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: #4A4A4A; border-radius: 5px; min-height: 25px; }} 
            QScrollBar::handle:vertical:hover {{ background: #6A6A6A; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: #252526; }}
            QScrollBar:horizontal {{ border: none; background: #252526; height: 10px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: #4A4A4A; border-radius: 5px; min-width: 25px; }}
            QScrollBar::handle:horizontal:hover {{ background: #6A6A6A; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: #252526; }}
        """

    def toggle_history_panel(self):
        current_width = self.history_panel.maximumWidth()
        if current_width > 0:
            end_width = 0
            self.title_bar.toggle_button.setText("➤")
        else:
            end_width = 240
            self.title_bar.toggle_button.setText("❮")
        
        self.history_panel_animation.setStartValue(current_width)
        self.history_panel_animation.setEndValue(end_width)
        self.history_panel_animation.start()

    def populate_history_list(self):
        self.history_list.clear()
        chats = self.history_manager.get_all_chats_sorted()
        for chat in chats:
            item = QListWidgetItem(chat['title'])
            item.setData(Qt.UserRole, chat['id'])
            self.history_list.addItem(item)
        
        if self.current_chat_id:
            for i in range(self.history_list.count()):
                item = self.history_list.item(i)
                if item.data(Qt.UserRole) == self.current_chat_id:
                    item.setSelected(True)
                    break
    
    def on_history_item_clicked(self, item):
        chat_id = item.data(Qt.UserRole)
        if chat_id != self.current_chat_id:
            self.load_chat_session(chat_id)

    def show_history_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if not item: return

        menu = QWidgetActionMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec(self.history_list.mapToGlobal(pos))
        
        if action == rename_action:
            self.rename_chat(item)
        elif action == delete_action:
            self.delete_chat(item)
    
    def rename_chat(self, item):
        chat_id = item.data(Qt.UserRole)
        current_title = item.text()
        new_title, ok = QInputDialog.getText(self, "Rename Chat", "Enter new title:", text=current_title)
        if ok and new_title.strip():
            self.history_manager.update_chat_title(chat_id, new_title.strip())
            item.setText(new_title.strip())
            self.update_log(f"Chat '{current_title}' renamed to '{new_title.strip()}'", "INFO")

    def delete_chat(self, item):
        chat_id = item.data(Qt.UserRole)
        chat_title = item.text()
        reply = QMessageBox.question(self, 'Delete Chat', f"Are you sure you want to delete '{chat_title}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.history_manager.delete_chat(chat_id):
                self.populate_history_list()
                if self.current_chat_id == chat_id:
                    self.start_new_chat_session()
                self.update_log(f"Chat '{chat_title}' deleted.", "INFO")

    def clear_chat_display(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def start_new_chat_session(self):
        self.clear_chat_display()
        self.memory.clear()
        self.current_chat_id = None
        self.history_list.clearSelection()
        self.update_log("--- New Chat Session Started ---", "STEP")
        self.status_label.setText("Ready")
        self.input_field.setPlaceholderText("Start a new conversation...")
        self.input_field.setFocus()
        self.set_ui_enabled(True)

    def load_chat_session(self, chat_id: str):
        self.clear_chat_display()
        chat_data = self.history_manager.get_chat(chat_id)
        if not chat_data:
            self.update_log(f"Failed to load chat {chat_id}, starting new session.", "ERROR")
            self.start_new_chat_session()
            return

        self.current_chat_id = chat_id
        self.memory.load_memory(chat_data['messages'])

        for message in chat_data['messages']:
            # --- FIX: Add a check to prevent crashing on corrupted data ---
            if not message:
                self.update_log("Skipping invalid (None) message in history.", "WARN")
                continue
            
            is_user = message['role'] == 'user'
            content_to_display = message.get('display_content', '')
            self.add_message_to_ui(content_to_display, is_user=is_user)

        self.update_log(f"Loaded chat: '{chat_data['title']}'", "STEP")
        self.status_label.setText("Ready")
        self.input_field.setPlaceholderText("Enter your query...")
        self.input_field.setFocus()
        self.set_ui_enabled(True)

    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text: return
            
        self.current_prompt = text

        is_new_chat = self.current_chat_id is None
        if is_new_chat:
            self.current_chat_id = self.history_manager.create_new_chat()
            self.populate_history_list()
            
            title_prompt = self.prompts.get('TITLE_PROMPT', "Generate a short title for this conversation.")
            self.title_worker = TitleWorker(self.current_chat_id, text, title_prompt)
            self.title_worker.log_message.connect(self.update_log)
            self.title_worker.finished.connect(self.update_chat_title)
            self.title_worker.start()

        self.add_message_to_ui(text, is_user=True)
        user_message_to_store = self.memory.add_message(
            role='user', 
            memory_content=self.current_prompt, 
            display_content=self.current_prompt
        )
        self.history_manager.add_message_to_chat(self.current_chat_id, user_message_to_store)

        self.input_field.clear()
        self.set_ui_enabled(False)
        self.update_log(f"USER QUERY: {text}", "USER")
        self.update_log("MODE: Default Search", "INFO")

        self.worker_timeout_timer.start()
        self.query_start_time = datetime.now()
        self.update_stopwatch()
        self.timer_label.setVisible(True)
        self.query_stopwatch_timer.start()

        self.worker = SearchWorker(text, self.memory)
        self.worker.log_message.connect(self.update_log)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.progress.connect(self.update_status)
        self.worker.start()

    def update_chat_title(self, chat_id: str, title: str):
        self.history_manager.update_chat_title(chat_id, title)
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            if item.data(Qt.UserRole) == chat_id:
                item.setText(title)
                break

    def add_message_to_ui(self, text: str, is_user: bool):
        if not text:
            return

        if is_user:
            bubble = MessageBubble(text)
            bubble.container.setProperty("isUser", True)
        else:
            working_text = text
            thinking_text = None
            citations = None
            think_match = re.search(r'<think>(.*?)</think>', working_text, re.DOTALL)
            if think_match:
                thinking_text = think_match.group(1).strip()
                working_text = re.sub(r'<think>.*?</think>', '', working_text, flags=re.DOTALL).strip()
            sources_match = re.search(r'<sources>(.*?)</sources>', working_text, re.DOTALL)
            if sources_match:
                sources_block = sources_match.group(1)
                working_text = re.sub(r'<sources>.*?</sources>', '', working_text, flags=re.DOTALL).strip()
                citations_found = re.findall(r'<source url="([^"]+)" date="([^"]*)">(.*?)</source>', sources_block)
                if citations_found:
                    citations = []
                    for url, date, title in citations_found:
                        clean_title = title.strip() or "Unknown Title"
                        if len(clean_title) > 80: clean_title = clean_title[:77] + "..."
                        citations.append({'url': url, 'date': date or "N/A", 'title': clean_title})
            main_content_html = markdown2.markdown(working_text, extras=["fenced-code-blocks", "tables", "cuddled-lists"])
            bubble = MessageBubble(main_content_html, citations=citations, thinking_text=thinking_text)
            bubble.container.setProperty("isUser", False)
            bubble.container.setMinimumWidth(650)
            bubble.container.setMaximumWidth(650)
        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(5, 5, 5, 5)
        row_layout.setSpacing(0)
        if is_user: 
            row_layout.addStretch()
            row_layout.addWidget(bubble, 0, Qt.AlignTop)
        else: 
            row_layout.addWidget(bubble, 0, Qt.AlignTop)
            row_layout.addStretch()
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, row_container)
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()))

    def handle_response(self, response: str, summary_for_memory: str):
        self.worker_timeout_timer.stop()
        self.query_stopwatch_timer.stop()
        self.timer_label.setVisible(False)
        
        self.add_message_to_ui(response, is_user=False)
        
        assistant_message_to_store = self.memory.add_message(
            role='assistant',
            memory_content=summary_for_memory,
            display_content=response
        )
        self.history_manager.add_message_to_chat(self.current_chat_id, assistant_message_to_store)
        
        self.current_prompt = None
        self.set_ui_enabled(True)
        self.update_log("Response delivered to UI.", "INFO")

    def handle_error(self, error: str):
        self.worker_timeout_timer.stop()
        self.query_stopwatch_timer.stop()
        self.timer_label.setVisible(False)
        
        error_msg = f"Error: {error}"
        self.add_message_to_ui(error_msg, is_user=False)
        
        if self.current_prompt and self.current_chat_id:
            error_message_to_store = self.memory.add_message(
                role='assistant', 
                memory_content=error_msg,
                display_content=error_msg
            )
            self.history_manager.add_message_to_chat(self.current_chat_id, error_message_to_store)

        self.current_prompt = None
        self.set_ui_enabled(True)
        self.update_log(f"Error handled: {error}", "ERROR")

    def handle_worker_timeout(self):
        self.update_log("WORKER TIMEOUT: Process exceeded 30 minutes and was terminated.", "ERROR")
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.terminate()
        
        if not self.current_prompt:
            self.current_prompt = self.input_field.toPlainText().strip() or "Timed out query"
        
        self.handle_error("The request took too long to process and was cancelled.")

    def update_stopwatch(self):
        if self.query_start_time:
            elapsed = datetime.now() - self.query_start_time
            minutes, seconds = divmod(int(elapsed.total_seconds()), 60)
            self.timer_label.setText(f"Elapsed: {minutes:02d}:{seconds:02d}")

    def update_status(self, status: str):
        self.status_label.setText(status)

    def update_log(self, message: str, level: str = "INFO"):
        LOG_LEVEL_STYLES = config.LOG_LEVEL_STYLES
        scrollbar = self.log_display.verticalScrollBar()
        is_dragging = scrollbar.isSliderDown()
        is_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 10)
        should_autoscroll = (not is_dragging) and is_at_bottom
        self.log_display.moveCursor(QTextCursor.End)
        style = LOG_LEVEL_STYLES.get(level, LOG_LEVEL_STYLES["INFO"])
        
        timestamp = datetime.now().strftime('%I:%M:%S %p')

        safe_message = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        content_html = (
            f'<p style="margin: 0; padding: 0; {style}">'
            f'<span style="color:#777;">{timestamp} --- </span>'
            f'{safe_message}'
            f'</p>'
        )
        spacer_html = '<div style="height: 10px; font-size: 2px;">&nbsp;</div>'
        self.log_display.insertHtml(content_html + spacer_html)
        if should_autoscroll:
            QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))

    def set_ui_enabled(self, enabled: bool):
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.new_chat_button.setEnabled(enabled)
        if enabled:
            self.status_label.setText("Ready")
            self.input_field.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            if self.send_button.isEnabled(): self.send_message()
        else: super().keyPressEvent(event)

# Helper class for a styled context menu
from PySide6.QtWidgets import QMenu
class QWidgetActionMenu(QMenu):
    def __init__(self, parent=None):
        super(QWidgetActionMenu, self).__init__(parent)
        self.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                border: 1px solid #3C3C3C;
                color: #D4D4D4;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #007ACC;
            }
        """)