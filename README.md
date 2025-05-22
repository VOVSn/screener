# Screener: Screenshot to Ollama Interaction Tool

<!-- Screenshot Placeholder: Main Application Window -->
<!-- Ideal: Show the main UI with custom prompt, action buttons, Ping Ollama, Re-open Session -->

**English** | [Русский](#-скриншот-в-ollama-инструмент-взаимодействия)

Screener is a desktop application that allows you to capture a region of your screen, send it to a running Ollama instance with a specific prompt, and interact with the response. You can ask follow-up questions about the image and Ollama's analysis, creating a conversation around the visual context.

## Features

*   **Screen Region Capture:** Easily select any part of your screen.
*   **Ollama Integration:** Sends the captured image and a user-defined or pre-configured prompt to your local Ollama instance (e.g., using models like LLaVA, Gemma, BakLLaVA for multimodal analysis).
*   **Configurable Hotkeys:** Define global hotkeys for different actions/prompts (e.g., "Solve this problem," "Describe this image," "Generate code from this UI mockup").
*   **Interactive Response Window:**
    *   Displays Ollama's response with markdown and Python syntax highlighting.
    *   Shows a preview of the captured image alongside the response.
    *   Allows asking follow-up questions about the image and the ongoing conversation.
    *   Navigate back and forth through the conversation history.
*   **Session Persistence:** Automatically saves each capture session (image + full conversation) for later review.
    *   "Re-open Last Session" button to quickly get back to your last interaction.
*   **Customizable Prompts:** Use pre-defined prompts tied to hotkeys or type your own custom prompt in the main UI.
*   **System Tray Integration:** Runs conveniently in the system tray with quick access to actions.
*   **Theming:** Light and Dark themes available.
*   **Multi-language Support:** UI available in English and Russian (easily extensible).
*   **Ollama Server Ping:** Utility to check if your Ollama server is reachable.

<!-- Screenshot Placeholder: Region Selection Overlay -->
<!-- Ideal: Show the screen dimmed, crosshair cursor, and a selection rectangle. -->

## Requirements

*   **Python 3.9+**
*   **Ollama Installed and Running:** You need a local Ollama instance with at least one multimodal model pulled (e.g., `ollama pull llava`, `ollama pull gemma:2b` with a vision model variant if available for gemma, or `ollama pull bakllava`).
    *   Ensure Ollama is accessible (default: `http://localhost:11434`).
*   **Tesseract OCR (Optional, for better text extraction by some models, not directly used by Screener but good for Ollama):** Installation varies by OS.
*   **(Linux Specific) X11 Windowing System:** `pynput` and `pyautogui` (for hotkeys and screenshots) generally work best on X11. Wayland support can be problematic. You might need `python3-tk` and `python3-dev` (or similar packages for your distribution). scrot `sudo apt install scrot` for pyautogui.
*   **(Linux Specific) `pystray` dependencies:** `sudo apt install python3-pil python3-pil.imagetk libappindicator3-dev python3-gi gir1.2-appindicator3-0.1` (or similar for your distro).
*   **(macOS Specific) Accessibility Permissions:** You may need to grant accessibility permissions to your terminal or Python interpreter for global hotkeys to work.

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/VOVSn/screener.git
    cd screener
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Ollama (if needed):**
    *   By default, Screener tries to connect to `http://localhost:11434/api/generate`.
    *   You can change the Ollama URL and default model in `settings.json` (created in the project root directory on first run, or you can create it manually based on `screener/settings.py` defaults).
    *   Example `settings.json`:
        ```json
        {
            "OLLAMA_URL": "http://localhost:11434/api/generate",
            "OLLAMA_MODEL": "llava:latest", // Your preferred multimodal model
            "OLLAMA_TIMEOUT_SECONDS": 180,
            "DEFAULT_LANGUAGE": "en",
            "DEFAULT_THEME": "dark",
            "DEFAULT_FONT_SIZE": 13,
            "ICON_FILENAME_PNG": "icon.png"
        }
        ```

5.  **Review Hotkeys:**
    *   Default hotkeys are defined in `screener/hotkeys.json`. You can customize the key combinations and prompts.
    *   Prompts can be localized (see `en` and `ru` examples).

## Usage

1.  **Run the application:**
    ```bash
    python main.py
    ```

2.  **Main Window:**
    *   Use the "Capture Region Manually" button with a custom prompt if desired.
    *   Pre-defined actions with their hotkeys are listed.
    *   Click "Ping Ollama" to test connectivity.
    *   Click "Re-open Last Session" to load your previous work.

3.  **Using Hotkeys:**
    *   Press a configured hotkey (e.g., `<ctrl>+<alt>+s`).
    *   Your mouse cursor will change to a crosshair. Click and drag to select a screen region.
    *   Release the mouse button to capture.

4.  **Response Window:**
    *   The captured image preview appears on the left.
    *   Ollama's response appears on the right.
    *   Type a follow-up question in the input field at the bottom and click "Ask."
    *   Use "Back" and "Forward" to navigate through the conversation history for the current image.
    *   Modifying a question at a previous point in history and asking will fork the conversation from that point.
    *   Adjust font size, copy the response, or close the window.

<!-- Screenshot Placeholder: Response Window -->
<!-- Ideal: Show the image preview, Ollama response, follow-up input field and Ask/Back/Forward buttons. -->

5.  **System Tray Menu (if `pystray` is installed):**
    *   Right-click the tray icon for options:
        *   Show/Hide Window
        *   Trigger a default capture action
        *   Change Language
        *   Change Theme
        *   Exit

## Customization

*   **`settings.json` (in project root):** Main application settings (Ollama URL, model, language, theme).
*   **`screener/hotkeys.json`:** Hotkey combinations, descriptions, and the initial prompts sent to Ollama for each action.
*   **`screener/ui_texts.json`:** Localization strings for the UI. Add new languages here.
*   **`screener/icon.png`:** Application icon.

## Troubleshooting

*   **Hotkeys not working (Linux):**
    *   Ensure you are on X11, not Wayland (Wayland can have issues with global hotkey libraries).
    *   Try running as root (not recommended for general use, but can help diagnose permission issues).
    *   Install `python3-tk` and `python3-dev`.
*   **Hotkeys not working (macOS):**
    *   Grant Accessibility permissions to your Terminal/IDE or the Python interpreter in System Settings -> Privacy & Security -> Accessibility.
*   **`PIL.ImageTk.PhotoImage` error or no tray icon:**
    *   Ensure `Pillow` is installed correctly. On Linux, you might need `python3-pil.imagetk`.
*   **Ollama connection errors:**
    *   Verify Ollama is running and accessible at the URL configured in `settings.json`.
    *   Check your firewall settings.
    *   Use the "Ping Ollama" button in the app to test.
*   **"Maximum recursion depth exceeded"**: If this occurs, it's likely a bug in the UI update logic. Please report it.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request. If you find any bugs or have feature suggestions, please open an issue.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (assuming you will add one).

---
<br>

## Screener: Скриншот в Ollama - Инструмент Взаимодействия

<!-- Screenshot Placeholder: Main Application Window (можно тот же, что и для английской части) -->

**[English](#screener-screenshot-to-ollama-interaction-tool)** | Русский

Screener — это десктопное приложение, которое позволяет вам захватывать область экрана, отправлять её на запущенный экземпляр Ollama с определенным запросом и взаимодействовать с ответом. Вы можете задавать уточняющие вопросы об изображении и анализе Ollama, создавая диалог вокруг визуального контекста.

## Возможности

*   **Захват области экрана:** Легко выбирайте любую часть экрана.
*   **Интеграция с Ollama:** Отправляет захваченное изображение и пользовательский или предварительно настроенный запрос на ваш локальный экземпляр Ollama (например, используя модели LLaVA, Gemma, BakLLaVA для мультимодального анализа).
*   **Настраиваемые горячие клавиши:** Определяйте глобальные горячие клавиши для различных действий/запросов (например, «Решить эту задачу», «Описать это изображение», «Сгенерировать код из этого макета UI»).
*   **Интерактивное окно ответа:**
    *   Отображает ответ Ollama с подсветкой синтаксиса markdown и Python.
    *   Показывает предварительный просмотр захваченного изображения рядом с ответом.
    *   Позволяет задавать уточняющие вопросы об изображении и текущем диалоге.
    *   Навигация вперед и назад по истории диалога.
*   **Сохранение сессий:** Автоматически сохраняет каждую сессию захвата (изображение + полный диалог) для последующего просмотра.
    *   Кнопка «Открыть последнюю сессию» для быстрого возврата к последнему взаимодействию.
*   **Пользовательские запросы:** Используйте предопределенные запросы, привязанные к горячим клавишам, или введите свой собственный запрос в главном интерфейсе.
*   **Интеграция с системным треем:** Удобно работает в системном трее с быстрым доступом к действиям.
*   **Темы оформления:** Доступны светлая и темная темы.
*   **Многоязычная поддержка:** Интерфейс доступен на английском и русском языках (легко расширяется).
*   **Пинг сервера Ollama:** Утилита для проверки доступности вашего сервера Ollama.

<!-- Screenshot Placeholder: Region Selection Overlay (можно тот же) -->

## Требования

*   **Python 3.9+**
*   **Установленный и запущенный Ollama:** Вам необходим локальный экземпляр Ollama с хотя бы одной загруженной мультимодальной моделью (например, `ollama pull llava`, `ollama pull gemma:2b` с вариантом vision-модели, если доступно для gemma, или `ollama pull bakllava`).
    *   Убедитесь, что Ollama доступен (по умолчанию: `http://localhost:11434`).
*   **Tesseract OCR (Опционально, для лучшего извлечения текста некоторыми моделями, Screener напрямую не использует, но полезно для Ollama):** Установка зависит от ОС.
*   **(Для Linux) Графическая подсистема X11:** `pynput` и `pyautogui` (для горячих клавиш и скриншотов) обычно лучше всего работают на X11. Поддержка Wayland может быть проблематичной. Вам могут понадобиться пакеты `python3-tk` и `python3-dev` (или аналогичные для вашего дистрибутива), а также `scrot` (`sudo apt install scrot`) для pyautogui.
*   **(Для Linux) Зависимости `pystray`:** `sudo apt install python3-pil python3-pil.imagetk libappindicator3-dev python3-gi gir1.2-appindicator3-0.1` (или аналогичные для вашего дистрибутива).
*   **(Для macOS) Разрешения на доступ (Accessibility):** Возможно, потребуется предоставить разрешения на доступ вашему терминалу или интерпретатору Python для работы глобальных горячих клавиш.

## Установка и Настройка

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/VOVSn/screener.git
    cd screener
    ```

2.  **Создайте виртуальное окружение (рекомендуется):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # В Windows: venv\Scripts\activate
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Настройте Ollama (при необходимости):**
    *   По умолчанию Screener пытается подключиться к `http://localhost:11434/api/generate`.
    *   Вы можете изменить URL-адрес Ollama и модель по умолчанию в файле `settings.json` (создается в корневом каталоге проекта при первом запуске, или вы можете создать его вручную на основе значений по умолчанию из `screener/settings.py`).
    *   Пример `settings.json`:
        ```json
        {
            "OLLAMA_URL": "http://localhost:11434/api/generate",
            "OLLAMA_MODEL": "llava:latest", // Ваша предпочитаемая мультимодальная модель
            "OLLAMA_TIMEOUT_SECONDS": 180,
            "DEFAULT_LANGUAGE": "ru", // язык по умолчанию
            "DEFAULT_THEME": "dark",
            "DEFAULT_FONT_SIZE": 13,
            "ICON_FILENAME_PNG": "icon.png"
        }
        ```

5.  **Проверьте горячие клавиши:**
    *   Горячие клавиши по умолчанию определены в `screener/hotkeys.json`. Вы можете настроить комбинации клавиш и запросы.
    *   Запросы могут быть локализованы (см. примеры для `en` и `ru`).

## Использование

1.  **Запустите приложение:**
    ```bash
    python main.py
    ```

2.  **Главное окно:**
    *   Используйте кнопку «Захватить область вручную» с пользовательским запросом, если это необходимо.
    *   Перечислены предопределенные действия с их горячими клавишами.
    *   Нажмите «Ping Ollama» для проверки соединения.
    *   Нажмите «Открыть последнюю сессию» для загрузки предыдущей работы.

3.  **Использование горячих клавиш:**
    *   Нажмите настроенную горячую клавишу (например, `<ctrl>+<alt>+s`).
    *   Курсор мыши изменится на перекрестие. Нажмите и перетащите, чтобы выбрать область экрана.
    *   Отпустите кнопку мыши для захвата.

4.  **Окно ответа:**
    *   Предварительный просмотр захваченного изображения появится слева.
    *   Ответ Ollama появится справа.
    *   Введите уточняющий вопрос в поле ввода внизу и нажмите «Спросить».
    *   Используйте кнопки «Назад» и «Вперед» для навигации по истории диалога для текущего изображения.
    *   Изменение вопроса на предыдущем этапе истории и нажатие «Спросить» создаст новую ветку диалога с этой точки.
    *   Отрегулируйте размер шрифта, скопируйте ответ или закройте окно.

<!-- Screenshot Placeholder: Response Window (можно тот же) -->
<!-- Идеально: показать превью изображения, ответ Ollama, поле для уточняющего вопроса и кнопки "Спросить", "Назад", "Вперед". -->

5.  **Меню в системном трее (если установлен `pystray`):**
    *   Щелкните правой кнопкой мыши по значку в трее для доступа к опциям:
        *   Показать/Скрыть окно
        *   Запустить стандартное действие захвата
        *   Изменить язык
        *   Изменить тему
        *   Выход

## Кастомизация

*   **`settings.json` (в корне проекта):** Основные настройки приложения (URL Ollama, модель, язык, тема).
*   **`screener/hotkeys.json`:** Комбинации горячих клавиш, описания и начальные запросы, отправляемые в Ollama для каждого действия.
*   **`screener/ui_texts.json`:** Строки локализации для интерфейса. Добавляйте сюда новые языки.
*   **`screener/icon.png`:** Иконка приложения.

## Устранение неполадок

*   **Горячие клавиши не работают (Linux):**
    *   Убедитесь, что вы используете X11, а не Wayland (Wayland может иметь проблемы с библиотеками глобальных горячих клавиш).
    *   Попробуйте запустить от имени root (не рекомендуется для обычного использования, но может помочь диагностировать проблемы с разрешениями).
    *   Установите `python3-tk` и `python3-dev`.
*   **Горячие клавиши не работают (macOS):**
    *   Предоставьте разрешения на «Универсальный доступ» (Accessibility) вашему Терминалу/IDE или интерпретатору Python в Системных настройках -> Конфиденциальность и безопасность -> Универсальный доступ.
*   **Ошибка `PIL.ImageTk.PhotoImage` или нет значка в трее:**
    *   Убедитесь, что `Pillow` установлен корректно. В Linux может потребоваться `python3-pil.imagetk`.
*   **Ошибки подключения к Ollama:**
    *   Убедитесь, что Ollama запущен и доступен по URL, указанному в `settings.json`.
    *   Проверьте настройки вашего брандмауэра.
    *   Используйте кнопку «Ping Ollama» в приложении для проверки.
*   **"Maximum recursion depth exceeded" (Превышена максимальная глубина рекурсии):** Если это произойдет, скорее всего, это ошибка в логике обновления интерфейса. Пожалуйста, сообщите об этом.

## Участие в разработке

Мы приветствуем ваш вклад! Пожалуйста, не стесняйтесь форкнуть репозиторий, вносить изменения и отправлять pull request. Если вы обнаружите какие-либо ошибки или у вас есть предложения по функциям, пожалуйста, создайте issue.