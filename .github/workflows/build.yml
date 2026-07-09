name: Build TelegramAutoBot

on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

env:
  PYTHON_VERSION: '3.11'
  APP_NAME: 'TelegramAutoBot'
  BUILD_DIR: './dist'
  PYTHONPATH: ${{ github.workspace }}

jobs:
  # Job 1: Тестирование и линтинг
  test:
    runs-on: macos-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: 🐍 Установка Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
          cache-dependency-path: requirements.txt
      
      - name: 📦 Установка зависимостей
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: 🧪 Smoke-тесты
        run: python test_smoke.py
      
      - name: ✅ Unit-тесты
        run: pytest test_telegram_bot.py -v --cov=. --cov-report=xml
      
      - name: 📊 Загрузка покрытия тестов
        uses: codecov/codecov-action@v3
        if: matrix.python-version == '3.11'
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

  # Job 2: Сборка для macOS (Intel + Apple Silicon)
  build-macos:
    needs: test
    runs-on: macos-latest
    strategy:
      matrix:
        arch: [x86_64, arm64]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: 🐍 Установка Python ${{ env.PYTHON_VERSION }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
          cache-dependency-path: requirements.txt
      
      - name: 📦 Установка зависимостей
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: 🔨 Проверка build.spec
        run: python -m PyInstaller --clean --dry-run build.spec
      
      - name: 🏗️ Сборка .app для ${{ matrix.arch }}
        run: |
          ARCHFLAGS=-Qunused-arguments LDFLAGS=-L/usr/local/opt/openssl/lib CPPFLAGS=-I/usr/local/opt/openssl/include \
          python -m PyInstaller --clean --noconfirm build.spec
      
      - name: 📋 Проверка структуры app
        run: |
          ls -la dist/
          ls -la dist/TelegramAutoBot.app/Contents/MacOS/
      
      - name: 📦 Упаковка DMG для ${{ matrix.arch }}
        run: |
          mkdir -p /tmp/dmg_contents
          cp -r dist/TelegramAutoBot.app /tmp/dmg_contents/
          ln -s /Applications /tmp/dmg_contents/Applications
          hdiutil create -srcfolder /tmp/dmg_contents \
                         -volname "${{ env.APP_NAME }}" \
                         -fs HFS+ -fsargs "-c c=63" \
                         -format UDZO \
                         -o ${{ env.APP_NAME }}_${{ matrix.arch }}_$(date +%Y%m%d).dmg
      
      - name: ⬆️ Загрузка артефактов (app)
        uses: actions/upload-artifact@v3
        with:
          name: TelegramAutoBot-${{ matrix.arch }}-app
          path: dist/TelegramAutoBot.app
          retention-days: 30
      
      - name: ⬆️ Загрузка артефактов (DMG)
        uses: actions/upload-artifact@v3
        with:
          name: TelegramAutoBot-${{ matrix.arch }}-dmg
          path: ./*.dmg
          retention-days: 30

  # Job 3: Code Quality
  quality:
    runs-on: macos-latest
    if: github.event_name == 'pull_request'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: 🐍 Установка Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
          cache-dependency-path: requirements.txt
      
      - name: 📦 Установка зависимостей
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install black mypy flake8 pylint
      
      - name: 🎨 Проверка форматирования (black)
        run: black --check *.py || true
      
      - name: 🔍 Статический анализ (mypy)
        run: mypy *.py --ignore-missing-imports || true
      
      - name: 📝 Проверка стиля (flake8)
        run: flake8 *.py --max-line-length=120 || true
