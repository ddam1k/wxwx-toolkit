"""Russian / English strings of the compressor (standalone app and toolkit add-on)."""
from __future__ import annotations

LANGS = ("ru", "en")
_lang = "ru"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in LANGS else "en"


def lang() -> str:
    return _lang


def _pl_ru(n: int, a: str, b: str, c: str) -> str:
    m, d = n % 100, n % 10
    return c if 10 < m < 20 else a if d == 1 else b if 2 <= d <= 4 else c


STR = {
    "ru": {
        "title": "Видео", "queue": "Очередь", "add": "+ Добавить", "clear": "Очистить", "no_files": "нет файлов",
        "empty": "Пусто. Закинь сюда что-нибудь ✨",
        "drop_b": "Перетащи видео сюда", "drop_or": "или выбери файлы",
        "drop_s": "MP4, MOV, MKV, WebM, GIF · можно папкой · .wtp — пресет",
        "drop_overlay": "Отпусти — добавлю в очередь",
        "s_naming": "ИМЯ ГОТОВОГО ФАЙЛА", "sec_preset": "ПРЕСЕТ", "sec_format": "ФОРМАТ", "sec_enc": "КОДИРОВАНИЕ", "sec_mode": "СЖАТИЕ",
        "sec_colors": "ПАЛИТРА GIF", "sec_size": "РАЗМЕР И FPS", "sec_audio": "ЗВУК", "sec_dest": "КУДА СОХРАНЯТЬ",
        "p_save": "+ Сохранить", "p_import": "Импорт", "p_note": "ПКМ по пресету — поделиться файлом .wtp, переименовать, удалить",
        "p_own": "Свой", "p_discord": "Discord 10 МБ", "p_telegram": "Telegram", "p_web": "Для веба", "p_archive": "Архив",
        "p_gif": "GIF-превью",
        "m_share": "Поделиться (.wtp)…", "m_dup": "Дублировать", "m_rename": "Переименовать…", "m_delete": "Удалить",
        "p_new_title": "Новый пресет", "p_name": "Название:", "p_rename_title": "Переименовать пресет",
        "p_copy": "{n} (копия)", "p_mine": "Мой #{n}",
        "t_saved_preset": "Пресет «{n}» сохранён", "t_deleted": "Пресет «{n}» удалён", "t_dup": "Копия создана — её можно менять",
        "t_exported": "Сохранено: {f} — кидай другу ✨", "t_imported": "Пресет «{n}» добавлен ✨", "t_imported_from": "Пресет «{n}» от {a} добавлен ✨",
        "t_wrong_addon": "Это пресет для аддона «{n}» — открой его там", "t_bad_wtp": "Это не файл пресета .wtp",
        "wtp_filter": "Пресет wxwx (*.wtp)", "share_title": "Поделиться пресетом", "import_title": "Импорт пресета",
        "cpu": "Процессор", "cpu_s": "меньше файл", "gpu": "Видеокарта", "gpu_s": "NVENC · быстро",
        "gpu_ready": "{n} · {av1}NVENC готов", "gpu_none": "Внешняя видеокарта не найдена — сжимаем на процессоре",
        "gpu_driver": "Видеокарта есть, но нужен драйвер NVIDIA новее — обнови его", "gpu_fail": "NVENC не запустился — наведи, чтобы увидеть ошибку",
        "gpu_checking": "Проверяю видеокарту…", "gif_cpu": "GIF кодируется только на процессоре", "vp9_cpu": "VP9 кодируется только на процессоре",
        "av1_old": "{n} · AV1 на видеокарте нужна RTX 40+", "nvidia": "NVIDIA",
        "mode_quality": "Качество", "mode_size": "Размер", "mode_ratio": "В N раз",
        "quality": "Качество", "smaller": "меньше файл", "better": "лучше картинка", "fit_in": "Уложиться в", "shrink_by": "Уменьшить в",
        "colors": "Цветов", "lighter": "легче", "smoother": "плавнее градиенты", "fps": "FPS", "fps_src": "исходный",
        "res_src": "Исходное", "a_keep": "Как есть", "a_compress": "Сжать", "a_none": "Без звука",
        "q_words": ["почти без потерь", "хорошее", "среднее", "заметно ужато", "максимально мелко"],
        "use_tk": "Как в настройках тулкита", "use_tk_s": "общая папка для всех инструментов",
        "o_beside": "Рядом", "o_beside_s": "с оригиналом", "o_sub": "Подпапка", "o_sub_s": "compressed", "o_custom": "Своя", "o_custom_s": "папка",
        "d_beside": "рядом с каждым видео", "d_example": "например {p}", "d_custom_s": "своя папка для этого инструмента",
        "d_tk_s": "из настроек тулкита", "d_change": "Изменить", "d_open": "Открыть", "d_pick": "Куда сохранять",
        "save_to": "Сохранится:", "beside_short": "рядом с оригиналами", "sub_short": "в подпапки «compressed»",
        "cmd": "ffmpeg-команда для первого файла", "copy": "копировать", "t_cmd_copied": "Команда скопирована",
        "total": "Итого", "go": "Сжать всё", "stop": "Стоп",
        "st_reading": "Читаю файл…", "st_queued": "В очереди", "st_start": "Запускаю…", "st_work": "Сжимаю · {p}%",
        "st_done": "Готово · {a} → {b}", "st_error": "Ошибка: {e}", "st_bad": "Не получилось прочитать — это точно видео?",
        "est_will": "БУДЕТ ≈", "est_now": "СТАЛО", "no_audio": "без звука", "rm_tip": "Убрать из очереди",
        "open_tip": "Двойной клик — показать в папке, когда готово",
        "t_no_videos": "Тут нет видеофайлов", "t_nothing": "Нечего сжимать — добавь видео", "t_stopped": "Остановлено",
        "t_done": "Готово ✨ сэкономлено {s} · файлы: {d}", "t_errors": " · ошибок: {n}",
        "t_failed": "Не получилось: {n} — наведи на статус, там текст ошибки",
        "no_ffmpeg": "Не нашла ffmpeg. В тулките он скачивается в «Аддонах», в отдельной программе — лежит в папке bin.",
        "busy_close": "Идёт сжатие. Остановить и выйти?",
        "video_filter": "Видео", "all_files": "Все файлы", "pick_videos": "Выбери видео",
        "mb": "МБ", "gb": "ГБ", "dec": ",",
    },
    "en": {
        "title": "Video", "queue": "Queue", "add": "+ Add", "clear": "Clear", "no_files": "no files",
        "empty": "Empty. Drop something here ✨",
        "drop_b": "Drop videos here", "drop_or": "or pick files",
        "drop_s": "MP4, MOV, MKV, WebM, GIF · folders too · .wtp presets",
        "drop_overlay": "Drop to add to the queue",
        "s_naming": "FINISHED FILE NAME", "sec_preset": "PRESET", "sec_format": "FORMAT", "sec_enc": "ENCODING", "sec_mode": "COMPRESSION",
        "sec_colors": "GIF PALETTE", "sec_size": "SIZE & FPS", "sec_audio": "AUDIO", "sec_dest": "SAVE TO",
        "p_save": "+ Save", "p_import": "Import", "p_note": "Right-click a preset to share it as .wtp, rename or delete",
        "p_own": "Custom", "p_discord": "Discord 10 MB", "p_telegram": "Telegram", "p_web": "For web", "p_archive": "Archive",
        "p_gif": "GIF preview",
        "m_share": "Share (.wtp)…", "m_dup": "Duplicate", "m_rename": "Rename…", "m_delete": "Delete",
        "p_new_title": "New preset", "p_name": "Name:", "p_rename_title": "Rename preset",
        "p_copy": "{n} (copy)", "p_mine": "My #{n}",
        "t_saved_preset": "Preset “{n}” saved", "t_deleted": "Preset “{n}” deleted", "t_dup": "Copy created — edit it freely",
        "t_exported": "Saved: {f} — send it to a friend ✨", "t_imported": "Preset “{n}” added ✨", "t_imported_from": "Preset “{n}” by {a} added ✨",
        "t_wrong_addon": "This preset is for the “{n}” add-on — open it there", "t_bad_wtp": "Not a .wtp preset file",
        "wtp_filter": "wxwx preset (*.wtp)", "share_title": "Share preset", "import_title": "Import preset",
        "cpu": "CPU", "cpu_s": "smaller file", "gpu": "GPU", "gpu_s": "NVENC · fast",
        "gpu_ready": "{n} · {av1}NVENC ready", "gpu_none": "No dedicated GPU found — encoding on the CPU",
        "gpu_driver": "GPU found, but the NVIDIA driver is too old — please update it", "gpu_fail": "NVENC failed to start — hover to see the error",
        "gpu_checking": "Checking the GPU…", "gif_cpu": "GIF is encoded on the CPU only", "vp9_cpu": "VP9 is encoded on the CPU only",
        "av1_old": "{n} · AV1 on the GPU needs an RTX 40+", "nvidia": "NVIDIA",
        "mode_quality": "Quality", "mode_size": "Size", "mode_ratio": "N× smaller",
        "quality": "Quality", "smaller": "smaller file", "better": "better picture", "fit_in": "Fit into", "shrink_by": "Shrink by",
        "colors": "Colors", "lighter": "lighter", "smoother": "smoother gradients", "fps": "FPS", "fps_src": "source",
        "res_src": "Source", "a_keep": "Keep", "a_compress": "Compress", "a_none": "No audio",
        "q_words": ["near lossless", "good", "medium", "heavily compressed", "smallest possible"],
        "use_tk": "Same as toolkit settings", "use_tk_s": "one folder for all tools",
        "o_beside": "Next to", "o_beside_s": "the original", "o_sub": "Subfolder", "o_sub_s": "compressed", "o_custom": "Own", "o_custom_s": "folder",
        "d_beside": "next to each video", "d_example": "e.g. {p}", "d_custom_s": "this tool's own folder",
        "d_tk_s": "from the toolkit settings", "d_change": "Change", "d_open": "Open", "d_pick": "Where to save",
        "save_to": "Saving to:", "beside_short": "next to the originals", "sub_short": "into “compressed” subfolders",
        "cmd": "ffmpeg command for the first file", "copy": "copy", "t_cmd_copied": "Command copied",
        "total": "Total", "go": "Compress all", "stop": "Stop",
        "st_reading": "Reading the file…", "st_queued": "Queued", "st_start": "Starting…", "st_work": "Compressing · {p}%",
        "st_done": "Done · {a} → {b}", "st_error": "Error: {e}", "st_bad": "Couldn't read it — is it really a video?",
        "est_will": "ABOUT", "est_now": "NOW", "no_audio": "no audio", "rm_tip": "Remove from the queue",
        "open_tip": "Double-click to show in folder when done",
        "t_no_videos": "No video files here", "t_nothing": "Nothing to compress — add some videos", "t_stopped": "Stopped",
        "t_done": "Done ✨ saved {s} · files: {d}", "t_errors": " · errors: {n}",
        "t_failed": "Failed: {n} — hover the status to see the error",
        "no_ffmpeg": "ffmpeg not found. In the toolkit it downloads from Add-ons; the standalone app keeps it in the bin folder.",
        "busy_close": "Compression is running. Stop and quit?",
        "video_filter": "Videos", "all_files": "All files", "pick_videos": "Pick videos",
        "mb": "MB", "gb": "GB", "dec": ".",
    },
}


def t(key: str, **kw):
    v = STR[_lang].get(key)
    if v is None:
        v = STR["en"].get(key, key)
    return v.format(**kw) if kw and isinstance(v, str) else v


def files_word(n: int) -> str:
    if _lang == "ru":
        return f"{n} {_pl_ru(n, 'файл', 'файла', 'файлов')}"
    return f"{n} file{'s' * (n != 1)}"


def fmt_mb(mb: float) -> str:
    d = t("dec")
    if mb >= 1024:
        s = f"{mb / 1024:.2f} {t('gb')}"
    elif mb >= 10:
        s = f"{mb:.0f} {t('mb')}"
    else:
        s = f"{mb:.1f} {t('mb')}"
    return s.replace(".", d)
