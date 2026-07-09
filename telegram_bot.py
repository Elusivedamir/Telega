import asyncio
import json
import os
import random
import re
import traceback
from datetime import datetime, time
from typing import Optional, Callable, List, Tuple

from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

import utils
from fixed_config import settings_manager, secrets_manager, BotSettings

logger = utils.setup_logger()
APP_NAME = "TelegramAutoBot"


def app_dir():
    from fixed_config import get_app_dir
    return get_app_dir()


def history_file():
    from fixed_config import get_history_file
    return get_history_file()


class TelegramBot:
    def __init__(self, api_id, api_hash, session_name="session", proxy=None, code_callback=None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.proxy = proxy
        self.code_callback = code_callback
        self.client = None
        self.is_connected = False
        self.phone = None
        self.stop_requested = False
        self.stop_event = asyncio.Event()
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.processed_posts = set()
        self.dry_run = False
        self._state_lock = asyncio.Lock()  # ✅ Создаём сразу, не лениво!
        self.stats = {
            "processed": 0,
            "sent": 0,
            "skipped": 0,
            "errors": 0,
        }

    def request_stop(self):
        self.stop_requested = True
        self.stop_event.set()

    def reset_stop(self):
        self.stop_requested = False
        self.stop_event.clear()

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def set_dry_run(self, enabled: bool):
        self.dry_run = bool(enabled)

    def update_stats(self, processed=0, sent=0, skipped=0, errors=0):
        self.stats["processed"] += processed
        self.stats["sent"] += sent
        self.stats["skipped"] += skipped
        self.stats["errors"] += errors
        self._save_stats_to_file()

    def get_stats(self):
        return dict(self.stats)

    def reset_stats(self):
        self.stats = {"processed": 0, "sent": 0, "skipped": 0, "errors": 0}
        self._save_stats_to_file()

    def _save_stats_to_file(self):
        try:
            from fixed_config import get_stats_file
            payload = {
                "timestamp": datetime.now().isoformat(),
                **self.stats,
            }
            with open(get_stats_file(), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения статистики: {e}")

    def load_stats_from_file(self):
        try:
            from fixed_config import get_stats_file
            stats_file = get_stats_file()
            if not os.path.exists(stats_file):
                return self.stats
            with open(stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key in self.stats:
                    if key in data:
                        self.stats[key] = int(data[key])
            return self.stats
        except Exception as e:
            logger.error(f"❌ Ошибка чтения статистики: {e}")
            return self.stats

    async def _sleep_interruptible(self, delay, status_cb=None, message=None):
        """✅ ИСПРАВЛЕННАЯ версия: правильно управляет pending задачами"""
        if delay <= 0:
            return
        try:
            end_time = asyncio.get_running_loop().time() + delay
            
            while True:
                remaining = end_time - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                
                if self.stop_event.is_set():
                    if status_cb:
                        status_cb(message or "🛑 Остановка...")
                    return
                
                # Если пауза активна, просто спим
                if self.pause_event.is_set():
                    try:
                        await asyncio.sleep(min(0.1, remaining))
                    except asyncio.CancelledError:
                        logger.debug("Sleep прерван CancelledError")
                        return
                    continue
                
                # Ждём изменения pause_event или stop_event
                try:
                    pause_task = asyncio.create_task(self.pause_event.wait())
                    stop_task = asyncio.create_task(self.stop_event.wait())
                    
                    done, pending = await asyncio.wait(
                        [pause_task, stop_task],
                        timeout=min(0.2, remaining),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    
                    # ✅ Очищаем pending задачи
                    for task in pending:
                        try:
                            task.cancel()
                        except Exception:
                            pass
                    
                    if self.stop_event.is_set():
                        if status_cb:
                            status_cb(message or "🛑 Остановка...")
                        return
                        
                except asyncio.CancelledError:
                    logger.debug("_sleep_interruptible прервана CancelledError")
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка в _sleep_interruptible: {e}")
                    try:
                        await asyncio.sleep(0.1)
                    except asyncio.CancelledError:
                        return
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в _sleep_interruptible: {e}")

    async def _handle_retry(self, exc, attempt, status_cb=None, default_delay=10):
        if isinstance(exc, errors.FloodWaitError):
            delay = max(exc.seconds + 2, default_delay)
            if status_cb:
                status_cb(f"⏳ FloodWait: ожидание {delay} сек.")
            await self._sleep_interruptible(delay, status_cb, "🛑 Остановка после FloodWait")
            return delay

        if isinstance(exc, errors.TooManyRequestsError):
            delay = min(60, default_delay * (2 ** attempt))
            if status_cb:
                status_cb(f"⏳ TooManyRequests: ожидание {delay} сек.")
            await self._sleep_interruptible(delay, status_cb, "🛑 Остановка после TooManyRequests")
            return delay

        if isinstance(exc, errors.SlowModeWaitError):
            delay = max(exc.seconds, default_delay)
            if status_cb:
                status_cb(f"⏳ SlowModeWait: ожидание {delay} сек.")
            await self._sleep_interruptible(delay, status_cb, "🛑 Остановка после SlowModeWait")
            return delay

        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
            delay = min(30, default_delay * (2 ** attempt))
            if status_cb:
                status_cb(f"⏳ Сетевой таймаут/обрыв: повтор через {delay} сек.")
            await self._sleep_interruptible(delay, status_cb, "🛑 Остановка после сетевой ошибки")
            return delay

        delay = min(30, default_delay * (2 ** attempt))
        if status_cb:
            status_cb(f"⏳ Временная ошибка: повтор через {delay} сек.")
        await self._sleep_interruptible(delay, status_cb, "🛑 Остановка после временной ошибки")
        return delay
    
    def load_history(self):
        try:
            with open(history_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
                self.processed_posts = set(data.keys()) if isinstance(data, dict) else set()
                return data
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.error(f"❌ Ошибка чтения истории обработанных постов: {e}")
            return {}
    
    def save_history(self, data):
        try:
            with open(history_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения истории: {e}")
    
    def is_post_processed(self, channel_id, post_id):
        key = f"{channel_id}_{post_id}"
        return key in self.processed_posts
    
    def mark_post_processed(self, channel_id, post_id):
        key = f"{channel_id}_{post_id}"
        self.processed_posts.add(key)
        history = self.load_history()
        history[key] = True
        self.save_history(history)
    
    async def connect(self):
        """✅ ИСПРАВЛЕННАЯ авторизация с лучшей обработкой ошибок"""
        credentials = secrets_manager.load_auth_credentials()
        if self.api_id is None or self.api_id == "":
            self.api_id = int(credentials.get("api_id", "0") or 0)
        if not self.api_hash:
            self.api_hash = credentials.get("api_hash", "") or ""
        if not self.phone:
            self.phone = credentials.get("phone", "") or ""

        try:
            proxy = None
            if self.proxy:
                from socks import PROXY_TYPE_SOCKS5, PROXY_TYPE_SOCKS4
                proxy_type = (
                    PROXY_TYPE_SOCKS5
                    if self.proxy.get("proxy_type", "socks5").lower() == "socks5"
                    else PROXY_TYPE_SOCKS4
                )
                proxy = (
                    proxy_type,
                    self.proxy["addr"],
                    int(self.proxy["port"]),
                    True,
                    self.proxy.get("username", ""),
                    self.proxy.get("password", "")
                )

            from fixed_config import get_session_path
            session_path = get_session_path(self.session_name)

            self.client = TelegramClient(
                session_path,
                self.api_id,
                self.api_hash,
                proxy=proxy
            )

            await self.client.connect()

            if not await self.client.is_user_authorized():
                await self.client.send_code_request(self.phone)

                # ✅ Улучшенная логика: повторяем запрос кода каждые 2 попытки
                for attempt in range(6):
                    code = await self._ask(self.code_callback, "Введите код из Telegram:")
                    if not code:
                        logger.error("❌ Код авторизации не был введен")
                        return False
                    
                    # Если прошло много попыток — запросим новый код
                    if attempt > 0 and attempt % 2 == 0:
                        logger.info(f"ℹ️ Запрашиваю новый код (попытка {attempt + 1}/6)...")
                        await self.client.send_code_request(self.phone)
                        await self._sleep_interruptible(2)
                    
                    try:
                        await self.client.sign_in(self.phone, code)
                        logger.info("✅ Успешная авторизация по коду")
                        break
                    except errors.PhoneCodeInvalidError:
                        logger.warning(f"⚠️ Неверный код (попытка {attempt + 1}/6)")
                        if attempt == 5:
                            logger.error("❌ Исчерпаны все попытки ввода кода")
                            return False
                    except errors.PhoneCodeExpiredError:
                        logger.warning("⚠️ Код истёк, запрашиваю новый")
                        await self.client.send_code_request(self.phone)
                        await self._sleep_interruptible(1)

            self.is_connected = True
            logger.info("✅ Telegram подключен")
            return True

        except errors.SessionPasswordNeededError:
            logger.info("ℹ️ Требуется 2FA пароль")
            for attempt in range(3):
                password = await self._ask(self.code_callback, "Введите пароль 2FA:")
                if not password:
                    logger.error("❌ Пароль 2FA не был введен")
                    return False
                try:
                    await self.client.sign_in(password=password)
                    self.is_connected = True
                    logger.info("✅ Успешная авторизация с 2FA")
                    return True
                except errors.PasswordHashInvalidError:
                    logger.warning(f"⚠️ Неверный пароль 2FA (попытка {attempt + 1}/3)")
                    if attempt == 2:
                        logger.error("❌ Исчерпаны попытки ввода 2FA пароля")
                        return False
            return False

        except Exception as e:
            logger.error(f"❌ Ошибка при подключении клиента: {self._mask_secrets(str(e))}")
            logger.debug(self._mask_secrets(traceback.format_exc()))
            return False

    def _mask_secrets(self, text: str) -> str:
        """✅ ИСПРАВЛЕННАЯ маскировка: маскируем ВСЕ секреты"""
        if not text:
            return text
        
        text = str(text)
        
        # Словарь секретов для маскирования
        secrets_to_mask = {}
        
        if self.api_hash and self.api_hash.strip():
            secrets_to_mask[self.api_hash] = "***api_hash***"
        
        if self.api_id:
            secrets_to_mask[str(self.api_id)] = "***api_id***"
        
        if self.phone and self.phone.strip():
            secrets_to_mask[self.phone] = "***phone***"
        
        if self.proxy:
            proxy_pass = self.proxy.get("password", "")
            if proxy_pass and proxy_pass.strip():
                secrets_to_mask[proxy_pass] = "***proxy_pass***"
        
        # Применяем маскирование
        for secret, mask in secrets_to_mask.items():
            if secret and str(secret).strip():
                text = text.replace(str(secret), mask)
        
        # Маскируем коды валидации (6 цифр подряд)
        text = re.sub(r'\b\d{6}\b', '***code***', text)
        
        return text
    
    @staticmethod
    async def _ask(callback, prompt):
        if asyncio.iscoroutinefunction(callback):
            return await callback(prompt)
        return callback(prompt)
    
    async def disconnect(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отключения клиента: {e}")
            self.is_connected = False
    
    @staticmethod
    def normalize_link(value: str) -> str:
        value = str(value).strip()
        for prefix in ("https://", "http://"):
            if value.startswith(prefix):
                value = value[len(prefix):]
        if value.startswith("t.me/"):
            value = value[len("t.me/"):]
        return value

    async def get_entity(self, value):
        return await self.client.get_entity(self.normalize_link(value))

    @staticmethod
    def _extract_invite_hash(value):
        value = TelegramBot.normalize_link(value)
        if value.startswith("+"):
            return value[1:]
        if value.startswith("joinchat/"):
            return value[len("joinchat/"):]
        return None
    
    async def join_channels(self, channels, progress_cb=None, status_cb=None, time_cb=None, stats_cb=None):
        total = len(channels)
        self.reset_stop()
        for i, ch in enumerate(channels, 1):
            if self.stop_requested or self.stop_event.is_set():
                return False

            await self.pause_event.wait()
            if self.stop_requested or self.stop_event.is_set():
                return False

            try:
                invite_hash = self._extract_invite_hash(ch)
                if self.dry_run:
                    if status_cb:
                        status_cb(f"🧪 DRY RUN: вступление в {ch} пропущено")
                    self.update_stats(processed=1, sent=0, skipped=1, errors=0)
                    if stats_cb:
                        stats_cb(self.get_stats())
                    if progress_cb:
                        progress_cb(i, total)
                    continue
                if invite_hash:
                    await self.client(ImportChatInviteRequest(invite_hash))
                else:
                    entity = await self.get_entity(ch)
                    await self.client(JoinChannelRequest(entity))

                self.update_stats(processed=1, sent=1, skipped=0, errors=0)
                if stats_cb:
                    stats_cb(self.get_stats())
                if status_cb:
                    status_cb(f"✅ Вступил в {ch}")

            except errors.PeerFloodError:
                self.update_stats(processed=1, sent=0, skipped=0, errors=1)
                if stats_cb:
                    stats_cb(self.get_stats())
                if status_cb:
                    status_cb("🚫 PeerFlood: Telegram временно ограничил аккаунт.")
                logger.error("🚫 PeerFloodError в join_channels — прекращаю выполнение")
                return False

            except Exception as e:
                if self.stop_requested or self.stop_event.is_set():
                    return False
                self.update_stats(processed=1, sent=0, skipped=0, errors=1)
                if stats_cb:
                    stats_cb(self.get_stats())
                if status_cb:
                    status_cb(f"❌ {ch}: {self._mask_secrets(str(e))}")
                logger.error(f"❌ Ошибка вступления в {ch}: {self._mask_secrets(str(e))}")
                await self._handle_retry(e, attempt=0, status_cb=status_cb, default_delay=5)

            if progress_cb:
                progress_cb(i, total)

            if self.stop_requested or self.stop_event.is_set():
                return False
            await self._sleep_interruptible(utils.random_delay(30), status_cb=status_cb, message="🛑 Остановка после паузы")

        return True
    
    async def run_commenting_with_ids(self, channels, pairs, text, progress_cb=None, status_cb=None, time_cb=None, stats_cb=None):
        """✅ ИСПРАВЛЕННАЯ версия: атомарные операции с SENT_TODAY"""
        self.load_history()
        self.reset_stop()

        # ✅ Используем SettingsManager для атомарности
        await settings_manager.load()

        if not pairs:
            if status_cb:
                status_cb("⚠️ Список связок пуст!")
            return False

        total = len(pairs)
        current = 0

        while True:
            # ✅ АТОМАРНАЯ операция: проверяем лимит ВНУТРИ лока
            async with self._state_lock:
                settings = await settings_manager.get_settings()
                today = datetime.now().strftime("%Y-%m-%d")
                
                if settings.last_reset_date != today:
                    await settings_manager.reset_daily_counter()
                    settings = await settings_manager.get_settings()
                
                if settings.sent_today >= settings.daily_limit:
                    if status_cb:
                        status_cb(f"✅ Дневной лимит ({settings.daily_limit}) достигнут.")
                    return True

            if self.stop_requested or self.stop_event.is_set():
                if status_cb:
                    status_cb("🛑 Процесс комментирования остановлен")
                return False

            pair = pairs[current % total]
            source, destination = pair

            try:
                channel = await self.get_entity(source)
                messages = await self.client.get_messages(channel, limit=1)

                if not messages:
                    if status_cb:
                        status_cb(f"⚠️ В канале {source} нет постов")
                    current += 1
                    continue

                post = messages[0]

                if self.is_post_processed(source, post.id):
                    self.update_stats(processed=1, sent=0, skipped=1, errors=0)
                    if stats_cb:
                        stats_cb(self.get_stats())
                    if status_cb:
                        status_cb(f"⏭ Пост в {source} уже прокомментирован")
                    current += 1
                    continue

                if self.dry_run:
                    if status_cb:
                        status_cb(f"🧪 DRY RUN: комментарий для {source} не отправлен")
                    self.update_stats(processed=1, sent=0, skipped=1, errors=0)
                    if stats_cb:
                        stats_cb(self.get_stats())
                    current += 1
                    continue

                # Выбираем случайный комментарий перед КАЖДОЙ отправкой
                settings = await settings_manager.get_settings()
                valid_texts = [c for c in settings.comment_variants if c.strip()]
                current_text = random.choice(valid_texts) if valid_texts else text

                try:
                    if destination and destination.strip():
                        await self.client.send_message(channel, current_text, comment_to=post.id)
                    else:
                        await self.client.send_message(channel, current_text)
                    
                    # ✅ АТОМАРНОЕ увеличение после успеха
                    sent_count = await settings_manager.increment_sent_today()
                    
                    if status_cb:
                        settings = await settings_manager.get_settings()
                        status_cb(f"💬 [{sent_count}/{settings.daily_limit}] Комментарий отправлен в {source}")
                        
                except errors.MsgIdInvalidError:
                    if status_cb:
                        status_cb(f"⚠️ Пост {post.id} в {source} больше недоступен для комментария")
                    logger.warning(f"⚠️ MsgIdInvalidError для поста {post.id} в {source}")
                    self.update_stats(processed=1, sent=0, skipped=1, errors=0)
                    if stats_cb:
                        stats_cb(self.get_stats())
                    current += 1
                    continue

                self.mark_post_processed(source, post.id)
                self.update_stats(processed=1, sent=1, skipped=0, errors=0)
                if stats_cb:
                    stats_cb(self.get_stats())

                current += 1
                if progress_cb:
                    progress_cb(current, total)

                # Расчёт delay'а
                now = datetime.now()
                end_of_day = datetime.combine(now.date(), time(23, 59, 59))
                seconds_left_today = max(0, (end_of_day - now).total_seconds())
                
                settings = await settings_manager.get_settings()
                sent = await settings_manager.get_sent_today()
                remaining_comments = max(0, settings.daily_limit - sent)

                if remaining_comments > 0 and seconds_left_today > 0:
                    base_delay = seconds_left_today / remaining_comments
                    final_delay = base_delay * random.uniform(0.75, 1.25)
                    final_delay = max(
                        settings.comment_delay_min,
                        min(settings.comment_delay_max, final_delay)
                    )
                else:
                    final_delay = random.uniform(
                        settings.comment_delay_min,
                        settings.comment_delay_max
                    )

                if status_cb and time_cb:
                    minutes = int(final_delay // 60)
                    seconds = int(final_delay % 60)
                    time_cb(f"⏳ Следующий комментарий через {minutes} мин {seconds} сек")

                await self._sleep_interruptible(final_delay, status_cb=status_cb, message="🛑 Остановка после паузы")

            except errors.PeerFloodError:
                self.update_stats(processed=1, sent=0, skipped=0, errors=1)
                if stats_cb:
                    stats_cb(self.get_stats())
                if status_cb:
                    status_cb("🚫 PeerFlood: Telegram временно ограничил аккаунт.")
                logger.error("🚫 PeerFloodError в run_commenting_with_ids — прекращаю выполнение")
                return False

            except Exception as e:
                if self.stop_requested or self.stop_event.is_set():
                    if status_cb:
                        status_cb("🛑 Процесс комментирования остановлен")
                    return False

                self.update_stats(processed=1, sent=0, skipped=0, errors=1)
                if stats_cb:
                    stats_cb(self.get_stats())
                if status_cb:
                    status_cb(f"❌ Ошибка для {source}: {self._mask_secrets(str(e))}")
                logger.error(f"❌ Ошибка отправки комментария для {source}: {self._mask_secrets(str(e))}")

                current += 1
                delay = await self._handle_retry(e, attempt=0, status_cb=status_cb, default_delay=5)
                if self.stop_requested or self.stop_event.is_set():
                    return False
                if delay <= 0:
                    settings = await settings_manager.get_settings()
                    await self._sleep_interruptible(
                        random.uniform(settings.comment_delay_min, settings.comment_delay_max),
                        status_cb=status_cb,
                        message="🛑 Остановка после паузы"
                    )
                continue

        return True
