import asyncio
import os
from PyQt6.QtWidgets import *

try:
    from qasync import asyncSlot
except Exception:  # pragma: no cover - fallback
    def asyncSlot(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from gui_styles import app_file


class ChannelsMixin:
    """Миксин для работы с каналами"""

    def init_channels_ui(self, layout):
        """Инициализация UI для вкладки каналов"""
        self.channels_list = QListWidget()
        layout.addWidget(QLabel("Список каналов для вступления:"))
        layout.addWidget(self.channels_list)

        row = QHBoxLayout()
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("@channel, https://t.me/channel или t.me/+invite")
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_channel)
        row.addWidget(self.add_edit)
        row.addWidget(self.add_btn)
        layout.addLayout(row)

        self.del_ch_btn = QPushButton("Удалить выбранный канал")
        self.del_ch_btn.clicked.connect(self.delete_channel)
        layout.addWidget(self.del_ch_btn)

        self.dry_run_checkbox = QCheckBox("🧪 Режим теста (без реальной отправки)")
        self.dry_run_checkbox.toggled.connect(self.set_dry_run_mode)
        layout.addWidget(self.dry_run_checkbox)

        self.join_btn = QPushButton("Вступить в каналы из списка")
        self.join_btn.clicked.connect(self.start_joining)
        layout.addWidget(self.join_btn)

        self.pause_btn = QPushButton("⏸ Пауза/Продолжить")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)

    def load_channels_from_file(self):
        path = app_file("channels.txt")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.channels = [x.strip() for x in f.readlines() if x.strip()]
            self.refresh_channels()
        except Exception as e:
            self.log(f"Ошибка загрузки каналов: {e}")

    def save_channels(self):
        try:
            with open(app_file("channels.txt"), "w", encoding="utf-8") as f:
                for c in self.channels:
                    f.write(c + "\n")
        except Exception as e:
            self.log(f"Ошибка сохранения каналов: {e}")

    def refresh_channels(self):
        self.channels_list.clear()
        self.channels_list.addItems(self.channels)

    def add_channel(self):
        value = self.add_edit.text().strip()
        if value:
            self.channels.append(value)
            self.save_channels()
            self.refresh_channels()
            self.add_edit.clear()
            self.log(f"💾 Сохранён канал: {value}")

    def delete_channel(self):
        current_row = self.channels_list.currentRow()
        if current_row >= 0:
            self.channels.pop(current_row)
            self.save_channels()
            self.refresh_channels()

    @asyncSlot()
    async def start_joining(self):
        if not self.bot or not self.bot.is_connected:
            self.log("❌ Сначала авторизуйтесь")
            return

        if not self.validate_before_start(require_comment=False):
            return

        if self.is_task_running:
            self.log("⚠️ Задача уже выполняется")
            return

        self.dry_run_mode = bool(self.dry_run_checkbox.isChecked())
        if self.bot:
            self.bot.reset_stop()
            self.bot.resume()
            self.bot.set_dry_run(self.dry_run_mode)

        self.is_task_running = True
        self.join_btn.setEnabled(False)
        self.start_comment_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)

        await self.run_join_task()

    def stop_task(self):
        if self.bot:
            self.bot.request_stop()
            self.cancel_active_task()
            self.bot.resume()
            self.log("🛑 Остановка...")

    def toggle_pause(self):
        if not self.bot or not self.is_task_running:
            self.log("⚠️ Нет активной задачи для паузы")
            return
        if self.bot.pause_event.is_set():
            self.bot.pause()
            self.log("⏸ Пауза")
        else:
            self.bot.resume()
            self.log("▶️ Продолжено")

    def set_dry_run_mode(self, checked):
        self.dry_run_mode = bool(checked)
        if self.bot:
            self.bot.set_dry_run(self.dry_run_mode)

    async def run_join_task(self):
        import traceback
        from utils import setup_logger
        logger = setup_logger()

        try:
            self.log("🚀 Вступление в каналы...")
            self.bot.reset_stop()

            result = await self.bot.join_channels(
                self.channels,
                progress_cb=self.progress,
                status_cb=self.log,
                stats_cb=self.emit_stats
            )

            if result:
                self.log("✅ Вступление завершено")
            else:
                self.log("⏹ Остановлено")

        except asyncio.CancelledError:
            self.log("🛑 Задача вступления прервана")
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.is_task_running = False
            self.join_btn.setEnabled(True)
            self.start_comment_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
