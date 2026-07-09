import asyncio
import csv
import os
import traceback
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

try:
    from qasync import asyncSlot
except Exception:  # pragma: no cover - fallback
    def asyncSlot(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from gui_styles import app_file
from utils import setup_logger

logger = setup_logger()


class PairsMixin:
    """Миксин для работы со связками и CSV"""

    def init_pairs_ui(self, layout):
        """Инициализация UI для вкладки связок"""
        # Кнопки управления
        controls_layout = QHBoxLayout()

        self.parse_btn = QPushButton("🔍 Парсинг каналов → CSV")
        self.parse_btn.clicked.connect(self.parse_channels_to_csv)
        controls_layout.addWidget(self.parse_btn)

        self.load_csv_btn = QPushButton("📂 Загрузить CSV")
        self.load_csv_btn.clicked.connect(self.load_pairs_from_csv)
        controls_layout.addWidget(self.load_csv_btn)

        self.template_btn = QPushButton("📄 Скачать шаблон связок")
        self.template_btn.clicked.connect(self.download_pairs_template)
        controls_layout.addWidget(self.template_btn)

        layout.addLayout(controls_layout)

        # Понятные подсказки для новичка
        info_text = (
            "<b>Как заполнять связки:</b><br>"
            "• <b>Колонка 1</b> — ID канала, откуда брать публикации<br>"
            "• <b>Колонка 2</b> — ID чата/обсуждения/группы, куда отправлять комментарий<br>"
            "• Если у вас просто обычный чат, оставьте вторую колонку пустой<br>"
            "• Для обсуждения или группы чаще всего нужен отрицательный ID вида -1001234567890"
        )
        layout.addWidget(QLabel(info_text))

        # Таблица связок (только просмотр)
        layout.addWidget(QLabel("📋 Связки (только просмотр):"))

        self.pairs_table = QTableWidget()
        self.pairs_table.setColumnCount(2)
        self.pairs_table.setHorizontalHeaderLabels(["Канал (Source)", "Чат (Destination)"])
        self.pairs_table.horizontalHeader().setStretchLastSection(True)
        self.pairs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pairs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Оптимизация таблицы
        self.pairs_table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.pairs_table.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.pairs_table.setAlternatingRowColors(False)
        self.pairs_table.setSortingEnabled(False)
        self.pairs_table.verticalHeader().setVisible(False)
        self.pairs_table.setShowGrid(False)

        layout.addWidget(self.pairs_table)

        # Удаление связки
        self.del_pair_btn = QPushButton("Удалить выбранную связку")
        self.del_pair_btn.clicked.connect(self.delete_pair)
        layout.addWidget(self.del_pair_btn)

    @staticmethod
    def parse_pairs_rows(rows):
        """Разбирает CSV/TSV/rows и возвращает список (source, destination)."""
        pairs = []
        for row in rows:
            if not row:
                continue

            cells = [str(cell).strip() for cell in row]
            if not cells or not any(cells):
                continue

            if cells[0].startswith("#"):
                continue

            if len(cells) >= 2 and cells[0].lower() in {"№", "no", "number", "n"}:
                continue

            if len(cells) >= 2:
                source = cells[1].strip() if len(cells) > 1 else ""
                destination = cells[2].strip() if len(cells) > 2 else ""
                if source and source != "ОШИБКА" and source != "ID КАНАЛА":
                    pairs.append((source, destination))

        return pairs

    def download_pairs_template(self):
        desktop = Path.home() / "Desktop"
        filename = "pairs_template.csv"
        filepath = str(desktop / filename)
        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["# Шаблон для связок TelegramAutoBot"])
                writer.writerow(["# Колонка 1 = ID канала (источник)"])
                writer.writerow(["# Колонка 2 = ID чата/обсуждения/группы (назначение)"])
                writer.writerow(["# Оставьте вторую колонку пустой, если нужен обычный чат"])
                writer.writerow(["# Пример: -1001111111111; -1002222222222"])
                writer.writerow(["№", "ID КАНАЛА", "ID ЧАТА/ОБСУЖДЕНИЯ/ГРУППЫ", "USERNAME", "НАЗВАНИЕ"])
                writer.writerow(["1", "-1001111111111", "-1002222222222", "", "Канал 1"])
                writer.writerow(["2", "-1003333333333", "", "", "Канал 2"])
            self.log(f"✅ Шаблон сохранён: {filepath}")
            QMessageBox.information(self, "Шаблон готов", f"Файл сохранён:\n{filepath}")
        except Exception as e:
            self.log(f"❌ Ошибка создания шаблона: {e}")

    def load_pairs_from_file(self):
        path = app_file("pairs.txt")
        if not os.path.exists(path):
            return
        try:
            self.pairs = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 1:
                        source = parts[0].strip()
                        destination = parts[1].strip() if len(parts) > 1 else ""
                        self.pairs.append((source, destination))
            self.refresh_pairs()
        except Exception as e:
            self.log(f"Ошибка загрузки связок: {e}")

    def save_pairs(self):
        try:
            with open(app_file("pairs.txt"), "w", encoding="utf-8") as f:
                for source, destination in self.pairs:
                    if destination:
                        f.write(f"{source}|{destination}\n")
                    else:
                        f.write(f"{source}\n")
        except Exception as e:
            self.log(f"Ошибка сохранения связок: {e}")

    def refresh_pairs(self):
        self.pairs_table.setUpdatesEnabled(False)
        try:
            self.pairs_table.setRowCount(len(self.pairs))
            for i, (source, destination) in enumerate(self.pairs):
                self.pairs_table.setItem(i, 0, QTableWidgetItem(source))
                dest_text = destination or "❌ ПУСТО (обычный чат)"
                item = QTableWidgetItem(dest_text)
                if not destination:
                    item.setForeground(QColor("#ffa500"))
                self.pairs_table.setItem(i, 1, item)
        finally:
            self.pairs_table.setUpdatesEnabled(True)

    def delete_pair(self):
        current_row = self.pairs_table.currentRow()
        if current_row >= 0:
            self.pairs.pop(current_row)
            self.save_pairs()
            self.refresh_pairs()

    def parse_channels_to_csv(self):
        if not self.bot or not self.bot.is_connected:
            self.log("❌ Сначала пройдите авторизацию")
            return

        if not self.channels:
            self.log("❌ Список каналов пуст")
            return

        self.log("🔍 Начинаю парсинг каналов...")
        self.parse_btn.setEnabled(False)
        self.run_async_safe(self._parse_channels_task())

    async def _parse_channels_task(self):
        try:
            results = []
            total = len(self.channels)

            for i, channel in enumerate(self.channels, 1):
                self.log(f"📡 Обработка {i}/{total}: {channel}")

                try:
                    entity = await self.bot.get_entity(channel)

                    channel_id = str(entity.id)
                    if hasattr(entity, 'megagroup') and entity.megagroup:
                        channel_id = f"-100{abs(entity.id)}"
                    elif hasattr(entity, 'broadcast') and entity.broadcast:
                        channel_id = f"-100{abs(entity.id)}"
                    else:
                        channel_id = str(entity.id)

                    username = entity.username if hasattr(entity, 'username') and entity.username else ""
                    title = entity.title if hasattr(entity, 'title') else ""

                    results.append({
                        'number': i,
                        'channel_id': channel_id,
                        'destination': '',
                        'username': username,
                        'title': title
                    })

                    self.log(f"✅ {title} (ID: {channel_id})")

                except Exception as e:
                    self.log(f"❌ Ошибка: {e}")
                    results.append({
                        'number': i,
                        'channel_id': 'ОШИБКА',
                        'destination': '',
                        'username': '',
                        'title': f'ОШИБКА: {channel}'
                    })

                await asyncio.sleep(1)

            # Сохраняем на рабочий стол через диалог (обход песочницы macOS)
            desktop = Path.home() / "Desktop"
            filename = f"channels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath, _ = QFileDialog.getSaveFileName(
                self, "Сохранить список каналов", str(desktop / filename), "CSV files (*.csv)"
            )
            
            if not filepath:
                self.log("⚠️ Сохранение отменено")
                return

            with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['# Шаблон для связок TelegramAutoBot'])
                writer.writerow(['# Колонка 1 = ID канала (источник)'])
                writer.writerow(['# Колонка 2 = ID чата/обсуждения/группы (назначение)'])
                writer.writerow(['# Оставьте вторую колонку пустой, если нужен обычный чат'])
                writer.writerow(['№', 'ID КАНАЛА', 'ID ЧАТА/ОБСУЖДЕНИЯ/ГРУППЫ', 'USERNAME', 'НАЗВАНИЕ'])
                writer.writerow(['', '← ID канала', '← ВСТАВЬТЕ ID ЧАТА ИЛИ ОБСУЖДЕНИЯ', '', ''])

                for r in results:
                    writer.writerow([r['number'], r['channel_id'], r['destination'], r['username'], r['title']])

                writer.writerow([])
                writer.writerow(['⚠️ ИНСТРУКЦИЯ:', 'Заполните вторую колонку, затем загрузите CSV в программу'])

            self.log(f"✅ Файл сохранён: {filepath}")
            QMessageBox.information(self, "Готово", f"✅ Файл сохранён:\n{filepath}")

        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.parse_btn.setEnabled(True)

    def load_pairs_from_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите CSV файл",
            str(Path.home() / "Desktop"),
            "CSV files (*.csv);;All files (*.*)"
        )

        if not filepath:
            return

        self.log("⏳ Загрузка CSV...")
        self.load_csv_btn.setEnabled(False)
        self.run_async_safe(self._load_csv_task(filepath))

    async def _load_csv_task(self, filepath):
        try:
            delimiter = ';'
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                first_line = f.readline()
                if '|' in first_line:
                    delimiter = '|'
                elif '\t' in first_line:
                    delimiter = '\t'
                elif ',' in first_line:
                    delimiter = ','

            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = [row for row in reader if row and any(cell.strip() for cell in row)]

                if not rows:
                    self.log("❌ Файл пуст")
                    return

                new_pairs = self.parse_pairs_rows(rows)

                if new_pairs:
                    self.pairs.extend(new_pairs)
                    self.save_pairs()
                    self.log(f"💾 Сохранено {len(new_pairs)} связок из CSV")
                    self.refresh_pairs()

                    with_dest = sum(1 for _, d in new_pairs if d)
                    without_dest = len(new_pairs) - with_dest

                    self.log(f"✅ Загружено {len(new_pairs)} связок")
                    self.log(f"📊 С чатом: {with_dest}, без чата: {without_dest}")

                    QMessageBox.information(
                        self,
                        "Готово",
                        f"✅ Загружено {len(new_pairs)} связок\n"
                        f"С чатом: {with_dest}\n"
                        f"Без чата: {without_dest}"
                    )
                else:
                    self.log("❌ Не найдено валидных связок")

        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.load_csv_btn.setEnabled(True)
