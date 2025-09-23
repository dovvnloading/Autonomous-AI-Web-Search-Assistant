# --- ui/main_window.py ---
import re
import markdown2
from datetime import datetime
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QPushButton, QLabel,
                             QFrame, QScrollArea, QSplitter)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QTextCursor

# Local Imports
import config
from semantic_memory import SemanticMemory
from core_logic import SearchWorker
from uiwidgets import CustomTitleBar, MessageBubble


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.memory = SemanticMemory(log_callback=lambda msg, level="MEMORY": self.update_log(msg, level))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.current_prompt = None
        
        self.worker_timeout_timer = QTimer(self)
        self.worker_timeout_timer.setSingleShot(True)
        self.worker_timeout_timer.setInterval(config.WORKER_TIMEOUT_MS)
        self.worker_timeout_timer.timeout.connect(self.handle_worker_timeout)
        
        self.query_stopwatch_timer = QTimer(self)
        self.query_stopwatch_timer.setInterval(1000) # 1 second tick
        self.query_stopwatch_timer.timeout.connect(self.update_stopwatch)
        self.query_start_time = None
        
        self.init_ui()
        
    def init_ui(self):
        self.setGeometry(100, 100, 1100, 750)
        self.setMinimumSize(800, 600)
        main_container = QFrame(); main_container.setObjectName("mainContainer")
        container_layout = QVBoxLayout(main_container); container_layout.setContentsMargins(1,1,1,1); container_layout.setSpacing(0)
        self.title_bar = CustomTitleBar(self)
        content_splitter = QSplitter(Qt.Horizontal)
        chat_panel = QWidget(); chat_panel_layout = QVBoxLayout(chat_panel); chat_panel_layout.setContentsMargins(10,10,5,10)
        self.chat_scroll = QScrollArea(); self.chat_scroll.setWidgetResizable(True); self.chat_scroll.setObjectName("chatScrollArea")
        self.chat_container = QWidget(); self.chat_layout = QVBoxLayout(self.chat_container); self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_container); chat_panel_layout.addWidget(self.chat_scroll)
        log_panel = QWidget(); log_panel_layout = QVBoxLayout(log_panel); log_panel_layout.setContentsMargins(5,10,10,10)
        log_title = QLabel("Action Log"); log_title.setObjectName("panelTitle")
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True); self.log_display.setObjectName("logDisplay")
        log_panel_layout.addWidget(log_title); log_panel_layout.addWidget(self.log_display)
        content_splitter.addWidget(chat_panel); content_splitter.addWidget(log_panel); content_splitter.setSizes([700, 300])
        footer_frame = QFrame(); footer_frame.setObjectName("footerFrame")
        footer_layout = QVBoxLayout(footer_frame); footer_layout.setContentsMargins(10,10,10,5)
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit(); self.input_field.setObjectName("inputField"); self.input_field.setPlaceholderText("Enter your query..."); self.input_field.setFixedHeight(50)
        self.send_button = QPushButton("➤"); self.send_button.setObjectName("sendButton"); self.send_button.setFixedSize(50, 50); self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_field); input_layout.addWidget(self.send_button)
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready"); self.status_label.setObjectName("statusLabel")
        
        self.timer_label = QLabel(""); self.timer_label.setObjectName("timerLabel"); self.timer_label.setVisible(False)
        
        self.clear_button = QPushButton("New Chat"); self.clear_button.setObjectName("clearButton"); self.clear_button.clicked.connect(self.clear_chat_session)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.timer_label)
        status_layout.addStretch()
        status_layout.addWidget(self.clear_button)
        
        footer_layout.addLayout(input_layout); footer_layout.addLayout(status_layout)
        container_layout.addWidget(self.title_bar, stretch=0); container_layout.addWidget(content_splitter, stretch=1); container_layout.addWidget(footer_frame, stretch=0)
        self.setCentralWidget(main_container)
        self.setStyleSheet(self.get_stylesheet())

    def get_stylesheet(self):
        return """
            #mainContainer { background-color: #1E1E1E; border: 1px solid #3C3C3C; border-radius: 8px; }
            QMainWindow { background-color: transparent; }
            #customTitleBar { background-color: #2D2D2D; border-top-left-radius: 8px; border-top-right-radius: 8px; }
            #windowTitle { color: #CCCCCC; font-size: 14px; font-weight: bold; }
            #windowButton { background-color: transparent; color: #CCCCCC; border: none; font-size: 16px; font-weight: bold; }
            #windowButton:hover { background-color: #4A4A4A; } #closeButton:hover { background-color: #E81123; color: white; }
            QSplitter::handle { background-color: #2D2D2D; width: 3px; } QSplitter::handle:hover { background-color: #007ACC; }
            #panelTitle { color: #4EC9B0; font-size: 13px; font-weight: bold; margin-bottom: 5px; padding-left: 2px; }
            #chatScrollArea { border: none; background: transparent; }
            #logDisplay { border: 1px solid #333333; border-radius: 4px; background-color: #252526; color: #D4D4D4; font-family: Consolas, Courier New, monospace; font-size: 12px; }
            QFrame#messageBubbleContainer { background-color: #2D2D2D; border: 1px solid #3C3C3C; border-radius: 8px; max-width: 650px; }
            QFrame#messageBubbleContainer[isUser="true"] { background-color: #004C8A; border-color: #007ACC; }
            QLabel#messageText { background-color: transparent; border: none; padding: 0; color: #D4D4D4; font-size: 14px; }
            #toggleDetailButton { background-color: #3C3C3C; color: #CCCCCC; border: none; border-radius: 6px; font-size: 12px; padding: 6px 12px; margin-top: 8px; font-weight: 500; }
            #toggleDetailButton:hover { background-color: #4A4A4A; color: #E0E0E0; } 
            #toggleDetailButton:checked { background-color: #555555; color: white; }
            #thinkingContainer, #citationsContainer { background-color: #252526; border: 1px solid #3C3C3C; border-radius: 6px; margin-top: 4px; }
            #thinkingLabel { font-family: Consolas, 'Courier New', monospace; font-size: 12px; color: #B3B3B3; background-color: transparent; padding: 8px; }
            #citationLabel { font-size: 12px; padding: 4px 6px; line-height: 1.4; background-color: transparent; border: none; } 
            #citationLabel a { color: #4EC9B0; text-decoration: none; } 
            #citationLabel a:hover { text-decoration: underline; color: #6BD4BC; }
            #footerFrame { background-color: #2D2D2D; border-top: 1px solid #3C3C3C; }
            #inputField { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 4px; padding: 8px; color: #F1F1F1; font-size: 14px; }
            #inputField:focus { border: 1px solid #007ACC; }
            #sendButton { background-color: #007ACC; color: white; border: none; border-radius: 25px; font-size: 20px; }
            #sendButton:hover { background-color: #1F9CFD; } 
            #sendButton:disabled { background-color: #4A4A4A; }
            #statusLabel { color: #888888; font-size: 12px; }
            #timerLabel { color: #007ACC; font-size: 12px; font-weight: bold; margin-left: 10px; }
            #clearButton { background-color: #3C3C3C; color: #CCCCCC; border: 1px solid #555; padding: 4px 10px; border-radius: 4px; font-size: 12px; }
            #clearButton:hover { background-color: #4A4A4A; color: white; border-color: #666; }
            QScrollBar:vertical { border: none; background: #252526; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #4A4A4A; border-radius: 5px; min-height: 25px; } 
            QScrollBar::handle:vertical:hover { background: #6A6A6A; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #252526; }
            QScrollBar:horizontal { border: none; background: #252526; height: 10px; margin: 0; }
            QScrollBar::handle:horizontal { background: #4A4A4A; border-radius: 5px; min-width: 25px; }
            QScrollBar::handle:horizontal:hover { background: #6A6A6A; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #252526; }
        """

    def clear_chat_session(self):
        self.memory.clear()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.update_log("--- New Chat Session Started ---", "STEP")
        self.status_label.setText("Ready")
        self.input_field.setFocus()

    def send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text: return
            
        self.current_prompt = text
            
        self.add_message_to_ui(text, is_user=True)
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

    def add_message_to_ui(self, text: str, is_user: bool):
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
        
        if self.current_prompt:
            self.memory.add_message(role='user', content=self.current_prompt)
            self.memory.add_message(role='assistant', content=summary_for_memory)
            self.current_prompt = None
        
        self.set_ui_enabled(True)
        self.update_log("Response delivered to UI.", "INFO")

    def handle_error(self, error: str):
        self.worker_timeout_timer.stop()
        self.query_stopwatch_timer.stop()
        self.timer_label.setVisible(False)
        
        error_msg = f"Error: {error}"
        self.add_message_to_ui(error_msg, is_user=False)
        
        if self.current_prompt:
            self.memory.add_message(role='user', content=self.current_prompt)
            self.memory.add_message(role='assistant', content=error_msg)
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
        self.clear_button.setEnabled(enabled)
        if enabled:
            self.status_label.setText("Ready")
            self.input_field.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            if self.send_button.isEnabled(): self.send_message()
        else: super().keyPressEvent(event)