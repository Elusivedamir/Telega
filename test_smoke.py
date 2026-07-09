"""
Smoke-тест для проверки базовой функциональности проекта
"""
import sys


def test_config_import():
    """Проверка импорта config.py"""
    try:
        import config
        print("[OK] config.py импортируется")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка импорта config.py: {e}")
        return False


def test_config_variables():
    """Проверка наличия необходимых переменных в config.py"""
    try:
        import config
        
        required_vars = [
            'JOIN_DELAY',
            'COMMENT_DELAY_MIN', 
            'COMMENT_DELAY_MAX',
            'DAILY_LIMIT',
            'SENT_TODAY',
            'LAST_RESET_DATE',
            'COMMENT_VARIANTS',
            'PROXY_TYPE',
            'PROXY_IP',
            'PROXY_PORT',
            'PROXY_USER',
            'PROXY_PASS'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not hasattr(config, var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"[FAIL] Отсутствуют переменные в config.py: {missing_vars}")
            return False
        
        print(f"[OK] Все {len(required_vars)} необходимых переменных есть в config.py")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка проверки переменных config.py: {e}")
        return False


def test_utils_import():
    """Проверка импорта utils.py"""
    try:
        import utils
        print("[OK] utils.py импортируется")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка импорта utils.py: {e}")
        return False


def test_telegram_bot_import():
    """Проверка импорта telegram_bot.py"""
    try:
        import telegram_bot
        print("[OK] telegram_bot.py импортируется")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка импорта telegram_bot.py: {e}")
        return False


def test_telegram_bot_creation():
    """Проверка создания объекта бота (без реального подключения)"""
    try:
        import telegram_bot
        
        # Создаём бота с тестовыми данными, без реального подключения
        bot = telegram_bot.TelegramBot(
            api_id=12345,
            api_hash="test_hash",
            session_name="test_session",
            proxy=None,
            code_callback=None
        )
        
        print("[OK] Объект TelegramBot создаётся корректно")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка создания объекта TelegramBot: {e}")
        return False


def test_gui_modules_import():
    """Проверка импорта GUI модулей"""
    try:
        import gui_styles
        import gui_channels
        import gui_pairs
        import gui_commenting
        print("[OK] GUI модули импортируются")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка импорта GUI модулей: {e}")
        return False


def test_bot_stop_control():
    """Проверка механизма остановки задачи через event"""
    try:
        import telegram_bot

        bot = telegram_bot.TelegramBot(
            api_id=12345,
            api_hash="test_hash",
            session_name="test_session",
            proxy=None,
            code_callback=None
        )

        if bot.stop_event.is_set():
            raise AssertionError("Событие остановки должно быть сброшено по умолчанию")

        bot.request_stop()
        if not bot.stop_event.is_set():
            raise AssertionError("request_stop() не выставил событие")

        bot.reset_stop()
        if bot.stop_event.is_set():
            raise AssertionError("reset_stop() не сбросил событие")

        print("[OK] Механизм остановки TelegramBot работает")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка проверки механизма остановки: {e}")
        return False


def test_font_resolution_helper():
    """Проверка, что функция выбора шрифта возвращает рабочий объект"""
    try:
        import main

        font = main.resolve_application_font("SF Pro Display", 11)
        if not font.family():
            raise AssertionError("Функция выбора шрифта не вернула семейство")

        print("[OK] Функция выбора шрифта корректно возвращает шрифт")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка проверки выбора шрифта: {e}")
        return False


def test_pair_csv_template_parsing():
    """Проверка чтения шаблона связок с комментариями и понятными колонками"""
    try:
        from gui_pairs import PairsMixin

        rows = [
            ["# Шаблон для связок"],
            ["# Колонка 1 = ID канала"],
            ["№", "ID КАНАЛА", "ID ЧАТА/ОБСУЖДЕНИЯ/ГРУППЫ", "USERNAME", "НАЗВАНИЕ"],
            ["1", "-1001111111111", "-1002222222222", "", "Example"],
            ["2", "-1003333333333", "", "", "Example 2"],
        ]

        pairs = PairsMixin.parse_pairs_rows(rows)

        if len(pairs) != 2:
            raise AssertionError(f"Ожидалось 2 связки, получено {len(pairs)}")

        if pairs[0] != ("-1001111111111", "-1002222222222"):
            raise AssertionError(f"Первая связка распарсилась неверно: {pairs[0]}")

        if pairs[1] != ("-1003333333333", ""):
            raise AssertionError(f"Вторая связка распарсилась неверно: {pairs[1]}")

        print("[OK] Шаблон связок с комментариями читается корректно")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка разбора шаблона связок: {e}")
        return False


def test_dry_run_and_stats_support():
    """Проверка наличия режима dry-run и счётчика статистики у TelegramBot"""
    try:
        import telegram_bot

        bot = telegram_bot.TelegramBot(
            api_id=12345,
            api_hash="test_hash",
            session_name="test_session",
            proxy=None,
            code_callback=None
        )

        bot.set_dry_run(True)
        if not bot.dry_run:
            raise AssertionError("Режим dry-run не был включён")

        bot.update_stats(processed=1, sent=0, skipped=1, errors=0)
        stats = bot.get_stats()
        if stats["processed"] != 1 or stats["skipped"] != 1:
            raise AssertionError(f"Статистика обновилась неверно: {stats}")

        print("[OK] Режим dry-run и статистика поддерживаются")
        return True
    except Exception as e:
        print(f"[FAIL] Ошибка проверки dry-run и статистики: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("=" * 50)
    print("SMOKE-ТЕСТЫ ДЛЯ TELEGRAM AUTOBOT")
    print("=" * 50)
    print()
    
    tests = [
        ("Импорт config.py", test_config_import),
        ("Переменные config.py", test_config_variables),
        ("Импорт utils.py", test_utils_import),
        ("Импорт telegram_bot.py", test_telegram_bot_import),
        ("Создание объекта бота", test_telegram_bot_creation),
        ("Импорт GUI модулей", test_gui_modules_import),
        ("Механизм остановки бота", test_bot_stop_control),
        ("Выбор шрифта", test_font_resolution_helper),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[TEST] {test_name}:")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("ИТОГИ:")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nВсего: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} тест(ов) не пройдено")
        return 1


if __name__ == "__main__":
    sys.exit(main())
