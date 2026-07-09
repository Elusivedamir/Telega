import asyncio
import os
import traceback
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

try:
    from qasync import asyncSlot
except Exception:  # pragma: no cover - fallback for environments without qasync
    def asyncSlot(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

import config
from gui_styles import app_file, beep
from utils import setup_logger

logger = setup_logger()


class AuthMixin:
    """Миксин для авторизации и прокси настроек"""

    def init_auth_ui(self, layout):
        """Инициализация UI для вкладки авторизации"""
        # API настройки
        api_group = QGroupBox("Данные аккаунта Telegram")
        api_layout = QGridLayout()
        api_layout.addWidget(QLabel("API ID:"), 0, 0)
        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("api_id")
        api_layout.addWidget(self.api_id_edit, 0, 1)

        api_layout.addWidget(QLabel("API Hash:"), 1, 0)
        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("api_hash")
        api_layout.addWidget(self.api_hash_edit, 1, 1)

        api_layout.addWidget(QLabel("Телефон:"), 2, 0)
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("+71234567890")
        api_layout.addWidget(self.phone_edit, 2, 1)
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # Прокси настройки
        proxy_group = QGroupBox("Настройки прокси (опционально)")
        proxy_layout = QGridLayout()

        proxy_layout.addWidget(QLabel("Тип прокси:"), 0, 0)
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["SOCKS5", "HTTP"])
        self.proxy_type_combo.setCurrentText(config.PROXY_TYPE)
        self.proxy_type_combo.currentTextChanged.connect(self.save_proxy_settings)
        proxy_layout.addWidget(self.proxy_type_combo, 0, 1)

        proxy_layout.addWidget(QLabel("IP адрес:"), 1, 0)
        self.proxy_ip_edit = QLineEdit()
        self.proxy_ip_edit.setText(config.PROXY_IP)
        self.proxy_ip_edit.setPlaceholderText("127.0.0.1")
        self.proxy_ip_edit.textChanged.connect(self.save_proxy_settings)
        proxy_layout.addWidget(self.proxy_ip_edit, 1, 1)

        proxy_layout.addWidget(QLabel("Порт:"), 2, 0)
        self.proxy_port_edit = QLineEdit()
        self.proxy_port_edit.setText(config.PROXY_PORT)
        self.proxy_port_edit.setPlaceholderText("1080")
        self.proxy_port_edit.textChanged.connect(self.save_proxy_settings)
        proxy_layout.addWidget(self.proxy_port_edit, 2, 1)

        proxy_layout.addWidget(QLabel("Логин:"), 3, 0)
        self.proxy_user_edit = QLineEdit()
        self.proxy_user_edit.setText(config.PROXY_USER)
        self.proxy_user_edit.setPlaceholderText("username (опционально)")
        self.proxy_user_edit.textChanged.connect(self.save_proxy_settings)
        proxy_layout.addWidget(self.proxy_user_edit, 3, 1)

        proxy_layout.addWidget(QLabel("Пароль:"), 4, 0)
        self.proxy_pass_edit = QLineEdit()
        self.proxy_pass_edit.setText(config.PROXY_PASS)
        self.proxy_pass_edit.setPlaceholderText("password (опционально)")
        self.proxy_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxy_pass_edit.textChanged.connect(self.save_proxy_settings)
        proxy_layout.addWidget(self.proxy_pass_edit, 4, 1)

        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # Кнопка авторизации
        self.auth_btn = QPushButton("Авторизоваться")
        self.auth_btn.clicked.connect(self.authorize)
        layout.addWidget(self.auth_btn)

        self.auth_status = QLabel("Не авторизован")
        self.auth_status.setObjectName("status_label")
        self.auth_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.auth_status.setStyleSheet("color: #ff6b6b;")
        layout.addWidget(self.auth_status)

        # Статистика
        self.stats_label = QLabel()
        self.stats_label.setObjectName("status_label")
        self.stats_label.setStyleSheet("color: #50fa7b;")
        layout.addWidget(self.stats_label)
        layout.addStretch()

    def save_proxy_settings(self):
        config.PROXY_TYPE = self.proxy_type_combo.currentText()
        config.PROXY_IP = self.proxy_ip_edit.text().strip()
        config.PROXY_PORT = self.proxy_port_edit.text().strip()
        config.PROXY_USER = self.proxy_user_edit.text().strip()
        config.PROXY_PASS = self.proxy_pass_edit.text().strip()
        config.save_proxy_settings(
            config.PROXY_TYPE,
            config.PROXY_IP,
            config.PROXY_PORT,
            config.PROXY_USER,
            config.PROXY_PASS,
        )
        config.save_settings()

    def load_proxy_from_config(self):
        self.proxy_type_combo.setCurrentText(config.PROXY_TYPE)
        self.proxy_ip_edit.setText(config.PROXY_IP)
        self.proxy_port_edit.setText(config.PROXY_PORT)
        self.proxy_user_edit.setText(config.PROXY_USER)
        self.proxy_pass_edit.setText(config.PROXY_PASS)

    def get_proxy_dict(self):
        if not config.PROXY_IP or not config.PROXY_PORT:
            return None
        return {
            "proxy_type": config.PROXY_TYPE.lower(),
            "addr": config.PROXY_IP,
            "port": config.PROXY_PORT,
            "username": config.PROXY_USER if config.PROXY_USER else "",
            "password": config.PROXY_PASS if config.PROXY_PASS else ""
        }

    def load_account_from_file(self):
        try:
            credentials = config.load_auth_credentials()
            api_id = credentials.get("api_id", "") or ""
            api_hash = credentials.get("api_hash", "") or ""
            phone = credentials.get("phone", "") or ""
            if api_id or api_hash or phone:
                self.api_id_edit.setText(api_id)
                self.api_hash_edit.setText(api_hash)
                self.phone_edit.setText(phone)
        except Exception as e:
            self.log(f"Ошибка загрузки данных аккаунта: {e}")

    def save_account(self):
        try:
            config.save_auth_credentials(
                self.api_id_edit.text().strip(),
                self.api_hash_edit.text().strip(),
                self.phone_edit.text().strip(),
            )
        except Exception as e:
            self.log(f"Ошибка сохранения данных аккаунта: {e}")

    @asyncSlot()
    async def authorize(self):
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()

        if not api_id or not api_hash or not phone:
            self.log("❌ Заполните все поля")
            return

        try:
            from telegram_bot import TelegramBot
            proxy_dict = self.get_proxy_dict()

            self.bot = TelegramBot(
                int(api_id),
                api_hash,
                session_name=f"session_{phone.replace('+', '')}",
                proxy=proxy_dict,
                code_callback=self.ask_code_async
            )
            self.bot.phone = phone
            self.save_account()
            self.auth_btn.setEnabled(False)
            await self.connect_bot()
        except ValueError:
            self.log("❌ API ID должен быть числом")

    async def connect_bot(self):
        self.auth_status.setText("⏳ Подключение...")
        self.auth_status.setStyleSheet("color: #ffb86c;")

        try:
            result = await self.bot.connect()
        except Exception as e:
            result = False
            self.log(f"❌ Ошибка: {e}")
            logger.error(traceback.format_exc())

        if result:
            self.auth_status.setText("✅ Авторизован")
            self.auth_status.setStyleSheet("color: #50fa7b;")
            self.log("✅ Telegram подключен")
            if self.get_proxy_dict():
                self.log(f"🌐 Прокси: {config.PROXY_TYPE} {config.PROXY_IP}:{config.PROXY_PORT}")
            beep()
        else:
            self.auth_status.setText("❌ Ошибка")
            self.auth_status.setStyleSheet("color: #ff5555;")

        self.auth_btn.setEnabled(True)
        self.update_status_labels()

    async def ask_code_async(self, message):
        self._code_future = self._loop.create_future()
        self.code_requested.emit(message)
        return await self._code_future

    @pyqtSlot(str)
    def _on_code_requested(self, message):
        dialog = QDialog(self)
        dialog.setWindowTitle("Telegram Авторизация")
        dialog.setModal(True)
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(message))

        input_edit = QLineEdit()
        if "пароль" in message.lower():
            input_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(input_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._code_future.set_result(input_edit.text().strip())
        else:
            self._code_future.set_result("")

    def update_status_labels(self):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        if config.LAST_RESET_DATE != today:
            config.SENT_TODAY = 0
            config.LAST_RESET_DATE = today
            config.save_settings()

        remaining = config.get_remaining_today()
        self.stats_label.setText(
            f"📊 Сегодня: {config.SENT_TODAY}/{config.DAILY_LIMIT} "
            f"(осталось: {remaining})"
        )
