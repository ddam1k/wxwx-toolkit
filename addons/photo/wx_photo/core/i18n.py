"""Russian / English strings of the Photo add-on."""
from __future__ import annotations

_lang = "ru"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in STR else "en"
    from .. import kit
    kit.set_lang(_lang)


def lang() -> str:
    return _lang


def plural(n: int, one: str, few: str, many: str) -> str:
    if _lang == "en":
        return one if n == 1 else many
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def files(n: int) -> str:
    return f"{n} " + (plural(n, "файл", "файла", "файлов") if _lang == "ru" else plural(n, "file", "files", "files"))


def pics(n: int) -> str:
    return f"{n} " + (plural(n, "картинку", "картинки", "картинок") if _lang == "ru" else plural(n, "picture", "pictures", "pictures"))


def fmt_size(b: float) -> str:
    if b <= 0:
        return "—"
    if b < 1024 * 1024:
        return f"{max(1, round(b / 1024))} " + ("КБ" if _lang == "ru" else "KB")
    mb = b / 1048576
    s = f"{mb:.1f}" if mb < 10 else f"{mb:.0f}"
    return (s.replace(".", ",") + " МБ") if _lang == "ru" else (s + " MB")


STR = {
    "ru": {
        "title": "Фото", "files_sum": "{f} · {s}", "no_files": "нет файлов",
        "add": "Добавить…", "clear_list": "Очистить", "clear_tip": "Убрать всё из списка — файлы останутся на месте",
        "empty_t": "Пусто", "empty_s": "Закинь сюда фотки, скриншоты или рендеры.\nJPG, PNG, WebP, HEIC, AVIF…",
        "drop": "Отпусти — добавлю картинки",
        "added": "Добавила {n}", "added_skip": "Добавила {n}, ещё {k} уже были в списке", "not_img": "Тут нужны картинки",
        "cleared": "Список пуст — файлы на месте", "removed": "Убрала из списка",
        "geo": "геометка", "geo_keep": "есть геометка", "counting": "считаю…", "will": "будет ≈", "became": "стало",
        "st_wait": "В очереди", "st_work": "Сжимаю…", "st_done": "Готово · {s}", "st_err": "Не получилось: {e}",
        "unreadable": "не открывается",
        "cmp_tip": "Сравнить «было / стало»", "rm_tip": "Убрать из списка",
        # panel
        "b_preset": "Пресет", "p_web": "Для сайта", "p_tg": "Telegram", "p_light": "Лёгкие", "p_loss": "Без потерь",
        "p_own": "◐ Свой", "preset_note": "Меняешь что-то ниже — пресет становится «Своим» и запоминается.",
        "b_format": "Формат", "f_orig": "Исходный", "f_jpg": "JPG", "f_webp": "WebP", "f_avif": "AVIF", "f_png": "PNG",
        "n_orig": "Каждый файл остаётся в своём формате: JPG — JPG, PNG — PNG.",
        "n_jpg": "Открывается вообще везде.", "n_jpg_alpha": "Прозрачность станет белым фоном.",
        "n_webp": "На 25–35% легче JPG, прозрачность сохраняется. Открывают браузеры, Telegram, Discord, Windows.",
        "n_avif": "Самый лёгкий, но сжимается дольше, а старые программы его не открывают.",
        "n_avif_alpha": "Прозрачность станет белым фоном.",
        "n_png": "Без потерь — для скриншотов, логотипов и всего с прозрачностью. Фото в PNG станут тяжелее.",
        "b_quality": "Качество", "q_light": "легче", "q_orig": "как оригинал",
        "q95": "почти без потерь", "q85": "отлично", "q75": "хорошо — разницы почти не видно", "q60": "заметно на деталях",
        "q40": "видно артефакты", "q_note": "Нажми на картинку слева — откроется сравнение «было / стало».",
        "q_png": "PNG сжимается без потерь — качество не настраивается.",
        "b_size": "Размер", "sz_0": "Не менять", "sz_own": "свой", "size_note": "По длинной стороне. Те, что меньше, не растягиваю.",
        "size_bad": "Впиши число от 64 до 16384",
        "b_privacy": "Приватность", "strip_t": "Убрать данные о камере и месте",
        "strip_s": "EXIF и геометка — то, что видно другим, если выложить оригинал",
        "strip_note": "Данные о камере переносятся только в JPG — в WebP, AVIF и PNG их не будет в любом случае.",
        "b_dest": "Куда сохранять", "tk_t": "Как в настройках тулкита", "tk_s": "общая папка и суффикс {s}",
        "beside": "рядом с оригиналами", "example": "например {n}",
        "total": "Итого", "go": "Сжать", "go_n": "Сжать {n}", "saving": "Сжимаю {i} из {n}…",
        "saveto": "Сохранится:", "done": "Готово ✨ {n}", "done_err": "Готово: {n}, не получилось: {k}",
        "no_ffmpeg": "Для HEIC и AVIF нужен ffmpeg — поставь его в «Аддонах»",
        # compare
        "before": "Было", "after": "Будет", "zoom": "Увеличить", "close": "Закрыть",
        "cmp_hint": "Тяни мышкой — сравниваешь половинки · Z — увеличить · Esc — закрыть. Меняй качество справа — картинка обновится",
        # settings
        "s_defaults": "ПО УМОЛЧАНИЮ", "s_preset": "Пресет при запуске",
        "s_dest": "КУДА СОХРАНЯТЬ", "s_formats": "Читает JPG, PNG, WebP, GIF, BMP, TIFF, а через ffmpeg ещё HEIC, AVIF и другие.",
    },
    "en": {
        "title": "Photo", "files_sum": "{f} · {s}", "no_files": "no files",
        "add": "Add…", "clear_list": "Clear", "clear_tip": "Remove everything from the list — the files stay where they are",
        "empty_t": "Empty", "empty_s": "Drop photos, screenshots or renders here.\nJPG, PNG, WebP, HEIC, AVIF…",
        "drop": "Drop — I'll add the pictures",
        "added": "Added {n}", "added_skip": "Added {n}, {k} more were already here", "not_img": "This needs pictures",
        "cleared": "The list is empty — the files are untouched", "removed": "Removed from the list",
        "geo": "location", "geo_keep": "has a location", "counting": "counting…", "will": "≈", "became": "now",
        "st_wait": "Queued", "st_work": "Compressing…", "st_done": "Done · {s}", "st_err": "Failed: {e}",
        "unreadable": "can't be opened",
        "cmp_tip": "Compare before / after", "rm_tip": "Remove from the list",
        "b_preset": "Preset", "p_web": "For the web", "p_tg": "Telegram", "p_light": "Light", "p_loss": "Lossless",
        "p_own": "◐ Own", "preset_note": "Change anything below and the preset becomes «Own» — it is remembered.",
        "b_format": "Format", "f_orig": "Original", "f_jpg": "JPG", "f_webp": "WebP", "f_avif": "AVIF", "f_png": "PNG",
        "n_orig": "Every file keeps its format: JPG stays JPG, PNG stays PNG.",
        "n_jpg": "Opens absolutely everywhere.", "n_jpg_alpha": "Transparency becomes a white background.",
        "n_webp": "25–35% lighter than JPG, keeps transparency. Browsers, Telegram, Discord and Windows open it.",
        "n_avif": "The lightest, but slower to make, and older programs can't open it.",
        "n_avif_alpha": "Transparency becomes a white background.",
        "n_png": "Lossless — for screenshots, logos and anything transparent. Photos get heavier in PNG.",
        "b_quality": "Quality", "q_light": "lighter", "q_orig": "like the original",
        "q95": "nearly lossless", "q85": "excellent", "q75": "good — hard to tell apart", "q60": "visible on details",
        "q40": "visible artifacts", "q_note": "Click a picture on the left to compare before / after.",
        "q_png": "PNG is lossless — there is no quality to set.",
        "b_size": "Size", "sz_0": "Keep", "sz_own": "own", "size_note": "By the longest side. Smaller ones aren't stretched.",
        "size_bad": "Enter a number from 64 to 16384",
        "b_privacy": "Privacy", "strip_t": "Remove camera and location data",
        "strip_s": "EXIF and the location — what others see if you post the original",
        "strip_note": "Camera data is carried over only into JPG — WebP, AVIF and PNG never get it.",
        "b_dest": "Where to save", "tk_t": "As in the toolkit settings", "tk_s": "shared folder and the {s} suffix",
        "beside": "next to the originals", "example": "e.g. {n}",
        "total": "Total", "go": "Compress", "go_n": "Compress {n}", "saving": "Compressing {i} of {n}…",
        "saveto": "Saved to:", "done": "Done ✨ {n}", "done_err": "Done: {n}, failed: {k}",
        "no_ffmpeg": "HEIC and AVIF need ffmpeg — install it in «Add-ons»",
        "before": "Before", "after": "After", "zoom": "Zoom", "close": "Close",
        "cmp_hint": "Drag to compare the halves · Z — zoom · Esc — close. Change the quality on the right and the picture updates",
        "s_defaults": "DEFAULTS", "s_preset": "Preset at start",
        "s_dest": "WHERE TO SAVE", "s_formats": "Reads JPG, PNG, WebP, GIF, BMP, TIFF, and through ffmpeg also HEIC, AVIF and more.",
    },
}


def t(key: str, **kw):
    s = STR[_lang].get(key, STR["en"].get(key, key))
    return s.format(**kw) if kw and isinstance(s, str) else s
