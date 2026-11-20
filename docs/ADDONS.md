# Как сделать аддон для wxwx toolkit

Аддон — это zip с `manifest.json` и Python-пакетом. Тулкит скачивает его, распаковывает в
`<папка тулкита>\data\addons\<id>\` (до 1.3 — `%LOCALAPPDATA%\wxwx-toolkit\addons\<id>\`) и показывает его виджет как отдельный инструмент в левом меню.

Готовый пример: [`examples/hello-addon`](../examples/hello-addon).

## Структура zip

```
manifest.json
wx_<id>/
    __init__.py        # def create(host) -> QWidget
    ...                # любые другие модули пакета
```

`manifest.json` может лежать в корне zip или в единственной папке внутри.

## manifest.json

```json
{
  "id": "compress",
  "version": "1.0.0",
  "entry": "wx_compress:create",
  "name": {"ru": "Видео", "en": "Video"},
  "description": {"ru": "Сжатие видео через ffmpeg", "en": "Video compression via ffmpeg"},
  "icon": "video",
  "needs": ["ffmpeg"],
  "min_toolkit": "1.0.0",
  "settings": "wx_compress:settings"
}
```

| поле | что это |
|---|---|
| `id` | строчные латинские буквы, цифры, дефис. Он же имя папки |
| `entry` | `модуль:функция`. Имя модуля должно быть уникальным, например `wx_<id>` |
| `icon` | одна из иконок тулкита: `video`, `photo`, `dl`, `music`, `folder`, `addon` |
| `needs` | общие компоненты: `ffmpeg`, `yt-dlp`. Тулкит скачает их перед установкой аддона |
| `min_toolkit` | минимальная версия тулкита. Если тулкит старее, аддон не запустится и попросит обновиться |
| `settings` | необязательно (1.2+): `модуль:функция`, `settings(host) -> QWidget`. Виджет станет вкладкой аддона в «Настройках» |

## Что получает аддон: `host`

```python
host.lang                  # "ru" | "en"
host.theme                 # "dark" | "light"
host.colors                # палитра текущей темы: {"text": "#ecebef", "tint": "#b8a8e2", ...}
host.lang_changed          # Signal(str), подключи, чтобы перевести свой интерфейс на лету
host.theme_changed         # Signal(str)
host.component("ffmpeg")              # путь к ffmpeg.exe или None
host.component("ffmpeg", "ffprobe")   # путь к ffprobe.exe
host.toast("Готово ✨")                # всплывающее уведомление тулкита
host.folder("output")                 # папка готовых файлов из настроек тулкита (1.1+)
host.folder("downloads")              # папка загрузок (1.1+)
host.folders_changed                  # Signal(str kind) — пользователь сменил папку (1.1+)
host.preset_received                  # Signal(dict) — открыли .wtp для этого аддона (1.1+)
host.get("key", default) / host.set("key", value)   # настройки аддона (любые JSON-значения)
host.get("presets", [], addon="compress")         # прочитать настройку другого аддона (1.2+)
host.installed("compress")            # установлен ли другой аддон (1.2+)
host.open_settings()                  # открыть вкладку этого аддона в «Настройках» (1.2+)
host.settings_changed                 # Signal(str key) — после host.set(), страница и вкладка настроек видят друг друга (1.2+)
host.hints                 # True — подсказки показываются; False — включено «Меньше подсказок» (1.3+)
host.hints_changed         # Signal(bool) (1.3+)
host.hint(label, ...)      # пометить пояснения: в режиме «Меньше подсказок» тулкит их спрячет (1.3+)
                           # то же самое: label.setProperty("hint", True)
host.suffix()              # "_wx": суффикс готового файла — общий тулкита или свой у аддона (1.3+)
host.suffix_changed        # Signal(str) (1.3+)
host.suffix_widget("clip.mp4")  # готовый блок для вкладки настроек: «Как в настройках тулкита» или свой (1.3+)
host.send_to("compress", [path])  # открыть другой аддон и передать ему файлы (1.3.1+)
host.files_received        # Signal(list): файлы, которые прислал другой аддон (1.3.1+)
host.data_dir              # pathlib.Path для своих файлов
host.toolkit_version       # "1.0.0"
host.api_version           # 1
```

Страница аддона может определить два метода (1.2+), тулкит вызывает их при обновлении на лету и удалении:

```python
def is_busy(self) -> bool:   # True, пока идёт работа: тихое автообновление подождёт
def shutdown(self):          # остановить потоки и процессы — старая страница сейчас будет удалена
```

Стили тулкита применяются ко всему окну, так что в аддоне работают те же objectName:
`h1`, `sub`, `section`, `accent`, `soft`, `ghost`, `link`, `card`, `row`, `rowTitle`, `rowSub`, `pill`.

Доступные библиотеки: стандартная библиотека Python и PySide6: QtCore, QtGui, QtWidgets,
QtSvg, QtNetwork, QtConcurrent, а с 1.2 ещё QtMultimedia и QtMultimediaWidgets (видео и звук). Если аддону понадобится что-то ещё, это добавляется в сам тулкит
(`wxwx-toolkit.spec`) и выходит новая версия тулкита. Тогда в манифесте аддона поднимается `min_toolkit`.

## Пресеты `.wtp`

Общий формат пресетов для всех аддонов: JSON-файл с расширением `.wtp`.

```json
{
  "wtp": 1,
  "addon": "compress",
  "addon_name": "Видео",
  "addon_version": "1.1.0",
  "name": "Discord 10 МБ",
  "author": "yuyu",
  "created": "2026-11-16",
  "settings": { "...": "что угодно, это решает аддон" }
}
```

Экспорт и импорт внутри своего интерфейса аддон делает сам. Тулкит берёт на себя остальное:
двойной клик по `.wtp` в проводнике или перетаскивание файла на окно. Он открывает аддон с нужным `addon`
и отправляет ему `host.preset_received(dict)`. Если такой аддон не установлен, тулкит так и скажет.

## Как опубликовать

Наши аддоны живут прямо в этом репозитории, в `addons/<id>/` (manifest.json + пакет + `tests/`).

1. Поменять код и поднять `version` в `addons/<id>/manifest.json` (и `__version__` пакета, если он есть).
2. Actions → **publish add-ons** → Run workflow. Он прогонит тесты, соберёт zip, проверит аддон внутри
   тулкита и положит **`wxwx-addon-<id>-<version>.zip`** в текущий релиз тулкита (старую версию zip уберёт).
   Если такая версия уже опубликована, аддон пропускается — значит, забыли поднять версию.
3. Тулкиты у всех увидят обновление при запуске, по кнопке «Проверить обновления» или сами через 30 минут.
   Новая версия тулкита для этого не нужна. Сборка тулкита тоже прикладывает zip всех аддонов к своему релизу.

Аддон из чужого репозитория тоже можно добавить: его релиз должен содержать тот же asset, а в `addons.json`
указывается его `repo`.

Запись в `addons.json`:

```json
{
  "addons": [
    {
      "id": "compress",
      "repo": "ddam1k/wxwx-toolkit",
      "name": {"ru": "Видео", "en": "Video"},
      "description": {"ru": "MP4, WebM, GIF · CPU или NVENC", "en": "MP4, WebM, GIF · CPU or NVENC"},
      "icon": "video",
      "needs": ["ffmpeg"],
      "min_toolkit": "1.0.0"
    }
  ]
}
```

Тулкит покажет аддон в «Аддонах» с меткой «новое». Новые версии подтянутся сами:
тулкит сравнивает версию из имени zip в последнем релизе с установленной.

Собрать zip локально: `python scripts/build_addons.py` → `dist/addons/`.

## Проверить локально

«Аддоны» → «+ установить из файла» → выбрать zip. Повторная установка того же id заменяет аддон
и сразу перезагружает его без перезапуска тулкита.
