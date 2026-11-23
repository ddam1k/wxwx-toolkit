"""Russian / English strings of the Clips add-on."""
from __future__ import annotations

_lang = "ru"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in STR else "en"


def lang() -> str:
    return _lang


def pl(n: int, one: str, few: str, many: str, en_one: str = "", en_many: str = "") -> str:
    """'3 клипа' / '3 clips'."""
    if _lang != "ru":
        return f"{n} {en_one if n == 1 else en_many}"
    d, h = n % 10, n % 100
    w = one if d == 1 and h != 11 else few if 2 <= d <= 4 and not 12 <= h <= 14 else many
    return f"{n} {w}"


def clips_n(n: int) -> str:
    return pl(n, "клип", "клипа", "клипов", "clip", "clips")


def files_n(n: int) -> str:
    return pl(n, "файл", "файла", "файлов", "file", "files")


def segs_n(n: int) -> str:
    return pl(n, "сегмент", "сегмента", "сегментов", "segment", "segments")


def fmt_mb(mb: float) -> str:
    d = "," if _lang == "ru" else "."
    gb, mbu = ("ГБ", "МБ") if _lang == "ru" else ("GB", "MB")
    if mb >= 1024:
        s = f"{mb / 1024:.2f} {gb}"
    elif mb >= 10:
        s = f"{mb:.0f} {mbu}"
    else:
        s = f"{mb:.1f} {mbu}"
    return s.replace(".", d)


STR = {
    "ru": {
        "title": "Клипы",
        "sub_nofolder": "Обрезать и ужать записи из игр за один проход",
        "nv_folder": "Папка NVIDIA", "change_lc": "изменить",
        "pick": "Выбери клипы", "open_n": "Открыть {n} →", "unpick": "Снять выбор",
        "tab_new": "Новые", "tab_folders": "Папки игр",
        "no_new": "Новых клипов нет", "since_last": "с последнего запуска", "since_day": "за сутки",
        "since_week": "за неделю",
        "select_all": "Выбрать все", "unselect_all": "Снять выбор",
        "not_nv_t": "Клип не из NVIDIA?", "not_nv_s": "Перетащи любые видео сюда или нажми, чтобы выбрать",
        "drop_t": "Перетащи клипы сюда", "drop_s": "или нажми, чтобы выбрать файлы · MP4, MOV, MKV, WebM",
        "tip_t": "Пишешь клипы через NVIDIA?", "tip_s": "Укажи папку — новые клипы будут ждать тебя здесь.",
        "tip_btn": "Указать папку",
        "resume_t": "Открыто: {n}", "resume_s": "нарезка сохранится, пока тулкит открыт",
        "resume_btn": "Продолжить нарезку →",
        "folders_sum": "{f} · {c} · {size}", "folders_w": ("папка", "папки", "папок"),
        "col_game": "ИГРА", "col_count": "КЛИПОВ", "col_size": "РАЗМЕР", "col_last": "СВЕЖИЙ КЛИП",
        "root_files": "Файлы в корне", "all_games": "Все игры",
        "sort_new": "Сначала новые", "sort_old": "Сначала старые", "sort_big": "Самые тяжёлые",
        "tag_new": "NEW", "tag_open": "ОТКРЫТ", "tag_done": "✓ ГОТОВО", "tag_cut": "КЛИП",
        "sort_name": "По имени",
        "trash_btn": "Удалить", "trash_tip": "Удалить этот клип в корзину Windows",
        "trash_one": "В корзине: {n}", "undo_trash": "Вернуть", "trash_back": "Вернула клип ✨",
        "trash_fail": "Не получилось удалить — файл занят другой программой", "card_trash": "В корзину",
        "scanning": "Смотрю папку…", "folder_missing": "Папка не найдена: {p}", "folder_empty": "Здесь пока нет клипов",
        "today": "сегодня, {t}", "yesterday": "вчера, {t}",
        "months": ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"),
        "dropv": "Отпусти — открою клипы", "pick_files": "Выбери клипы", "video_files": "Видео",

        "gallery": "← Галерея", "clear": "Очистить", "add": "Добавить", "add_sub": "из галереи\nили файлом",
        "add_sub_nf": "или перетащи\nфайлы",
        "start": "Начало", "end": "Конец", "loop_tip": "Повтор (L)", "playcut_tip": "Проиграть нарезку (C)",
        "hint_single": "Пробел — пауза · I / O — начало / конец · ← → — кадр (Shift — секунда) · C — проиграть нарезку · Tab — след. клип",
        "hint_multi": "I — начало · O — конец · ✎ у сегмента — править его ключами · C — следующий сегмент · Del — удалить · Esc — готово",
        "step1": "Нарезка", "step2": "Сжатие и сохранение",
        "sec_how": "КАК РЕЗАТЬ",
        "mode_single": "Отрезок", "mode_single_s": "один кусок: начало и конец",
        "mode_multi": "Сегменты", "mode_multi_s": "несколько кусков по ключам",
        "sec_cut": "ОТРЕЗОК", "reset": "Сбросить", "apply_all": "Ко всем",
        "t_start": "НАЧАЛО", "t_end": "КОНЕЦ", "t_len": "ДЛИНА",
        "note_single": "Тяни ручки на таймлайне или впиши время руками.",
        "sec_segs": "СЕГМЕНТЫ",
        "seg_empty": "Сегментов пока нет.\nПоставь I на начале и O на конце куска.",
        "type_hint": "Время можно вписать руками", "total_lc": "всего",
        "note_multi": "<b>Новый сегмент:</b> плейхед на пустое место → I, потом в конец куска → O.<br>"
                      "<b>Поправить:</b> нажми ✎ у сегмента — теперь I / O двигают его начало и конец, "
                      "где бы ни стоял плейхед. Сегменты могут наезжать друг на друга. Esc — готово.",
        "sec_merge": "КАК СОХРАНИТЬ СЕГМЕНТЫ",
        "merge_one": "Склеить", "merge_one_s": "один файл", "merge_sep": "Отдельно", "merge_sep_s": "файл на сегмент",
        "after_cut": "После нарезки", "of": "из {d}", "next": "Далее — сжатие  →",
        "files_line": "{c} → {f}", "whole_line": " · {n} без сегментов — целиком",

        "sec_comp": "СЖАТИЕ", "no_comp": "✂ Без сжатия",
        "no_comp_d": "Только обрезать, без пережатия: мгновенно, но режет по ключевым кадрам (±1–2 с), звуковые дорожки не смешиваются.",
        "presets_note": "Пресеты общие с аддоном «Видео» — свои и импортированные .wtp тоже здесь.",
        "enc_gpu": "Видеокарта", "enc_gpu_s": "NVENC · быстро", "enc_cpu": "Процессор", "enc_cpu_s": "меньше файл",
        "gpu_none": "Видеокарта NVIDIA не найдена — жмём на процессоре",
        "gpu_checking": "Проверяю видеокарту…",
        "sec_sound": "ЗВУК", "track_n": "дорожка {n}", "track_game": "Игра", "track_mic": "Микрофон",
        "track_x": "Звук",
        "no_audio": "В этом клипе нет звука",
        "sound_note": "В записях NVIDIA игра и микрофон — разные дорожки. Включённые смешаются в одну.",
        "muted": "Клип будет без звука",
        "sec_dest": "КУДА СОХРАНЯТЬ", "same_tk": "Как в настройках тулкита",
        "same_tk_s": "общая папка для всех инструментов",
        "d_beside": "Рядом", "d_subfolder": "Подпапка", "d_custom": "Своя папка",
        "d_beside_s": "в папке каждого клипа", "d_subfolder_s": "подпапка «clips» рядом с клипом",
        "d_custom_s": "одна папка для всего", "d_custom_none": "папка не выбрана",
        "open": "Открыть", "change": "Изменить", "choose_folder": "Куда сохранять клипы",
        "saveto": "Сохранится", "beside_orig": "рядом с оригиналами", "subfolder_orig": "в «clips» рядом с оригиналами",
        "total": "Итого",
        "go": "Обрезать и сжать всё ({f})", "go_copy": "Обрезать всё ({f})", "stop": "Стоп · {k}/{n}",
        "done": "Готово ✨ {f} · {a} → {b}", "done_errors": "Готово, но с ошибками: {n}", "stopped": "Остановлено",
        "failed": "Не получилось: {e}",

        "key_pending": "Ключ начала стоит — теперь конец O", "too_short": "Конец должен быть правее начала",
        "no_room": "Тут нет места — новые сегменты не наезжают на старые",
        "cleared_segs": "Сегменты очищены", "reset_done": "Обрезка сброшена", "applied_all": "Ко всем клипам: {a} → {b}",
        "added_clips": "Клипы открыты — смотри и режь ✂", "no_segs": "Сегментов пока нет",
        "time_bad": "Не поняла время — пиши как 01:23.45 или 83.4", "clamped": "Время подвинула до допустимого",
        "edit_bar": "✎ Правлю сегмент {n} · I — начало · O — конец", "edit_done": "Готово",
        "pl_seg": "▶ сегмент {n}", "pl_next": " · C — следующий", "pl_cut": "▶ нарезка", "pl_all": "▶ все сегменты",
        "loop": "↻ повтор", "loading": "Загружаю…", "bad_file": "Не получилось открыть: {n}",

        "s_folder": "ПАПКА С КЛИПАМИ NVIDIA", "s_unset": "Не задана",
        "s_set_sub": "смотрю все подпапки игр — новые клипы появятся в «Клипах»",
        "s_unset_sub": "без неё клипы нужно перетаскивать руками",
        "s_find": "Найти сама", "s_pick": "Выбрать…",
        "s_note": "NVIDIA App кладёт клипы в <b>Видео\\NVIDIA\\&lt;Игра&gt;</b>, старый ShadowPlay — в <b>Видео\\&lt;Игра&gt;</b>. "
                  "Свой путь можно посмотреть в оверлее <b>Alt+Z</b> → настройки записи.",
        "s_found": "Нашла: {p}", "s_notfound": "Не нашла клипов NVIDIA — выбери папку сама",
        "s_new": "ЧТО СЧИТАТЬ НОВЫМИ", "new_last": "С последнего запуска", "new_day": "За сутки", "new_week": "За неделю",
        "s_mark": "Помечать обработанные клипы", "s_mark_s": "«✓ готово» в галерее, и они больше не считаются новыми",
        "s_cut": "НАРЕЗКА ПО УМОЛЧАНИЮ", "s_merge": "Склеивать сегменты в один файл",
        "s_merge_s": "иначе — отдельный файл на каждый сегмент",
        "s_naming": "ИМЯ ГОТОВОГО ФАЙЛА", "s_naming_segs": "Если сегменты отдельными файлами, к имени добавится номер: {a}, {b}",
        "s_cache": "КЭШ ПРЕВЬЮ", "s_cache_t": "Кадры для галереи и таймлайна", "s_cache_s": "занимает {mb}",
        "s_cache_btn": "Очистить", "s_cache_done": "Кэш очищен",
        "p_discord": "Discord 10 МБ", "p_telegram": "Telegram", "p_web": "Для веба", "p_archive": "Архив",
        "p_gif": "GIF-превью", "own_preset": "твой пресет",
        "multi_tip": "Ставь ключи: I — начало, O — конец ✂", "cleared": "Список очищен",
        "seg_sub": "{s} с · {f} кадров",
        "del_orig": "Удалить оригиналы после сохранения", "del_orig_s": "отправятся в корзину — если что, их можно вернуть",
        "trashed": "Оригиналы в корзине: {n}",
        "folder_previews": "превью папок", "s_fprev": "Превью в «Папках игр»",
        "s_fprev_s": "кадр из последнего клипа вместо иконки папки",
        "d_q": "качество {q}", "d_size": "уложить в {mb}", "d_ratio": "в {r} раза меньше", "d_src_res": "исходное разрешение",
        "d_fps": "{f} fps", "d_colors": "{n} цветов", "d_noaudio": "без звука",
    },
    "en": {
        "title": "Clips",
        "sub_nofolder": "Trim and shrink game recordings in one go",
        "nv_folder": "NVIDIA folder", "change_lc": "change",
        "pick": "Pick clips", "open_n": "Open {n} →", "unpick": "Clear selection",
        "tab_new": "New", "tab_folders": "Game folders",
        "no_new": "No new clips", "since_last": "since the last launch", "since_day": "last 24 hours",
        "since_week": "last week",
        "select_all": "Select all", "unselect_all": "Clear selection",
        "not_nv_t": "Clip not from NVIDIA?", "not_nv_s": "Drop any videos here or click to pick them",
        "drop_t": "Drop clips here", "drop_s": "or click to pick files · MP4, MOV, MKV, WebM",
        "tip_t": "Recording clips with NVIDIA?", "tip_s": "Set the folder and new clips will wait for you here.",
        "tip_btn": "Set the folder",
        "resume_t": "Open: {n}", "resume_s": "your cuts stay while the toolkit is open",
        "resume_btn": "Continue cutting →",
        "folders_sum": "{f} · {c} · {size}", "folders_w": ("folder", "folders", "folders"),
        "col_game": "GAME", "col_count": "CLIPS", "col_size": "SIZE", "col_last": "LATEST CLIP",
        "root_files": "Files in the root", "all_games": "All games",
        "sort_new": "Newest first", "sort_old": "Oldest first", "sort_big": "Largest",
        "tag_new": "NEW", "tag_open": "OPEN", "tag_done": "✓ DONE", "tag_cut": "CLIP",
        "sort_name": "By name",
        "trash_btn": "Delete", "trash_tip": "Move this clip to the Windows Recycle Bin",
        "trash_one": "In the Bin: {n}", "undo_trash": "Undo", "trash_back": "The clip is back ✨",
        "trash_fail": "Couldn't delete — another program is using the file", "card_trash": "To the Bin",
        "scanning": "Looking through the folder…", "folder_missing": "Folder not found: {p}", "folder_empty": "No clips here yet",
        "today": "today, {t}", "yesterday": "yesterday, {t}",
        "months": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        "dropv": "Drop to open the clips", "pick_files": "Pick clips", "video_files": "Video",

        "gallery": "← Gallery", "clear": "Clear", "add": "Add", "add_sub": "from the gallery\nor a file",
        "add_sub_nf": "or drop\nfiles",
        "start": "Start", "end": "End", "loop_tip": "Loop (L)", "playcut_tip": "Play the cut (C)",
        "hint_single": "Space — pause · I / O — start / end · ← → — frame (Shift — second) · C — play the cut · Tab — next clip",
        "hint_multi": "I — start · O — end · ✎ on a segment — edit it with the keys · C — next segment · Del — delete · Esc — done",
        "step1": "Cutting", "step2": "Compress & save",
        "sec_how": "HOW TO CUT",
        "mode_single": "One piece", "mode_single_s": "a start and an end",
        "mode_multi": "Segments", "mode_multi_s": "several pieces by keys",
        "sec_cut": "PIECE", "reset": "Reset", "apply_all": "To all",
        "t_start": "START", "t_end": "END", "t_len": "LENGTH",
        "note_single": "Drag the handles on the timeline or type the time.",
        "sec_segs": "SEGMENTS",
        "seg_empty": "No segments yet.\nPress I at the start and O at the end of a piece.",
        "type_hint": "You can type the times", "total_lc": "total",
        "note_multi": "<b>New segment:</b> playhead on an empty spot → I, then at the end of the piece → O.<br>"
                      "<b>Adjust:</b> press ✎ on a segment — now I / O move its start and end wherever the playhead is. "
                      "Segments may overlap. Esc — done.",
        "sec_merge": "HOW TO SAVE SEGMENTS",
        "merge_one": "Join", "merge_one_s": "one file", "merge_sep": "Separate", "merge_sep_s": "a file per segment",
        "after_cut": "After cutting", "of": "of {d}", "next": "Next — compression  →",
        "files_line": "{c} → {f}", "whole_line": " · {n} without segments — whole",

        "sec_comp": "COMPRESSION", "no_comp": "✂ No compression",
        "no_comp_d": "Just cut, no re-encode: instant, but cuts land on keyframes (±1–2 s) and audio tracks aren't mixed.",
        "presets_note": "Presets are shared with the Video add-on — your own and imported .wtp ones too.",
        "enc_gpu": "Graphics card", "enc_gpu_s": "NVENC · fast", "enc_cpu": "Processor", "enc_cpu_s": "smaller file",
        "gpu_none": "No NVIDIA card found — using the processor",
        "gpu_checking": "Checking the graphics card…",
        "sec_sound": "SOUND", "track_n": "track {n}", "track_game": "Game", "track_mic": "Microphone",
        "track_x": "Sound",
        "no_audio": "This clip has no sound",
        "sound_note": "NVIDIA records the game and the mic as separate tracks. The ones you keep are mixed into one.",
        "muted": "The clip will be silent",
        "sec_dest": "WHERE TO SAVE", "same_tk": "Same as toolkit settings",
        "same_tk_s": "one folder for all tools",
        "d_beside": "Beside", "d_subfolder": "Subfolder", "d_custom": "My folder",
        "d_beside_s": "in each clip's folder", "d_subfolder_s": "a “clips” folder next to the clip",
        "d_custom_s": "one folder for everything", "d_custom_none": "no folder picked",
        "open": "Open", "change": "Change", "choose_folder": "Where to save clips",
        "saveto": "Saving to", "beside_orig": "next to the originals", "subfolder_orig": "into “clips” next to the originals",
        "total": "Total",
        "go": "Cut and compress all ({f})", "go_copy": "Cut all ({f})", "stop": "Stop · {k}/{n}",
        "done": "Done ✨ {f} · {a} → {b}", "done_errors": "Done, with errors: {n}", "stopped": "Stopped",
        "failed": "Failed: {e}",

        "key_pending": "Start key set — now the end, O", "too_short": "The end must be after the start",
        "no_room": "No room here — new segments don't overlap old ones",
        "cleared_segs": "Segments cleared", "reset_done": "Cut reset", "applied_all": "All clips: {a} → {b}",
        "added_clips": "Clips are open — watch and cut ✂", "no_segs": "No segments yet",
        "time_bad": "Couldn't read that — type like 01:23.45 or 83.4", "clamped": "Moved the time into range",
        "edit_bar": "✎ Editing segment {n} · I — start · O — end", "edit_done": "Done",
        "pl_seg": "▶ segment {n}", "pl_next": " · C — next", "pl_cut": "▶ the cut", "pl_all": "▶ all segments",
        "loop": "↻ loop", "loading": "Loading…", "bad_file": "Couldn't open: {n}",

        "s_folder": "NVIDIA CLIPS FOLDER", "s_unset": "Not set",
        "s_set_sub": "every game subfolder is watched — new clips show up in Clips",
        "s_unset_sub": "without it, drop clips in by hand",
        "s_find": "Find it", "s_pick": "Pick…",
        "s_note": "NVIDIA App saves clips to <b>Videos\\NVIDIA\\&lt;Game&gt;</b>, the old ShadowPlay to <b>Videos\\&lt;Game&gt;</b>. "
                  "Your own path is in the <b>Alt+Z</b> overlay → recording settings.",
        "s_found": "Found: {p}", "s_notfound": "Couldn't find NVIDIA clips — pick the folder yourself",
        "s_new": "WHAT COUNTS AS NEW", "new_last": "Since the last launch", "new_day": "Last 24 hours", "new_week": "Last week",
        "s_mark": "Mark processed clips", "s_mark_s": "“✓ done” in the gallery, and they no longer count as new",
        "s_cut": "DEFAULT CUTTING", "s_merge": "Join segments into one file",
        "s_merge_s": "otherwise a separate file per segment",
        "s_naming": "FINISHED FILE NAME", "s_naming_segs": "With segments as separate files a number is added: {a}, {b}",
        "s_cache": "PREVIEW CACHE", "s_cache_t": "Frames for the gallery and the timeline", "s_cache_s": "takes {mb}",
        "s_cache_btn": "Clear", "s_cache_done": "Cache cleared",
        "p_discord": "Discord 10 MB", "p_telegram": "Telegram", "p_web": "For web", "p_archive": "Archive",
        "p_gif": "GIF preview", "own_preset": "your preset",
        "multi_tip": "Set keys: I — start, O — end ✂", "cleared": "List cleared",
        "seg_sub": "{s} s · {f} frames",
        "del_orig": "Delete the originals after saving", "del_orig_s": "they go to the Recycle Bin — you can restore them",
        "trashed": "Originals moved to the Recycle Bin: {n}",
        "folder_previews": "folder previews", "s_fprev": "Previews in Game folders",
        "s_fprev_s": "a frame of the latest clip instead of a folder icon",
        "d_q": "quality {q}", "d_size": "fit into {mb}", "d_ratio": "{r}× smaller", "d_src_res": "source resolution",
        "d_fps": "{f} fps", "d_colors": "{n} colors", "d_noaudio": "no sound",
    },
}


def t(key: str, **kw):
    s = STR[_lang].get(key, STR["en"].get(key, key))
    return s.format(**kw) if kw and isinstance(s, str) else s
