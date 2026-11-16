"""Russian / English strings for the toolkit shell. Add-ons get the current language through the
host API and keep their own strings."""
from __future__ import annotations

LANGS = ("ru", "en")
_lang = "ru"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in LANGS else "ru"


def lang() -> str:
    return _lang


def _pl_ru(n: int, a: str, b: str, c: str) -> str:
    m, d = n % 100, n % 10
    return c if 10 < m < 20 else a if d == 1 else b if 2 <= d <= 4 else c


STR = {
    "ru": {
        "tools": "ИНСТРУМЕНТЫ", "toolkit": "ТУЛКИТ", "addons": "Аддоны", "settings": "Настройки",
        "nav_empty": "Пока пусто — загляни\nв «Аддоны»", "check_upd": "Проверить обновления",
        "store_sub": "Инструменты качаются с GitHub, весят килобайты и обновляются сами",
        "available": "ДОСТУПНО", "shared": "ОБЩИЕ КОМПОНЕНТЫ", "from_file": "+ установить из файла",
        "catalog_loading": "Загружаю список аддонов…",
        "catalog_empty": "Аддонов пока нет — скоро появятся ✨",
        "catalog_error": "Не получилось загрузить список аддонов. Проверь интернет.",
        "retry": "Повторить",
        "addon": "аддон", "install": "Установить", "update": "Обновить", "open": "Открыть", "remove": "Удалить",
        "installed_v": "установлен · v{v}", "new": "новое", "needs_toolkit": "нужен тулкит {v}+",
        "local": "установлен из файла", "kb": "КБ", "mb": "МБ", "gb": "ГБ", "dec": ",",
        "needed_for": "нужен для", "nobody": "пока никому", "comp_ok": "✓ v{v}", "comp_missing": "{mb} МБ · скачается с аддоном",
        "download": "Скачать",
        "t_installed": "«{n}» установлен ✨", "t_updated": "«{n}» обновлён до {v} ✨", "t_removed": "«{n}» удалён",
        "t_restart": "Обновление применится после перезапуска", "t_comp": "{n} скачан ✨",
        "t_failed": "Не получилось: {e}", "t_bad_zip": "Это не аддон: {e}",
        "addon_failed": "Аддон «{n}» не запустился", "addon_failed_sub": "Текст ошибки — можно скопировать и прислать:",
        "settings_sub": "Общие для всех инструментов", "language": "ЯЗЫК", "updates": "ОБНОВЛЕНИЯ", "data": "ДАННЫЕ",
        "ru_sub": "интерфейс на русском", "en_sub": "interface in English",
        "au_addons": "Обновлять аддоны автоматически", "au_addons_s": "тихо, при запуске — они маленькие",
        "au_new": "Устанавливать новые аддоны сами", "au_new_s": "иначе они просто появятся в «Аддонах» с меткой «новое»",
        "au_ask": "Проверять обновления тулкита при запуске", "au_ask_s": "сам тулкит ~30 МБ, Windows спросит разрешение",
        "data_folder": "Папка с аддонами и компонентами", "open_folder": "Открыть",
        "lang_set": "Язык: русский",
        "upd_available": "Доступна версия <b>{v}</b>", "upd_notes": "что нового", "upd_later": "Позже",
        "upd_go": "Обновить", "upd_get": "Скачать", "upd_dl": "Скачиваю обновление… {p}%",
        "upd_installing": "Запускаю установщик — тулкит сейчас перезапустится",
        "upd_latest": "У тебя последняя версия ✨", "upd_fail": "Не получилось проверить обновления",
        "upd_checking": "проверяю…", "upd_cancelled": "Установка отменена", "upd_page": "Скачай установщик со страницы релиза",
        "addon_zip": "Аддон (*.zip)", "choose_zip": "Выбери zip аддона",
        "folders": "ПАПКИ", "f_output": "Готовые файлы", "f_downloads": "Загрузки", "change": "Изменить",
        "choose_folder": "Выбери папку",
        "folders_note": "Инструменты с включённым «Как в настройках тулкита» сохраняют сюда. В каждом можно выбрать и свою папку.",
        "presets": "ПРЕСЕТЫ", "wtp_title": "Файлы пресетов .wtp",
        "wtp_sub": "двойной клик по .wtp открывает тулкит и передаёт пресет нужному аддону",
        "wtp_missing": "Это пресет для аддона «{n}» — сначала установи его",
        "wtp_bad": "Это не файл пресета .wtp",
    },
    "en": {
        "tools": "TOOLS", "toolkit": "TOOLKIT", "addons": "Add-ons", "settings": "Settings",
        "nav_empty": "Nothing here yet —\ncheck Add-ons", "check_upd": "Check for updates",
        "store_sub": "Tools download from GitHub, weigh kilobytes and update themselves",
        "available": "AVAILABLE", "shared": "SHARED COMPONENTS", "from_file": "+ install from file",
        "catalog_loading": "Loading the add-on list…",
        "catalog_empty": "No add-ons yet — coming soon ✨",
        "catalog_error": "Couldn't load the add-on list. Check your connection.",
        "retry": "Retry",
        "addon": "add-on", "install": "Install", "update": "Update", "open": "Open", "remove": "Remove",
        "installed_v": "installed · v{v}", "new": "new", "needs_toolkit": "needs toolkit {v}+",
        "local": "installed from file", "kb": "KB", "mb": "MB", "gb": "GB", "dec": ".",
        "needed_for": "needed by", "nobody": "nobody yet", "comp_ok": "✓ v{v}", "comp_missing": "{mb} MB · downloads with an add-on",
        "download": "Download",
        "t_installed": "{n} installed ✨", "t_updated": "{n} updated to {v} ✨", "t_removed": "{n} removed",
        "t_restart": "The update applies after a restart", "t_comp": "{n} downloaded ✨",
        "t_failed": "Failed: {e}", "t_bad_zip": "Not an add-on: {e}",
        "addon_failed": "The {n} add-on failed to start", "addon_failed_sub": "Error text — copy it and send it over:",
        "settings_sub": "Shared by all tools", "language": "LANGUAGE", "updates": "UPDATES", "data": "DATA",
        "ru_sub": "интерфейс на русском", "en_sub": "interface in English",
        "au_addons": "Update add-ons automatically", "au_addons_s": "silently on start — they are tiny",
        "au_new": "Install new add-ons automatically", "au_new_s": "otherwise they just show up in Add-ons marked “new”",
        "au_ask": "Check for toolkit updates on start", "au_ask_s": "the toolkit is ~30 MB, Windows will ask for permission",
        "data_folder": "Add-ons and components folder", "open_folder": "Open",
        "lang_set": "Language: English",
        "upd_available": "Version <b>{v}</b> is available", "upd_notes": "what's new", "upd_later": "Later",
        "upd_go": "Update", "upd_get": "Download", "upd_dl": "Downloading the update… {p}%",
        "upd_installing": "Starting the installer — the toolkit will restart",
        "upd_latest": "You're on the latest version ✨", "upd_fail": "Couldn't check for updates",
        "upd_checking": "checking…", "upd_cancelled": "Installation cancelled", "upd_page": "Get the installer from the release page",
        "addon_zip": "Add-on (*.zip)", "choose_zip": "Pick an add-on zip",
        "folders": "FOLDERS", "f_output": "Finished files", "f_downloads": "Downloads", "change": "Change",
        "choose_folder": "Choose a folder",
        "folders_note": "Tools with “Same as toolkit settings” turned on save here. Each tool can also use its own folder.",
        "presets": "PRESETS", "wtp_title": ".wtp preset files",
        "wtp_sub": "double-click a .wtp to open the toolkit and hand the preset to its add-on",
        "wtp_missing": "This preset is for the “{n}” add-on — install it first",
        "wtp_bad": "Not a .wtp preset file",
    },
}


def t(key: str, **kw) -> str:
    s = STR[_lang].get(key) or STR["en"].get(key) or key
    return s.format(**kw) if kw else s


def fmt_size(mb: float) -> str:
    d = t("dec")
    if mb >= 1024:
        s = f"{mb / 1024:.2f} {t('gb')}"
    elif mb >= 10:
        s = f"{mb:.0f} {t('mb')}"
    elif mb >= 1:
        s = f"{mb:.1f} {t('mb')}"
    else:
        s = f"{max(1, round(mb * 1024))} {t('kb')}"
    return s.replace(".", d)


def plural_files(n: int) -> str:
    return f"{n} {_pl_ru(n, 'файл', 'файла', 'файлов')}" if _lang == "ru" else f"{n} file{'s' * (n != 1)}"
