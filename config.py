import json
import logging
import os
import asyncio
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any

try:
    import keyring
except Exception:
    keyring = None

try:
    from cryptography.fernet import Fernet
    import base64
    import hashlib
    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False

def _get_logger():
    """Ленивая инициализация логгера."""
    return logging.getLogger("TelegramAutoBot")

APP_NAME = "TelegramAutoBot"
APP_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
CONFIG_FILE = APP_DIR / "settings.json"
SERVICE_NAME = APP_NAME


def get_app_dir() -> str:
    """Получить директорию приложения с проверкой прав"""
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Проверяем права записи
        test_file = APP_DIR / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        
        return str(APP_DIR)
    except PermissionError:
        logger = _get_logger()
        logger.error(f"❌ Нет прав на запись в {APP_DIR}")
        # Fallback: /tmp
        fallback = Path("/tmp") / "TelegramAutoBot"
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback)
    except Exception as e:
        logger = _get_logger()
        logger.error(f"❌ Ошибка создания директории: {e}")
        return str(Path.home() / ".telegramautobot")


def get_config_file() -> str:
    return str(CONFIG_FILE)


def get_log_file() -> str:
    return str(APP_DIR / "bot.log")


def get_history_file() -> str:
    return str(APP_DIR / "processed_posts.json")


def get_stats_file() -> str:
    return str(APP_DIR / "stats.json")


def get_session_path(session_name: str) -> str:
    return str(APP_DIR / f"{session_name}.session")


# ========================
# ШИФРОВАНИЕ СЕКРЕТОВ
# ========================

class CryptoManager:
    """Управление шифрованием на основе machine ID"""
    
    def __init__(self):
        self._cipher = self._init_cipher()
    
    def _init_cipher(self) -> Optional[Fernet]:
        """Инициализация шифра на основе machine ID + username"""
        if not HAS_CRYPTO:
            return None
        
        try:
            import uuid
            import getpass
            
            machine_id = str(uuid.getnode())
            username = getpass.getuser()
            key_material = f"{machine_id}:{username}:{APP_NAME}".encode()
            
            key = base64.urlsafe_b64encode(
                hashlib.sha256(key_material).digest()
            )
            return Fernet(key)
        except Exception as e:
            _get_logger().warning(f"⚠️ Не удалось инициализировать шифр: {e}")
            return None
    
    def encrypt(self, data: str) -> str:
        """Зашифровать строку"""
        if not self._cipher:
            return data
        
        try:
            encrypted = self._cipher.encrypt(data.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            _get_logger().warning(f"Ошибка шифрования: {e}")
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        """Расшифровать строку"""
        if not self._cipher:
            return encrypted_data
        
        try:
            encrypted = base64.b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            _get_logger().warning(f"Ошибка расшифрования: {e}")
            return ""


# ========================
# DATACLASS ДЛЯ НАСТРОЕК
# ========================

@dataclass
class BotSettings:
    """Потокобезопасные настройки бота"""
    join_delay: float = 30
    comment_delay_min: float = 15.0
    comment_delay_max: float = 45.0
    daily_limit: int = 40
    sent_today: int = 0
    last_reset_date: str = ""
    comment_variants: list = field(default_factory=lambda: [
        "Интересная мысль, спасибо за пост!",
        "Полностью согласен с автором.",
        "А ведь если подумать, тут все не так однозначно.",
        "Отличный разбор ситуации, жду продолжения.",
        "Крутой контент, сохранил себе!"
    ])
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'BotSettings':
        return BotSettings(
            join_delay=data.get("join_delay", 30),
            comment_delay_min=data.get("comment_delay_min", 15.0),
            comment_delay_max=data.get("comment_delay_max", 45.0),
            daily_limit=data.get("daily_limit", 40),
            sent_today=data.get("sent_today", 0),
            last_reset_date=data.get("last_reset_date", ""),
            comment_variants=data.get("comment_variants", []),
        )


# ========================
# МЕНЕДЖЕР СЕКРЕТОВ
# ========================

class SecureSecretsManager:
    """Управление секретами с шифрованием или keyring"""
    
    def __init__(self):
        self.secrets_file = APP_DIR / "secrets.json"
        self._crypto = CryptoManager()
        self._lock = asyncio.Lock() if HAS_CRYPTO else None
    
    def _get_keyring(self):
        if keyring is None:
            return None
        return keyring
    
    def _load_fallback_secrets(self) -> dict:
        """Загружает секреты из fallback файла"""
        try:
            if not self.secrets_file.exists():
                return {}
            
            with open(self.secrets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Пытаемся расшифровать если данные зашифрованы
            if HAS_CRYPTO and self._crypto._cipher and "_encrypted" in data:
                try:
                    encrypted_data = data["_encrypted"]
                    decrypted = self._crypto.decrypt(encrypted_data)
                    return json.loads(decrypted)
                except Exception as e:
                    _get_logger().warning(f"⚠️ Не удалось расшифровать secrets: {e}")
                    return {}
            
            return data
        except Exception as e:
            _get_logger().debug(f"Ошибка чтения fallback secrets: {e}")
            return {}
    
    def _save_fallback_secrets(self, data: dict) -> None:
        """Сохраняет секреты в fallback файл (шифруя если возможно)"""
        try:
            self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
            
            if HAS_CRYPTO and self._crypto._cipher:
                # Шифруем данные
                plaintext = json.dumps(data, ensure_ascii=False)
                encrypted = self._crypto.encrypt(plaintext)
                to_save = {"_encrypted": encrypted}
            else:
                to_save = data
            
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=4)
            
            # Защищаем файл от чтения другими пользователями
            if hasattr(os, 'chmod'):
                os.chmod(self.secrets_file, 0o600)
        except Exception as e:
            _get_logger().error(f"❌ Ошибка сохранения fallback secrets: {e}")
    
    def set_secret(self, name: str, value: str) -> None:
        """Сохранить секрет"""
        if not value:
            return
        
        backend = self._get_keyring()
        if backend:
            try:
                backend.set_password(SERVICE_NAME, name, value)
                return
            except Exception as e:
                _get_logger().debug(f"Не удалось сохранить в keyring, используем fallback: {e}")
        
        # Fallback: сохраняем в файл (зашифрованный)
        secrets = self._load_fallback_secrets()
        secrets[name] = value
        self._save_fallback_secrets(secrets)
    
    def get_secret(self, name: str, default: str = None) -> Optional[str]:
        """Получить секрет"""
        backend = self._get_keyring()
        if backend:
            try:
                value = backend.get_password(SERVICE_NAME, name)
                if value is not None:
                    return value
            except Exception as e:
                _get_logger().debug(f"Не удалось прочитать из keyring: {e}")
        
        # Fallback: читаем из файла
        secrets = self._load_fallback_secrets()
        return secrets.get(name, default)
    
    def delete_secret(self, name: str) -> None:
        """Удалить секрет"""
        backend = self._get_keyring()
        if backend:
            try:
                backend.delete_password(SERVICE_NAME, name)
                return
            except Exception as e:
                _get_logger().debug(f"Не удалось удалить из keyring: {e}")
        
        # Fallback: удаляем из файла
        secrets = self._load_fallback_secrets()
        if name in secrets:
            del secrets[name]
            self._save_fallback_secrets(secrets)
    
    def save_auth_credentials(self, api_id: str, api_hash: str, phone: str) -> None:
        self.set_secret("api_id", str(api_id))
        self.set_secret("api_hash", str(api_hash))
        self.set_secret("phone", str(phone))
    
    def load_auth_credentials(self) -> dict:
        return {
            "api_id": self.get_secret("api_id", ""),
            "api_hash": self.get_secret("api_hash", ""),
            "phone": self.get_secret("phone", ""),
        }
    
    def save_proxy_settings(self, proxy_type: str, proxy_ip: str, proxy_port: str, 
                           proxy_user: str, proxy_pass: str) -> None:
        self.set_secret("proxy_type", proxy_type)
        self.set_secret("proxy_ip", proxy_ip)
        self.set_secret("proxy_port", proxy_port)
        self.set_secret("proxy_user", proxy_user)
        self.set_secret("proxy_pass", proxy_pass)
    
    def load_proxy_settings(self) -> dict:
        return {
            "proxy_type": self.get_secret("proxy_type", "SOCKS5") or "SOCKS5",
            "proxy_ip": self.get_secret("proxy_ip", "") or "",
            "proxy_port": self.get_secret("proxy_port", "") or "",
            "proxy_user": self.get_secret("proxy_user", "") or "",
            "proxy_pass": self.get_secret("proxy_pass", "") or "",
        }


# ========================
# МЕНЕДЖЕР НАСТРОЕК (ASYNC)
# ========================

class SettingsManager:
    """Потокобезопасный асинхронный менеджер настроек"""
    
    def __init__(self):
        self._settings = BotSettings()
        self._lock = asyncio.Lock()
        self._config_file = CONFIG_FILE
        self._secrets_manager = SecureSecretsManager()
    
    async def load(self):
        """Загрузить настройки из файла"""
        async with self._lock:
            try:
                if self._config_file.exists():
                    with open(self._config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._settings = BotSettings.from_dict(data)
                    
                    # Проверяем дату и сбрасываем счётчик если нужно
                    today = datetime.now().strftime("%Y-%m-%d")
                    if self._settings.last_reset_date != today:
                        self._settings.sent_today = 0
                        self._settings.last_reset_date = today
                        await self.save()
                else:
                    self._settings = BotSettings()
            except Exception as e:
                _get_logger().error(f"❌ Ошибка чтения settings.json: {e}")
                self._settings = BotSettings()
    
    async def save(self):
        """Сохранить настройки в файл (БЕЗ доп лока, используется существующий)"""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings.to_dict(), f, ensure_ascii=False, indent=4)
        except Exception as e:
            _get_logger().error(f"❌ Ошибка сохранения settings.json: {e}")
    
    async def get_settings(self) -> BotSettings:
        """Получить копию текущих настроек"""
        async with self._lock:
            return BotSettings.from_dict(self._settings.to_dict())
    
    async def update_settings(self, settings: BotSettings) -> None:
        """Обновить настройки"""
        async with self._lock:
            self._settings = settings
            await self.save()
    
    async def increment_sent_today(self) -> int:
        """Атомарно увеличить счётчик (КРИТИЧЕСКОЕ: используется везде!)"""
        async with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Проверяем дату и сбрасываем если нужно
            if self._settings.last_reset_date != today:
                self._settings.sent_today = 0
                self._settings.last_reset_date = today
            
            self._settings.sent_today += 1
            await self.save()
            return self._settings.sent_today
    
    async def get_sent_today(self) -> int:
        """Получить количество отправленных сегодня"""
        async with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            if self._settings.last_reset_date != today:
                self._settings.sent_today = 0
                self._settings.last_reset_date = today
                await self.save()
            return self._settings.sent_today
    
    async def get_remaining_today(self) -> int:
        """Получить оставшихся комментариев сегодня"""
        sent = await self.get_sent_today()
        async with self._lock:
            return max(0, self._settings.daily_limit - sent)
    
    async def reset_daily_counter(self):
        """Сбросить дневной счётчик"""
        async with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            self._settings.sent_today = 0
            self._settings.last_reset_date = today
            await self.save()


# ========================
# ГЛОБАЛЬНЫЕ ЭКЗЕМПЛЯРЫ
# ========================

get_app_dir()  # Инициализируем директорию

settings_manager = SettingsManager()
secrets_manager = SecureSecretsManager()

# Старые функции для обратной совместимости
def save_auth_credentials(api_id: str, api_hash: str, phone: str) -> None:
    secrets_manager.save_auth_credentials(api_id, api_hash, phone)

def load_auth_credentials() -> dict:
    return secrets_manager.load_auth_credentials()

def save_proxy_settings(proxy_type: str, proxy_ip: str, proxy_port: str, 
                       proxy_user: str, proxy_pass: str) -> None:
    secrets_manager.save_proxy_settings(proxy_type, proxy_ip, proxy_port, proxy_user, proxy_pass)

def load_proxy_settings() -> dict:
    return secrets_manager.load_proxy_settings()

def get_secret(name: str, default: str = None) -> Optional[str]:
    return secrets_manager.get_secret(name, default)

def set_secret(name: str, value: str) -> None:
    secrets_manager.set_secret(name, value)

def delete_secret(name: str) -> None:
    secrets_manager.delete_secret(name)
