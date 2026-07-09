"""
✅ Unit-тесты для TelegramBot

Запуск:
    pytest fixed_test_telegram_bot.py -v

Для asyncio тестов нужен:
    pip install pytest-asyncio
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fixed_telegram_bot import TelegramBot
from fixed_config import BotSettings, SettingsManager, SecureSecretsManager


class TestTelegramBotBasics:
    """Базовые тесты TelegramBot"""
    
    @pytest.fixture
    def bot(self):
        """Создаёт экземпляр бота для тестов"""
        return TelegramBot(
            api_id=12345,
            api_hash="test_hash_123",
            session_name="test_session",
            proxy=None,
            code_callback=None
        )
    
    def test_bot_initialization(self, bot):
        """Проверка инициализации бота"""
        assert bot.api_id == 12345
        assert bot.api_hash == "test_hash_123"
        assert bot.session_name == "test_session"
        assert bot.is_connected is False
        assert bot.stop_event.is_set() is False
        assert bot.pause_event.is_set() is True
        assert bot.dry_run is False
    
    def test_normalize_link(self, bot):
        """Проверка нормализации ссылок"""
        assert bot.normalize_link("https://t.me/testchannel") == "testchannel"
        assert bot.normalize_link("http://t.me/testchannel") == "testchannel"
        assert bot.normalize_link("t.me/testchannel") == "testchannel"
        assert bot.normalize_link("testchannel") == "testchannel"
        assert bot.normalize_link("  testchannel  ") == "testchannel"
        assert bot.normalize_link("t.me/+abc123") == "+abc123"
    
    def test_extract_invite_hash(self, bot):
        """Проверка извлечения хеша приглашения"""
        assert bot._extract_invite_hash("t.me/+abc123") == "abc123"
        assert bot._extract_invite_hash("https://t.me/joinchat/abc123") == "abc123"
        assert bot._extract_invite_hash("t.me/joinchat/abc123") == "abc123"
        assert bot._extract_invite_hash("testchannel") is None
    
    def test_pause_resume(self, bot):
        """Проверка функций паузы и резюме"""
        assert bot.pause_event.is_set() is True  # По умолчанию resumed
        
        bot.pause()
        assert bot.pause_event.is_set() is False
        
        bot.resume()
        assert bot.pause_event.is_set() is True
    
    def test_stop_control(self, bot):
        """Проверка управления остановкой"""
        assert bot.stop_event.is_set() is False
        assert bot.stop_requested is False
        
        bot.request_stop()
        assert bot.stop_event.is_set() is True
        assert bot.stop_requested is True
        
        bot.reset_stop()
        assert bot.stop_event.is_set() is False
        assert bot.stop_requested is False
    
    def test_dry_run_mode(self, bot):
        """Проверка режима dry-run"""
        assert bot.dry_run is False
        
        bot.set_dry_run(True)
        assert bot.dry_run is True
        
        bot.set_dry_run(False)
        assert bot.dry_run is False
    
    def test_mask_secrets_api_hash(self, bot):
        """Проверка маскирования api_hash"""
        bot.api_hash = "super_secret_hash"
        
        text = "Error: super_secret_hash not found"
        masked = bot._mask_secrets(text)
        
        assert "super_secret_hash" not in masked
        assert "***api_hash***" in masked
    
    def test_mask_secrets_phone(self, bot):
        """Проверка маскирования номера телефона"""
        bot.phone = "+71234567890"
        
        text = "Phone: +71234567890 is registered"
        masked = bot._mask_secrets(text)
        
        assert "+71234567890" not in masked
        assert "***phone***" in masked
    
    def test_mask_secrets_code(self, bot):
        """Проверка маскирования 6-значных кодов"""
        text = "Enter code 123456"
        masked = bot._mask_secrets(text)
        
        assert "123456" not in masked
        assert "***code***" in masked
    
    def test_mask_secrets_proxy_password(self, bot):
        """Проверка маскирования пароля прокси"""
        bot.proxy = {"password": "proxy_secret"}
        
        text = "Proxy error: proxy_secret"
        masked = bot._mask_secrets(text)
        
        assert "proxy_secret" not in masked
        assert "***proxy_pass***" in masked
    
    def test_stats_initialization(self, bot):
        """Проверка инициализации статистики"""
        stats = bot.get_stats()
        
        assert stats["processed"] == 0
        assert stats["sent"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
    
    def test_update_stats(self, bot):
        """Проверка обновления статистики"""
        bot.update_stats(processed=5, sent=3, skipped=2, errors=0)
        
        stats = bot.get_stats()
        assert stats["processed"] == 5
        assert stats["sent"] == 3
        assert stats["skipped"] == 2
        assert stats["errors"] == 0
        
        # Добавляем ещё
        bot.update_stats(processed=1, sent=1, skipped=0, errors=0)
        stats = bot.get_stats()
        assert stats["processed"] == 6
        assert stats["sent"] == 4
    
    def test_reset_stats(self, bot):
        """Проверка сброса статистики"""
        bot.update_stats(processed=10, sent=5)
        bot.reset_stats()
        
        stats = bot.get_stats()
        assert stats["processed"] == 0
        assert stats["sent"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
    
    def test_processed_posts_tracking(self, bot):
        """Проверка отслеживания обработанных постов"""
        bot.load_history()
        
        # Первый пост не обработан
        assert bot.is_post_processed("channel1", 123) is False
        
        # Отмечаем как обработанный
        bot.mark_post_processed("channel1", 123)
        
        # Теперь обработан
        assert bot.is_post_processed("channel1", 123) is True
        
        # Другой пост не обработан
        assert bot.is_post_processed("channel1", 456) is False


class TestBotSettings:
    """Тесты для BotSettings dataclass"""
    
    def test_settings_initialization(self):
        """Проверка инициализации настроек"""
        settings = BotSettings()
        
        assert settings.join_delay == 30
        assert settings.comment_delay_min == 15.0
        assert settings.comment_delay_max == 45.0
        assert settings.daily_limit == 40
        assert settings.sent_today == 0
        assert len(settings.comment_variants) == 5
    
    def test_settings_to_dict(self):
        """Проверка конвертации в dict"""
        settings = BotSettings(
            join_delay=20,
            comment_delay_min=10.0,
            daily_limit=50
        )
        
        data = settings.to_dict()
        assert data["join_delay"] == 20
        assert data["comment_delay_min"] == 10.0
        assert data["daily_limit"] == 50
    
    def test_settings_from_dict(self):
        """Проверка создания из dict"""
        data = {
            "join_delay": 25,
            "comment_delay_min": 12.0,
            "daily_limit": 60,
            "sent_today": 5,
            "last_reset_date": "2024-01-01"
        }
        
        settings = BotSettings.from_dict(data)
        assert settings.join_delay == 25
        assert settings.comment_delay_min == 12.0
        assert settings.daily_limit == 60
        assert settings.sent_today == 5


class TestSecureSecretsManager:
    """Тесты для управления секретами"""
    
    @pytest.fixture
    def secrets_mgr(self):
        return SecureSecretsManager()
    
    def test_secrets_manager_init(self, secrets_mgr):
        """Проверка инициализации менеджера секретов"""
        assert secrets_mgr.secrets_file is not None
        assert secrets_mgr._crypto is not None
    
    def test_set_get_secret(self, secrets_mgr):
        """Проверка сохранения и получения секрета"""
        secrets_mgr.set_secret("test_key", "test_value")
        value = secrets_mgr.get_secret("test_key")
        
        assert value == "test_value"
    
    def test_delete_secret(self, secrets_mgr):
        """Проверка удаления секрета"""
        secrets_mgr.set_secret("test_key", "test_value")
        assert secrets_mgr.get_secret("test_key") is not None
        
        secrets_mgr.delete_secret("test_key")
        assert secrets_mgr.get_secret("test_key") is None
    
    def test_auth_credentials(self, secrets_mgr):
        """Проверка сохранения/загрузки учётных данных"""
        secrets_mgr.save_auth_credentials("123", "hash_abc", "+71234567890")
        
        creds = secrets_mgr.load_auth_credentials()
        assert creds["api_id"] == "123"
        assert creds["api_hash"] == "hash_abc"
        assert creds["phone"] == "+71234567890"
    
    def test_proxy_settings(self, secrets_mgr):
        """Проверка сохранения/загрузки настроек прокси"""
        secrets_mgr.save_proxy_settings(
            "SOCKS5",
            "127.0.0.1",
            "1080",
            "user",
            "pass"
        )
        
        proxy = secrets_mgr.load_proxy_settings()
        assert proxy["proxy_type"] == "SOCKS5"
        assert proxy["proxy_ip"] == "127.0.0.1"
        assert proxy["proxy_port"] == "1080"
        assert proxy["proxy_user"] == "user"
        assert proxy["proxy_pass"] == "pass"


class TestAsyncSleep:
    """Тесты для async операций"""
    
    @pytest.mark.asyncio
    async def test_sleep_interruptible_completes(self):
        """Проверка что sleep завершается по истечении времени"""
        bot = TelegramBot(api_id=123, api_hash="test")
        
        import time
        start = time.time()
        await bot._sleep_interruptible(0.5)
        elapsed = time.time() - start
        
        # Должно быть примерно 0.5 сек (±0.2)
        assert 0.3 < elapsed < 0.8
    
    @pytest.mark.asyncio
    async def test_sleep_interruptible_stops_on_event(self):
        """Проверка что sleep прерывается по stop_event"""
        bot = TelegramBot(api_id=123, api_hash="test")
        
        async def request_stop():
            await asyncio.sleep(0.1)
            bot.request_stop()
        
        import time
        start = time.time()
        
        await asyncio.gather(
            bot._sleep_interruptible(10),  # Должна вернуться быстро
            request_stop()
        )
        
        elapsed = time.time() - start
        # Должно быть < 1 сек, а не 10!
        assert elapsed < 1
    
    @pytest.mark.asyncio
    async def test_sleep_interruptible_zero_delay(self):
        """Проверка что sleep с delay <= 0 возвращается сразу"""
        bot = TelegramBot(api_id=123, api_hash="test")
        
        import time
        start = time.time()
        await bot._sleep_interruptible(0)
        elapsed = time.time() - start
        
        # Должно быть почти мгновенно
        assert elapsed < 0.1


@pytest.mark.asyncio
async def test_settings_manager_async():
    """Тест async SettingsManager"""
    mgr = SettingsManager()
    await mgr.load()
    
    settings = await mgr.get_settings()
    assert settings.daily_limit == 40
    
    # Тест инкремента
    sent = await mgr.increment_sent_today()
    assert sent == 1
    
    sent = await mgr.increment_sent_today()
    assert sent == 2
    
    # Сброс
    await mgr.reset_daily_counter()
    sent = await mgr.get_sent_today()
    assert sent == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
