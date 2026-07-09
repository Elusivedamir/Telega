# 🔄 ГАЙД МИГРАЦИИ: Старая → Исправленная версия

## ⚠️ ВАЖНО: РЕЗЕРВНАЯ КОПИЯ

Перед миграцией создайте резервную копию:

```bash
# Резервная копия всей директории проекта
cp -r /path/to/TelegramAutoBot /path/to/TelegramAutoBot.backup

# Или только важные файлы
cp -r ~/Library/Application\ Support/TelegramAutoBot ~/TelegramAutoBot.backup
```

---

## 📋 ПОШАГОВАЯ МИГРАЦИЯ

### Этап 1: Обновление файлов

```bash
cd /path/to/TelegramAutoBot

# 1. Замените основные файлы
cp fixed_config.py config.py
cp fixed_telegram_bot.py telegram_bot.py
cp fixed_main.py main.py
cp fixed_build.spec build.spec
cp fixed_requirements.txt requirements.txt

# 2. Опционально: добавьте тесты
cp fixed_test_telegram_bot.py test_telegram_bot.py
```

### Этап 2: Обновление зависимостей

```bash
# Если используете venv
source venv/bin/activate

# Или создайте новый venv
python3 -m venv venv_new
source venv_new/bin/activate

# Установите зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Проверка конфликтов
pip check
```

### Этап 3: Миграция старых конфигов

#### 3.1 Миграция secrets (ОБЯЗАТЕЛЬНА)

```python
# migration_secrets.py
import sys
import os
from pathlib import Path

# Добавляем текущую директорию в path
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем менеджеры
import config  # Старый
from fixed_config import secrets_manager  # Новый

def migrate_secrets():
    """Миграция секретов из plain-text в зашифрованный формат"""
    
    print("🔄 Начинаю миграцию секретов...")
    
    try:
        # Загружаем старые credentials
        old_creds = config.load_auth_credentials()
        
        if old_creds.get("api_id"):
            print(f"  ✓ Загружена api_id")
            secrets_manager.set_secret("api_id", old_creds["api_id"])
        
        if old_creds.get("api_hash"):
            print(f"  ✓ Загружена api_hash")
            secrets_manager.set_secret("api_hash", old_creds["api_hash"])
        
        if old_creds.get("phone"):
            print(f"  ✓ Загружена phone")
            secrets_manager.set_secret("phone", old_creds["phone"])
        
        # Загружаем старые proxy settings
        old_proxy = config.load_proxy_settings()
        
        if old_proxy.get("proxy_ip"):
            print(f"  ✓ Загружены proxy settings")
            secrets_manager.save_proxy_settings(
                old_proxy.get("proxy_type", "SOCKS5"),
                old_proxy.get("proxy_ip", ""),
                old_proxy.get("proxy_port", ""),
                old_proxy.get("proxy_user", ""),
                old_proxy.get("proxy_pass", "")
            )
        
        print("✅ Миграция секретов завершена!")
        print("ℹ️  Старые secrets сохранены, новые зашифрованы")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_secrets()
    sys.exit(0 if success else 1)
```

**Запустите миграцию:**
```bash
python3 migration_secrets.py
# 🔄 Начинаю миграцию секретов...
#   ✓ Загружена api_id
#   ✓ Загружена api_hash
#   ✓ Загружена phone
#   ✓ Загружены proxy settings
# ✅ Миграция секретов завершена!
```

#### 3.2 Проверка миграции

```bash
# Проверяем что новые secrets зашифрованы
cat ~/Library/Application\ Support/TelegramAutoBot/secrets.json
# Должно быть:
# {
#     "_encrypted": "gAAAAABj8Kx1WN8K3XvQkZxD4f2G5h6i7j8k9l0m1n..."
# }
# НА, а не:
# {
#     "api_id": "12345",  <- ПЛОХО
#     "api_hash": "abc..."
# }
```

### Этап 4: Обновление конфигов

```bash
# Старые settings.json будут автоматически загружены
# Новый формат: использует BotSettings dataclass

# Для сброса всех настроек (опционально):
# rm ~/Library/Application\ Support/TelegramAutoBot/settings.json
```

### Этап 5: Проверка работы

```bash
# 1. Smoke-тесты
python3 test_smoke.py
# Expected: 6/6 tests passed ✅

# 2. Unit-тесты (если установлен pytest)
pip install pytest pytest-asyncio
pytest test_telegram_bot.py -v
# Expected: 30+ tests passed ✅

# 3. Запуск приложения
python3 main.py
# Expected: GUI откроется без ошибок ✅
```

### Этап 6: Тестирование авторизации

```
1. Запустите приложение
2. Перейдите на вкладку "Аккаунт"
3. Нажмите "Авторизоваться"
4. Введите 6-значный код из Telegram
5. Должно появиться сообщение "✅ Авторизован"
```

### Этап 7: Тестирование graceful shutdown

```bash
# Запустите приложение
python3 main.py

# В другом терминале пошлите сигнал:
kill -TERM <PID>

# Или просто закройте окно (⌘Q на macOS)
# Должно быть:
# 🛑 Graceful shutdown инициирован...
# ✅ Shutdown завершён
```

---

## 🔍 ДИАГНОСТИКА ПРОБЛЕМ

### Проблема 1: `ImportError: cannot import name 'HAS_CRYPTO'`

**Причина:** Старый импорт конфига
**Решение:**
```python
# В файлах где импортируется config, замените:
from config import ...
# На:
from fixed_config import ...

# Или создайте symlink:
ln -s fixed_config.py config.py
```

### Проблема 2: `RuntimeError: no running event loop`

**Причина:** Старый asyncio код
**Решение:** Используйте новый `fixed_telegram_bot.py`

### Проблема 3: `Secrets не загружаются`

**Причина:** Старые secrets в plain-text
**Решение:**
```bash
# Вручную запустите миграцию
python3 migration_secrets.py
```

### Проблема 4: `TypeError: settings is not a BotSettings instance`

**Причина:** Смешивание старого и нового кода
**Решение:**
```python
# Убедитесь что используется везде:
from fixed_config import settings_manager, BotSettings
# А не:
import config
```

---

## 📊 ПРОВЕРКА ПЕРЕД И ПОСЛЕ

### ДО МИГРАЦИИ

```bash
ls -la ~/Library/Application\ Support/TelegramAutoBot/
# -rw-r--r--  secrets.json         ← PLAIN TEXT (опасно!)
# -rw-r--r--  settings.json
# -rw-r--r--  session.session
# -rw-r--r--  processed_posts.json
# -rw-r--r--  bot.log
```

### ПОСЛЕ МИГРАЦИИ

```bash
ls -la ~/Library/Application\ Support/TelegramAutoBot/
# -rw-------  secrets.json         ← ЗАШИФРОВАН (безопасно!)
# -rw-r--r--  settings.json        ← Обновлён формат
# -rw-r--r--  session.session      ← Не изменился
# -rw-r--r--  processed_posts.json ← Не изменился
# -rw-r--r--  bot.log              ← Логирование улучшено
```

---

## ⚡ БЫСТРАЯ МИГРАЦИЯ (5 минут)

Если вам некогда:

```bash
# 1. Копируем исправленные файлы
for file in fixed_*.py; do
  cp "$file" "${file#fixed_}"
done

# 2. Обновляем зависимости
pip install -r requirements.txt

# 3. Запускаем миграцию
python3 migration_secrets.py

# 4. Проверяем
python3 test_smoke.py

# Готово! 🚀
```

---

## 🔄 ОТКАТ НА СТАРУЮ ВЕРСИЮ (если что-то сломалось)

```bash
# Восстанавливаем из резервной копии
cp -r ~/TelegramAutoBot.backup/* /path/to/TelegramAutoBot/

# Или откатываем файлы
git checkout HEAD~1 config.py telegram_bot.py main.py
```

---

## ✅ ЧЕКЛИСТ МИГРАЦИИ

- [ ] Создана резервная копия
- [ ] Заменены файлы (config, telegram_bot, main, build.spec, requirements.txt)
- [ ] Обновлены зависимости (`pip install -r requirements.txt`)
- [ ] Запущена миграция секретов (`python3 migration_secrets.py`)
- [ ] Проверены smoke-тесты (`python3 test_smoke.py`)
- [ ] Приложение запускается (`python3 main.py`)
- [ ] Авторизация работает
- [ ] Graceful shutdown работает
- [ ] Unit-тесты проходят (опционально)

---

## 🎓 ЧТО ИЗМЕНИЛОСЬ В API

### config.py

```python
# ❌ Старое
from config import SENT_TODAY, DAILY_LIMIT
SENT_TODAY += 1  # Не потокобезопасно!

# ✅ Новое
from fixed_config import settings_manager
sent_count = await settings_manager.increment_sent_today()  # Потокобезопасно!
```

### telegram_bot.py

```python
# ❌ Старое
await bot.run_commenting_with_ids(channels, pairs, text)

# ✅ Новое (на 90% совместимо, но с исправленной race condition)
await bot.run_commenting_with_ids(channels, pairs, text)
# Внутри используется SettingsManager для безопасности
```

### main.py

```python
# ❌ Старое
loop.run_forever()  # Может зависнуть

# ✅ Новое
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
loop.run_forever()  # Graceful shutdown работает
```

---

## 📞 ЕСЛИ ЧТО-ТО ПОШЛО НЕ ТАК

1. **Проверьте логи:**
```bash
tail -f ~/Library/Application\ Support/TelegramAutoBot/bot.log
```

2. **Запустите диагностику:**
```bash
python3 -c "from fixed_config import secrets_manager; print(secrets_manager.get_secret('api_id'))"
```

3. **Реsets secrets** (если совсем сломалось):
```bash
rm ~/Library/Application\ Support/TelegramAutoBot/secrets.json
python3 migration_secrets.py
```

---

**Миграция завершена! Теперь ваш проект безопаснее и надёжнее 🎉**
