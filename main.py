import asyncio
import os
import platform
import signal
import sys
import traceback
from typing import Optional

import qasync
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

import config
from gui import MainWindow

APP_NAME = "TelegramAutoBot"


def resolve_application_font(fallback_family="SF Pro Display", fallback_size=11):
    try:
        font = QFont()
        if fallback_family:
            font.setFamily(fallback_family)
        font.setPointSize(fallback_size)
        if font.family():
            return font
    except Exception:
        pass
    return QFont()


def setup_macos():
    if platform.system() == 'Darwin':
        os.environ['QT_MAC_WANTS_LAYER'] = '1'
        os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
        os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
        os.environ['QT_QUICK_BACKEND'] = 'software'
        os.environ['PYTHONASYNCIODEBUG'] = '0'
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        print("✅ macOS оптимизации применены")


def get_app_dir():
    return config.get_app_dir()


def show_error(title, message):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.exec()


async def async_main():
    await asyncio.sleep(0.1)
    window = MainWindow()
    window.show()
    return window


def main():
    import utils
    logger = utils.setup_logger()
    
    try:
        os.chdir(get_app_dir())

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)

        setup_macos()

        font = resolve_application_font("SF Pro Display", 11)
        app.setFont(font)

        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        startup_task: Optional[asyncio.Task] = None
        window_holder = {}
        shutdown_event = asyncio.Event()

        def _shutdown_loop(reason: str = "Unknown"):
            """✅ ИСПРАВЛЕННАЯ версия: корректно закрывает loop"""
            nonlocal startup_task
            
            logger.info(f"🛑 Graceful shutdown инициирован ({reason})...")
            
            try:
                # 1. Отменяем startup task
                if startup_task and not startup_task.done():
                    startup_task.cancel()
                    try:
                        loop.run_until_complete(asyncio.sleep(0.1))
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отмены startup task: {e}")
            
            try:
                # 2. Отключаем бота если он подключён
                if window_holder.get("window") and window_holder["window"].bot:
                    try:
                        logger.info("ℹ️ Отключаю Telegram клиент...")
                        async def disconnect_bot():
                            try:
                                await window_holder["window"].bot.disconnect()
                            except Exception as e:
                                logger.warning(f"⚠️ Ошибка отключения бота: {e}")
                        
                        try:
                            loop.run_until_complete(asyncio.wait_for(disconnect_bot(), timeout=5))
                        except asyncio.TimeoutError:
                            logger.warning("⚠️ Timeout при отключении бота")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка в disconnect_bot: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отключения бота: {e}")
            
            try:
                # 3. Отменяем все остальные task'и
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    if task is not asyncio.current_task():
                        try:
                            task.cancel()
                        except Exception:
                            pass
                
                # Даём им время завершиться
                if pending:
                    try:
                        loop.run_until_complete(asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=2))
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ Timeout при отмене задач")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отмены задач: {e}")
            
            try:
                # 4. Закрываем loop
                if loop.is_running():
                    loop.stop()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка остановки loop: {e}")
            
            try:
                if not loop.is_closed():
                    loop.close()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка закрытия loop: {e}")
            
            logger.info("✅ Shutdown завершён")

        def _on_startup_done(task):
            nonlocal startup_task
            if task.cancelled():
                logger.info("ℹ️ Startup task был отменён")
                return
            
            exc = task.exception()
            if exc is not None:
                logger.error(f"❌ Ошибка запуска: {exc}")
                show_error(
                    "Ошибка запуска",
                    "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                )
                _shutdown_loop("startup error")
            else:
                window_holder["window"] = task.result()
                logger.info("✅ Окно приложения инициализировано")

        def _signal_handler(signum, frame):
            """✅ Обработчик SIGTERM/SIGINT для корректного завершения"""
            sig_name = signal.Signals(signum).name
            logger.warning(f"⚠️ Получен сигнал {sig_name}, выполняю shutdown...")
            _shutdown_loop(f"signal {sig_name}")
            QApplication.quit()

        # ✅ Регистрируем обработчики сигналов
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        
        # На macOS также обработаем SIGHUP
        if platform.system() == 'Darwin':
            signal.signal(signal.SIGHUP, _signal_handler)

        app.aboutToQuit.connect(lambda: _shutdown_loop("application quit"))

        with loop:
            startup_task = loop.create_task(async_main())
            startup_task.add_done_callback(_on_startup_done)
            
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                logger.info("⚠️ Получен KeyboardInterrupt")
                _shutdown_loop("keyboard interrupt")
            except Exception as e:
                logger.error(f"❌ Критическая ошибка в event loop: {e}")
                traceback.print_exc()
                _shutdown_loop("loop exception")
            finally:
                logger.info("ℹ️ Event loop завершён")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        traceback.print_exc()
        show_error("Критическая ошибка", traceback.format_exc())


if __name__ == "__main__":
    main()
