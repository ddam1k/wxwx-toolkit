"""Russian / English strings of the Covers add-on."""
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


def tracks(n: int) -> str:
    return f"{n} " + (plural(n, "трек", "трека", "треков") if _lang == "ru" else plural(n, "track", "tracks", "tracks"))


def tracks_of(n: int) -> str:
    """«для 1 трека / 5 треков» — after «для»."""
    return f"{n} " + (plural(n, "трека", "треков", "треков") if _lang == "ru" else plural(n, "track", "tracks", "tracks"))


def files(n: int) -> str:
    return f"{n} " + (plural(n, "файл", "файла", "файлов") if _lang == "ru" else plural(n, "file", "files", "files"))


def fmt_size(b: float) -> str:
    if b <= 0:
        return "—"
    kb = b / 1024
    if kb < 1000:
        return f"{kb:.0f} " + ("КБ" if _lang == "ru" else "KB")
    mb = kb / 1024
    s = f"{mb:.1f}" if mb < 100 else f"{mb:.0f}"
    return (s.replace(".", ",") + " МБ") if _lang == "ru" else (s + " MB")


def short(sec: float) -> str:
    sec = max(0, int(round(sec)))
    return f"{sec // 60}:{sec % 60:02d}"


STR = {
    "ru": {
        "title": "Обложки", "sub": "Картинка и теги для MP3, M4A и FLAC",
        "add": "Добавить треки…", "clear_list": "Очистить список",
        "clear_tip": "Убрать все треки из списка — файлы останутся на месте",
        "n_tracks": "{n}", "no_cover_n": "{n} без обложки", "picked": "Выбрано {n} из {m}",
        "only_no": "Только без обложки",
        "empty_t": "Пусто", "empty_s": "Закинь сюда треки — поставим им обложки.\nMP3, M4A или FLAC.",
        "drop": "Отпусти — добавлю треки", "drop_img": "Отпусти — это будет обложка",
        "fn_tag": "имя файла", "no_artist": "без исполнителя",
        "st_dirty": "изменено", "st_saved": "✓ сохранено", "st_nocover": "без обложки", "st_err": "не читается",
        "st_from": "из «{a}»", "src_saves": "Сохранёнок",
        "added": "Добавила {n}", "added_skip": "Добавила {n}, ещё {k} уже были в списке",
        "not_audio": "Тут нужны MP3, M4A или FLAC", "cleared": "Убрала {n} из списка — файлы не трогала",
        "pick_first": "Сначала выбери треки — или кинь картинку прямо на трек",
        "pasted": "Вставила картинку из буфера ✨", "paste_pick": "Выбери треки — и вставь картинку ещё раз",
        "cover_for": "Обложка для {n} ✨", "bad_image": "Не получилось открыть картинку",
        # panel
        "b_cover": "Обложка", "pick_img": "Выбрать картинку…",
        "cv_hint": "или перетащи сюда\nCtrl+V — из буфера", "rm_cover": "Убрать обложку",
        "mixed": "разные у {n}", "drop_here": "Отпусти",
        "b_wide": "Картинка не квадратная", "fit_crop": "Обрезать", "fit_crop_s": "до квадрата по центру",
        "fit_fit": "Целиком", "fit_fit_s": "с полями по краям",
        "pad_blur": "Размытый фон", "pad_black": "Чёрные", "pad_white": "Белые",
        "wide_note": "Плееры всегда показывают обложку квадратом — решаем заранее, что с краями.",
        "b_size": "Размер обложки", "sz_600": "600 px", "sz_600_s": "легче", "sz_1000": "1000 px",
        "sz_1000_s": "как в Spotify", "sz_orig": "Как есть", "sz_orig_s": "без уменьшения",
        "size_note": "Телефоны и плееры больше ~1000 px не показывают — крупнее только раздувает каждый файл.",
        "b_tags": "Теги", "tg_title": "Название", "tg_artist": "Исполнитель", "tg_album": "Альбом", "tg_year": "Год",
        "ph_title": "как называется трек", "ph_artist": "кто", "ph_album": "необязательно", "ph_year": "2026",
        "ph_each": "у каждого своё", "ph_mixed": "разные — не трогаю",
        "guess": "Заполнить из имени файла",
        "guess_note": "«Исполнитель - Название.mp3» → разложу по полям.",
        "guessed": "Заполнила {n} из имени файла ✨", "guess_none": "Нечего разбирать",
        "b_files": "Файлы", "rename_t": "Переименовать по тегам", "rename_s": "«Исполнитель — Название» вместо track07",
        "copies_t": "Не трогать оригиналы", "copies_s": "сохранить копии в папку тулкита",
        "fn_keep": "нет тегов, оставлю", "fn_more": "и ещё {n}",
        "idle_t": "Выбери треки", "idle_s": "Кликни по треку слева — или по галочке «все», чтобы менять сразу несколько.",
        "total": "Итого", "changed": "Изменено", "save": "Сохранить в файлы", "save_n": "Сохранить {n}",
        "saving": "Сохраняю {i} из {n}…", "undo": "Отменить изменения",
        "undone": "Вернула как было: {n}", "saveto_copies": "Копии в:", "saveto_inplace": "Перезапишу теги в самих файлах · звук не трогаю",
        "done": "Готово: {n} ✨", "done_copies": "Готово: {n} — копии в папке тулкита ✨",
        "done_err": "Сохранила {n}, не получилось: {k}", "no_ffmpeg": "Нужен ffmpeg — поставь его в «Аддонах»",
        "save_err": "Не сохранилось: {e}",
        # settings
        "s_defaults": "ПО УМОЛЧАНИЮ", "s_rename_s": "«Исполнитель — Название.mp3»",
        "s_copies_s": "сохранять копии в папку тулкита", "s_from": "ИЗ «СОХРАНЁНОК»",
        "s_from_note": "У скачанного звука в «Сохранёнках» есть кнопка «Обложка» — трек сразу появится здесь.",
        "s_formats": "MP3, M4A и FLAC. Звук не перекодируется: меняются только картинка и теги.",
    },
    "en": {
        "title": "Covers", "sub": "Artwork and tags for MP3, M4A and FLAC",
        "add": "Add tracks…", "clear_list": "Clear the list",
        "clear_tip": "Remove all tracks from the list — the files stay where they are",
        "n_tracks": "{n}", "no_cover_n": "{n} without a cover", "picked": "{n} of {m} picked",
        "only_no": "Only without a cover",
        "empty_t": "Empty", "empty_s": "Drop tracks here — let's give them covers.\nMP3, M4A or FLAC.",
        "drop": "Drop — I'll add the tracks", "drop_img": "Drop — this will be the cover",
        "fn_tag": "file name", "no_artist": "no artist",
        "st_dirty": "changed", "st_saved": "✓ saved", "st_nocover": "no cover", "st_err": "can't read",
        "st_from": "from «{a}»", "src_saves": "Saves",
        "added": "Added {n}", "added_skip": "Added {n}, {k} more were already here",
        "not_audio": "This needs MP3, M4A or FLAC", "cleared": "Removed {n} from the list — the files are untouched",
        "pick_first": "Pick tracks first — or drop the picture right on a track",
        "pasted": "Pasted the picture from the clipboard ✨", "paste_pick": "Pick tracks — then paste the picture again",
        "cover_for": "Cover for {n} ✨", "bad_image": "Couldn't open the picture",
        "b_cover": "Cover", "pick_img": "Choose a picture…",
        "cv_hint": "or drag it here\nCtrl+V — from the clipboard", "rm_cover": "Remove the cover",
        "mixed": "{n} different", "drop_here": "Drop",
        "b_wide": "The picture isn't square", "fit_crop": "Crop", "fit_crop_s": "to a square, centered",
        "fit_fit": "Whole", "fit_fit_s": "with borders",
        "pad_blur": "Blurred", "pad_black": "Black", "pad_white": "White",
        "wide_note": "Players always show a cover as a square — decide now what happens at the edges.",
        "b_size": "Cover size", "sz_600": "600 px", "sz_600_s": "lighter", "sz_1000": "1000 px",
        "sz_1000_s": "like Spotify", "sz_orig": "As is", "sz_orig_s": "no downsizing",
        "size_note": "Phones and players don't show more than ~1000 px — bigger only bloats every file.",
        "b_tags": "Tags", "tg_title": "Title", "tg_artist": "Artist", "tg_album": "Album", "tg_year": "Year",
        "ph_title": "what the track is called", "ph_artist": "who", "ph_album": "optional", "ph_year": "2026",
        "ph_each": "each has its own", "ph_mixed": "different — left as is",
        "guess": "Fill in from the file name",
        "guess_note": "«Artist - Title.mp3» → split into the fields.",
        "guessed": "Filled in {n} from the file name ✨", "guess_none": "Nothing to split",
        "b_files": "Files", "rename_t": "Rename by tags", "rename_s": "«Artist — Title» instead of track07",
        "copies_t": "Keep the originals", "copies_s": "save copies to the toolkit folder",
        "fn_keep": "no tags, kept", "fn_more": "and {n} more",
        "idle_t": "Pick tracks", "idle_s": "Click a track on the left — or the «all» box to change several at once.",
        "total": "Total", "changed": "Changed", "save": "Save to files", "save_n": "Save {n}",
        "saving": "Saving {i} of {n}…", "undo": "Undo changes",
        "undone": "Back as it was: {n}", "saveto_copies": "Copies to:", "saveto_inplace": "Tags are rewritten in the files · the sound is untouched",
        "done": "Done: {n} ✨", "done_copies": "Done: {n} — copies in the toolkit folder ✨",
        "done_err": "Saved {n}, failed: {k}", "no_ffmpeg": "This needs ffmpeg — install it in «Add-ons»",
        "save_err": "Not saved: {e}",
        "s_defaults": "DEFAULTS", "s_rename_s": "«Artist — Title.mp3»",
        "s_copies_s": "save copies to the toolkit folder", "s_from": "FROM «SAVES»",
        "s_from_note": "Sound saved in «Saves» has a «Cover» button — the track shows up here right away.",
        "s_formats": "MP3, M4A and FLAC. The sound isn't re-encoded: only the picture and tags change.",
    },
}


def t(key: str, **kw):
    s = STR[_lang].get(key, STR["en"].get(key, key))
    return s.format(**kw) if kw and isinstance(s, str) else s
