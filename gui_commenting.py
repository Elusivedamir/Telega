import asyncio
import random
import traceback
from PyQt6.QtWidgets import *

try:
    from qasync import asyncSlot
except Exception:  # pragma: no cover - fallback
    def asyncSlot(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from utils import setup_logger
import config

logger = setup_logger()


class CommentingMixin:
    """Миксин для комментирования"""

    def init_commenting_ui(self, layout):
        """Инициализация UI для вкладки комментирования"""
        # Варианты комментариев
        layout.addWidget(QLabel("📝 Варианты комментариев (случайный выбор):"))
        self.comment_variants = []
        for i in range(5):
            variant_layout = QHBoxLayout()
            label = QLabel(f"Вариант {i+1}:")
            edit = QTextEdit()
            edit.setMinimumHeight(60)
            edit.setPlaceholderText(f"Вариант комментария #{i+1}")
            if i < len(config.COMMENT_VARIANTS):
                edit.setText(config.COMMENT_VARIANTS[i])
            edit.textChanged.connect(lambda checked, idx=i: self.save_comment_variant(idx))
            self.comment_variants.append(edit)
            variant_layout.addWidget(label)
            variant_layout.addWidget(edit)
            layout.addLayout(variant_layout)

        # Кнопки управления (только 2)
        btn_row = QHBoxLayout()
        self.start_comment_btn = QPushButton("▶️ Запустить комментирование")
        self.start_comment_btn.clicked.connect(self.start_commenting)

        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_task)

        btn_row.addWidget(self.start_comment_btn)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

    def save_comment_variant(self, index):
        if index < len(self.comment_variants):
            config.COMMENT_VARIANTS[index] = self.comment_variants[index].toPlainText()
            config.save_settings()
            self.log(f"💾 Сохранён вариант комментария #{index + 1}")

    def get_random_comment(self):
        valid = [c for c in config.COMMENT_VARIANTS if c.strip()]
        return random.choice(valid) if valid else ""

    @asyncSlot()
    async def start_commenting(self):
        if not self.bot or not self.bot.is_connected:
            self.log("❌ Сначала авторизуйтесь")
            return

        if not self.validate_before_start(require_comment=True):
            return

        text = self.get_random_comment()

        if self.is_task_running:
            self.log("⚠️ Задача уже выполняется")
            return

        if self.bot:
            self.bot.reset_stop()
            self.bot.resume()
            self.bot.set_dry_run(bool(getattr(self, "dry_run_mode", False)))

        self.comment_text = text
        self.is_task_running = True
        self.stop_btn.setEnabled(True)
        self.start_comment_btn.setEnabled(False)
        self.join_btn.setEnabled(False)

        await self.run_comment_task()

    async def run_comment_task(self):
        try:
            self.log("🚀 Запуск комментирования...")
            self.bot.reset_stop()

            result = await self.bot.run_commenting_with_ids(
                [],
                self.pairs,
                self.comment_text,
                progress_cb=self.progress,
                status_cb=self.log,
                time_cb=self.log,
                stats_cb=self.emit_stats
            )

            if result:
                self.log("✅ Комментирование завершено")
            else:
                self.log("⏹ Остановлено")

        except asyncio.CancelledError:
            self.log("🛑 Задача комментирования прервана")
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.is_task_running = False
            self.stop_btn.setEnabled(False)
            self.start_comment_btn.setEnabled(True)
            self.join_btn.setEnabled(True)
            self.update_status_labels()

    def stop_task(self):
        if self.bot:
            self.bot.request_stop()
            self.cancel_active_task()
            self.log("🛑 Остановка...")
