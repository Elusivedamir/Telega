import asyncio
import os
import subprocess
import sys
import traceback
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

import config
from gui_styles import STYLE, app_file, beep
from gui_auth import AuthMixin
from gui_channels import ChannelsMixin
from gui_pairs import PairsMixin
from gui_commenting import CommentingMixin
from utils import setup_logger

logger = setup_logger()

class MainWindow(QMainWindow, AuthMixin, ChannelsMixin, PairsMixin, CommentingMixin):
    code_requested = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    stats_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ===== ОПТИМИЗАЦИЯ ДЛЯ macOS =====
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        self.bot = None
        self.channels = []
        self.pairs = []
        self.is_task_running = False
        self.comment_text = ""
        self._loop = asyncio.get_event_loop()
        self._code_future = None
        self.load_thread = None
        self._active_task = None

        self.code_requested.connect(self._on_code_requested)
        self.log_signal.connect(self._handle_log_signal)
        self.progress_signal.connect(self._handle_progress_signal)
        self.stats_signal.connect(self._handle_stats_signal)

        self.setWindowTitle("Telegram AutoBot")
        self._log_path = config.get_log_file()
        self.resize(1000, 900)

        self.init_ui()
        self.setStyleSheet(STYLE)

        self._show_first_run_welcome_if_needed()

        # Отложенная инициализация
        QTimer.singleShot(100, self._delayed_init)

    def _show_first_run_welcome_if_needed(self):
        flag_path = os.path.join(os.path.expanduser("~"), ".telegramautobot_welcome_shown")
        if os.path.exists(flag_path):
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Добро пожаловать")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            "<b>Привет!</b><br><br>"
            "Чтобы начать, выполните 4 простых шага:<br>"
            "1. Перейдите в <b>Аккаунт</b> и авторизуйтесь<br>"
            "2. Добавьте каналы во вкладке <b>Каналы</b><br>"
            "3. Заполните связки во вкладке <b>Связки</b><br>"
            "4. Запустите комментирование во вкладке <b>Комментирование</b>"
        )
        msg.setInformativeText("Если нужно, откройте инструкцию через кнопку ниже или вкладку «Как пользоваться».")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        with open(flag_path, "w", encoding="utf-8") as f:
            f.write("shown")

    def _delayed_init(self):
        """Отложенная инициализация для предотвращения зависаний"""
        self.load_channels_from_file()
        self.load_pairs_from_file()
        self.load_account_from_file()
        self.load_proxy_from_config()
        self.update_status_labels()
        if self.bot:
            self.bot.load_stats_from_file()
            self.emit_stats(self.bot.get_stats())

    # ===============================
    # UI - 5 ВКЛАДОК
    # ===============================

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.tabs = QTabWidget()

        # ---------- 1. АККАУНТ ----------
        account = QWidget()
        al = QVBoxLayout(account)
        self.init_auth_ui(al)
        self.tabs.addTab(account, "Аккаунт")

        # ---------- 2. КАНАЛЫ ----------
        ch_tab = QWidget()
        chl = QVBoxLayout(ch_tab)
        self.init_channels_ui(chl)
        self.tabs.addTab(ch_tab, "Каналы")

        # ---------- 3. СВЯЗКИ ----------
        pair_tab = QWidget()
        pl = QVBoxLayout(pair_tab)
        self.init_pairs_ui(pl)
        self.tabs.addTab(pair_tab, "Связки")

        # ---------- 4. КОММЕНТИРОВАНИЕ ----------
        comment_tab = QWidget()
        col = QVBoxLayout(comment_tab)
        self.init_commenting_ui(col)
        self.tabs.addTab(comment_tab, "Комментирование")

        # ---------- 5. КАК ПОЛЬЗОВАТЬСЯ ----------
        help_tab = QWidget()
        help_layout = QVBoxLayout(help_tab)
        help_browser = QTextBrowser()
        help_browser.setOpenExternalLinks(False)
        help_browser.setHtml("""
        <h2>Как пользоваться TelegramAutoBot</h2>
        <ol>
            <li><b>Аккаунт</b> — войдите в Telegram, при необходимости укажите прокси.</li>
            <li><b>Каналы</b> — добавьте каналы, в которые нужно вступить, и нажмите «Вступить в каналы из списка».</li>
            <li><b>Связки</b> — укажите, где брать публикации, а куда отправлять комментарий. Первая колонка — ID канала, вторая — ID чата/обсуждения/группы.</li>
            <li><b>Комментирование</b> — заполните текст комментария и запустите процесс. Если нужно, остановите его кнопкой «Остановить».</li>
            <li><b>Лог</b> — следите за статусом работы и ошибками внизу окна.</li>
        </ol>
        <p><b>Полезно знать:</b></p>
        <ul>
            <li>Если нужен обычный чат, вторую колонку в связках можно оставить пустой.</li>
            <li>Для группы или обсуждения чаще всего нужен ID вида -1001234567890.</li>
            <li>Сначала лучше пройти авторизацию, затем добавить каналы и связки.</li>
        </ul>
        """)
        help_layout.addWidget(help_browser)
        self.tabs.addTab(help_tab, "Как пользоваться")

        # ---------- ЛОГ ----------
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # ОПТИМИЗАЦИЯ ЛОГА (ИСПРАВЛЕНО ДЛЯ PyQt6)
        self.log_box.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_box.document().setMaximumBlockCount(1000)

        layout.addWidget(self.tabs)
        help_row = QHBoxLayout()
        self.help_btn = QPushButton("📘 Инструкция для клиента")
        self.help_btn.clicked.connect(self.open_client_guide)
        self.quick_help_btn = QPushButton("❓ Помощь")
        self.quick_help_btn.clicked.connect(self.show_quick_help)
        self.open_log_btn = QPushButton("📄 Открыть лог")
        self.open_log_btn.clicked.connect(self.open_log_file)
        self.reset_stats_btn = QPushButton("🧹 Сбросить статистику")
        self.reset_stats_btn.clicked.connect(self.reset_stats)
        help_row.addWidget(self.help_btn)
        help_row.addWidget(self.quick_help_btn)
        help_row.addWidget(self.open_log_btn)
        help_row.addWidget(self.reset_stats_btn)
        help_row.addStretch()
        layout.addLayout(help_row)
        self.stats_summary_label = QLabel("📊 Статистика: ещё не запускалась")
        self.stats_summary_label.setObjectName("status_label")
        layout.addWidget(self.stats_summary_label)
        layout.addWidget(QLabel(f"Лог работы (файл: {self._log_path})"))
        layout.addWidget(self.log_box)

    # ===============================
    # LOG
    # ===============================

    def open_client_guide(self):
        try:
            # Ищем файл с новым названием
            guide_path = os.path.join(os.path.dirname(__file__), "СТЯ  С.md")
            if sys.platform == "darwin":
                subprocess.Popen(["open", guide_path])
            elif os.name == "nt":
                os.startfile(guide_path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", guide_path])
        except Exception as e:
            self.log(f"❌ Не удалось открыть инструкцию: {e}")

    def open_log_file(self):
        try:
            if os.path.exists(self._log_path):
                if sys.platform == "darwin":
                    subprocess.Popen(["open", self._log_path])
                elif os.name == "nt":
                    os.startfile(self._log_path)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", self._log_path])
            else:
                self.log(f"⚠️ Лог-файл ещё не создан: {self._log_path}")
        except Exception as e:
            self.log(f"❌ Не удалось открыть лог-файл: {e}")

    def reset_stats(self):
        if self.bot:
            self.bot.reset_stats()
            self.emit_stats(self.bot.get_stats())
            self.log("🧹 Статистика сброшена")
        else:
            self.log("⚠️ Сначала авторизуйтесь, чтобы сбросить статистику")

    def show_quick_help(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Краткая помощь")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            "<b>Краткий план работы:</b><br><br>"
            "1. Авторизуйтесь во вкладке <b>Аккаунт</b><br>"
            "2. Добавьте каналы во вкладке <b>Каналы</b><br>"
            "3. Заполните связки во вкладке <b>Связки</b><br>"
            "4. Запустите процесс во вкладке <b>Комментирование</b>"
        )
        msg.setInformativeText("Если нужно, откройте полную инструкцию через кнопку «Инструкция для клиента».")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def log(self, text):
        self.log_signal.emit(text)

    def emit_stats(self, stats=None):
        if stats is None and self.bot:
            stats = self.bot.get_stats()
        if stats is not None:
            self.stats_signal.emit(stats)

    def validate_before_start(self, require_comment=False):
        from utils import format_validation_errors, validate_runtime_state
        issues = validate_runtime_state(
            channels=self.channels,
            pairs=self.pairs,
            comment_text=self.comment_text if hasattr(self, "comment_text") else "",
            require_comment=require_comment,
        )
        if issues:
            message = f"⚠️ Невозможно запустить: {format_validation_errors(issues)}"
            self.log(message)
            return False
        return True

    @pyqtSlot(str)
    def _handle_log_signal(self, text):
        if not hasattr(self, "log_box") or self.log_box is None:
            return
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_box.append(f"{timestamp} | {text}")
        logger.info(text)

        scrollbar = self.log_box.verticalScrollBar()
        is_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
        if is_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(dict)
    def _handle_stats_signal(self, stats):
        if not hasattr(self, "stats_label") or self.stats_label is None:
            return
        self.stats_label.setText(
            f"📊 Сегодня: {stats.get('sent', 0)}/{config.DAILY_LIMIT} | "
            f"обработано: {stats.get('processed', 0)} | "
            f"пропущено: {stats.get('skipped', 0)} | "
            f"ошибки: {stats.get('errors', 0)}"
        )
        if hasattr(self, "stats_summary_label") and self.stats_summary_label is not None:
            self.stats_summary_label.setText(
                f"📈 Сессия: отправлено {stats.get('sent', 0)}, "
                f"обработано {stats.get('processed', 0)}, "
                f"пропущено {stats.get('skipped', 0)}, "
                f"ошибки {stats.get('errors', 0)}"
            )

    # ===============================
    # ASYNC SAFE
    # ===============================

    def run_async_safe(self, coro):
        try:
            if getattr(self._loop, "is_closed", lambda: True)():
                return None
            task = self._loop.create_task(coro)
            self._active_task = task

            def _on_done(t):
                if self._active_task is t:
                    self._active_task = None
                if t.cancelled():
                    return
                exc = t.exception()
                if exc is not None:
                    self.log(f"❌ Необработанная ошибка: {exc}")
                    logger.error("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))

            task.add_done_callback(_on_done)
            return task
        except RuntimeError:
            return None

    def cancel_active_task(self):
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()

    def progress(self, current, total):
        self.progress_signal.emit(current, total)

    @pyqtSlot(int, int)
    def _handle_progress_signal(self, current, total):
        self._handle_log_signal(f"📊 Прогресс: {current}/{total}")

    # ===============================
    # CLOSE
    # ===============================

    def closeEvent(self, event):
        self.cancel_active_task()
        try:
            if self.bot:
                self.run_async_safe(self.bot.disconnect())
        except Exception:
            pass
        event.accept()