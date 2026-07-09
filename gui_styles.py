import asyncio
import os

import config

# ===== ФИКС ДЛЯ ASYNCIO =====
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

APP_NAME = "TelegramAutoBot"


def app_dir():
    return config.get_app_dir()


def app_file(name):
    return os.path.join(app_dir(), name)


def beep():
    from PyQt6.QtWidgets import QApplication
    QApplication.beep()

# ===== СТИЛЬ ДЛЯ macOS =====
FONT_FAMILY = 'system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Arial, sans-serif'
STYLE = """
QMainWindow, QWidget {{
    background-color:#2b2b2b;
    color:#d4d4d4;
    font-family: {font_family};
    font-size: 13px;
}}
QTabWidget::pane {{
    border: 1px solid #3c3c3c;
    background: #2b2b2b;
}}
QTabBar::tab {{
    background: #3c3c3c;
    color: #d4d4d4;
    padding: 8px 16px;
    margin-right: 2px;
    border: none;
}}
QTabBar::tab:selected {{
    background: #2b2b2b;
    border-bottom: 2px solid #3390ec;
    color: white;
}}
QTabBar::tab:hover {{
    background: #4a4a4a;
}}
QGroupBox {{
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    background: #2b2b2b;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QListWidget, QTableWidget {{
    background: #3c3c3c;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 4px 6px;
    color: white;
    selection-background-color: #3390ec;
}}
QPushButton {{
    background: #4a4a4a;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
    color: white;
    border: none;
    min-height: 20px;
}}
QPushButton:hover {{
    background: #5a5a5a;
}}
QPushButton:pressed {{
    background: #3a3a3a;
}}
QPushButton:disabled {{
    background: #333333;
    color: #777777;
}}
QTextEdit {{
    background: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}}
QLabel#status_label {{
    font-size: 14px;
    font-weight: bold;
}}
QTableWidget::item {{
    background: #2b2b2b;
    color: #d4d4d4;
    padding: 4px;
}}
QTableWidget::item:selected {{
    background: #3390ec;
}}
QHeaderView::section {{
    background: #3c3c3c;
    color: #d4d4d4;
    padding: 4px;
    border: none;
    border-right: 1px solid #4a4a4a;
}}
QScrollBar:vertical {{
    background: #2b2b2b;
    width: 12px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: #4a4a4a;
    border-radius: 6px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: #5a5a5a;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QComboBox {{
    background: #3c3c3c;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 4px 6px;
    color: white;
    min-height: 20px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: #3c3c3c;
    color: white;
    selection-background-color: #3390ec;
}}
""".format(font_family=FONT_FAMILY)
