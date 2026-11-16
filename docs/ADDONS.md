# Как сделать аддон для wxwx toolkit

Аддон — это zip с `manifest.json` и Python-пакетом. Тулкит скачивает его, распаковывает в
`%LOCALAPPDATA%\wxwx-toolkit\addons\<id>\` и показывает его виджет как отдельный инструмент в левом меню.

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
  "min_toolkit": "1.0.0"
}
```

| поле | что это |
|---|---|
| `id` | строчные латинские буквы, цифры, дефис. Он же имя папки |
| `entry` | `модуль:функция`. Имя модуля должно быть уникальным, например `wx_<id>` |
| `icon` | одна из иконок тулкита: `video`, `photo`, `dl`, `music`, `folder`, `addon` |
| `needs` | общие компоненты: `ffmpeg`, `yt-dlp`. Тулкит скачает их перед установкой аддона |
| `min_toolkit` | минимальная версия тулкита. Если тулкит старее, аддон не запустится и попросит обновиться |

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
host.data_dir              # pathlib.Path для своих файлов
host.toolkit_version       # "1.0.0"
host.api_version           # 1
```

Стили тулкита применяются ко всему окну, так что в аддоне работают те же objectName:
`h1`, `sub`, `section`, `accent`, `soft`, `ghost`, `link`, `card`, `row`, `rowTitle`, `rowSub`, `pill`.

Доступные библиотеки: стандартная библиотека Python и PySide6-Essentials (QtCore, QtGui, QtWidgets,
QtSvg, QtNetwork, QtConcurrent). Если аддону понадобится что-то ещё, это добавляется в сам тулкит
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

1. У аддона свой репо. Его релиз должен содержать asset **`wxwx-addon-<id>-<version>.zip`**
2. В `addons.json` этого репо (тулкита) добавляется запись:

```json
{
  "addons": [
    {
      "id": "compress",
      "repo": "ddam1k/wxwx-compress",
      "name": {"ru": "Видео", "en": "Video"},
      "description": {"ru": "MP4, WebM, GIF · CPU или NVENC", "en": "MP4, WebM, GIF · CPU or NVENC"},
      "icon": "video",
      "needs": ["ffmpeg"],
      "min_toolkit": "1.0.0"
    }
  ]
}
```

При следующем запуске тулкит покажет аддон в «Аддонах» с меткой «новое». Новые версии подтянутся сами:
тулкит сравнивает версию из имени zip в последнем релизе с установленной.

## Проверить локально

«Аддоны» → «+ установить из файла» → выбрать zip. Повторная установка того же id заменяет аддон
и сразу перезагружает его без перезапуска тулкита.
