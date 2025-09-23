# --- ui/widgets.py ---
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, 
                             QLabel, QPushButton, QFrame)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve

class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent; self.pressing = False; self.setObjectName("customTitleBar")
        layout = QHBoxLayout(self); layout.setContentsMargins(10, 0, 0, 0); layout.setSpacing(10)
        self.title = QLabel("Chorus.Ai"); self.title.setObjectName("windowTitle"); layout.addWidget(self.title); layout.addStretch()
        btn_size = 30
        self.minimize_button = QPushButton("—"); self.minimize_button.setObjectName("windowButton"); self.minimize_button.setFixedSize(btn_size, btn_size); self.minimize_button.clicked.connect(self.parent.showMinimized)
        self.maximize_button = QPushButton("□"); self.maximize_button.setObjectName("windowButton"); self.maximize_button.setFixedSize(btn_size, btn_size); self.maximize_button.clicked.connect(self.toggle_maximize)
        self.close_button = QPushButton("✕"); self.close_button.setObjectName("closeButton"); self.close_button.setFixedSize(btn_size, btn_size); self.close_button.clicked.connect(self.parent.close)
        layout.addWidget(self.minimize_button); layout.addWidget(self.maximize_button); layout.addWidget(self.close_button)
    def toggle_maximize(self): self.parent.showNormal() if self.parent.isMaximized() else self.parent.showMaximized()
    def mousePressEvent(self, event): self.startPos = event.globalPosition().toPoint(); self.pressing = True
    def mouseMoveEvent(self, event):
        if self.pressing: self.endPos = event.globalPosition().toPoint(); self.movement = self.endPos - self.startPos; self.parent.move(self.parent.pos() + self.movement); self.startPos = self.endPos
    def mouseReleaseEvent(self, event): self.pressing = False

class MessageBubble(QWidget):
    def __init__(self, main_text, citations=None, thinking_text=None):
        super().__init__()
        self.is_citations_expanded = False
        self.is_thinking_expanded = False
        self.citations_animation = None
        self.thinking_animation = None
        self.citations_container = None
        self.thinking_container = None
        self.container = QFrame()
        self.container.setObjectName("messageBubbleContainer")
        self.container.setMinimumWidth(450)
        self.container.setMaximumWidth(450)
        self.setProperty("isUser", False)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(8)
        self.message_label = QLabel(main_text)
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName("messageText")
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_label.setOpenExternalLinks(True)
        container_layout.addWidget(self.message_label)

        if thinking_text:
            self.toggle_thinking_button = QPushButton("Thinking Process")
            self.toggle_thinking_button.setObjectName("toggleDetailButton")
            self.toggle_thinking_button.setCheckable(True)
            self.toggle_thinking_button.clicked.connect(self.toggle_thinking)
            container_layout.addWidget(self.toggle_thinking_button, 0, Qt.AlignLeft)
            self.thinking_container = QFrame()
            self.thinking_container.setObjectName("thinkingContainer")
            self.thinking_container.setVisible(False)
            thinking_layout = QVBoxLayout(self.thinking_container)
            thinking_layout.setContentsMargins(8, 8, 8, 8)
            thinking_label = QLabel(thinking_text)
            thinking_label.setWordWrap(True)
            thinking_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            thinking_label.setObjectName("thinkingLabel")
            thinking_layout.addWidget(thinking_label)
            container_layout.addWidget(self.thinking_container)
            self.thinking_animation = QPropertyAnimation(self.thinking_container, b"maximumHeight")
            self.thinking_animation.setDuration(250)
            self.thinking_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.thinking_animation.finished.connect(self._on_thinking_animation_finished)
        
        if citations:
            source_count = len(citations)
            button_text = f"{source_count} Source{'s' if source_count != 1 else ''}"
            self.toggle_citations_button = QPushButton(button_text)
            self.toggle_citations_button.setObjectName("toggleDetailButton")
            self.toggle_citations_button.setCheckable(True)
            self.toggle_citations_button.clicked.connect(self.toggle_citations)
            container_layout.addWidget(self.toggle_citations_button, 0, Qt.AlignLeft)
            self.citations_container = QFrame()
            self.citations_container.setObjectName("citationsContainer")
            self.citations_container.setVisible(False)
            citations_layout = QVBoxLayout(self.citations_container)
            citations_layout.setContentsMargins(8, 8, 8, 8)
            citations_layout.setSpacing(6)
            for i, citation in enumerate(citations, 1):
                date_str = f" • {citation['date']}" if citation['date'] != "N/A" else ""
                citation_html = f"""
                <div style='margin-bottom: 4px;'>
                    <strong style='color: #4EC9B0;'>[{i}]</strong> 
                    <a href='{citation['url']}' style='color: #4EC9B0; text-decoration: none;'>{citation['title']}</a>
                    <span style='color: #888; font-size: 11px;'>{date_str}</span>
                </div>
                """
                citation_label = QLabel(citation_html)
                citation_label.setOpenExternalLinks(True)
                citation_label.setObjectName("citationLabel")
                citation_label.setWordWrap(True)
                citations_layout.addWidget(citation_label)
            container_layout.addWidget(self.citations_container)
            self.citations_animation = QPropertyAnimation(self.citations_container, b"maximumHeight")
            self.citations_animation.setDuration(250)
            self.citations_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.citations_animation.finished.connect(self._on_citations_animation_finished)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def _on_citations_animation_finished(self):
        if not self.is_citations_expanded:
            self.citations_container.setVisible(False)
    def _on_thinking_animation_finished(self):
        if not self.is_thinking_expanded:
            self.thinking_container.setVisible(False)

    def toggle_citations(self):
        if self.citations_animation: self.citations_animation.stop()
        self.is_citations_expanded = not self.is_citations_expanded
        if self.is_citations_expanded:
            self.citations_container.setVisible(True)
            self.citations_container.setMaximumHeight(16777215)
            self.citations_animation.setStartValue(0)
            self.citations_animation.setEndValue(self.citations_container.sizeHint().height())
        else:
            self.citations_animation.setStartValue(self.citations_container.height())
            self.citations_animation.setEndValue(0)
        self.citations_animation.start()

    def toggle_thinking(self):
        if self.thinking_animation: self.thinking_animation.stop()
        self.is_thinking_expanded = not self.is_thinking_expanded
        if self.is_thinking_expanded:
            self.toggle_thinking_button.setText("Hide")
            self.thinking_container.setVisible(True)
            self.thinking_container.setMaximumHeight(16777215)
            self.thinking_animation.setStartValue(0)
            self.thinking_animation.setEndValue(self.thinking_container.sizeHint().height())
        else:
            self.toggle_thinking_button.setText("Thinking Process")
            self.thinking_animation.setStartValue(self.thinking_container.height())
            self.thinking_animation.setEndValue(0)
        self.thinking_animation.start()