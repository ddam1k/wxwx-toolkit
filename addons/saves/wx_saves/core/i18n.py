"""Russian / English strings of the Saves add-on."""
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


def fmt_size(b: float) -> str:
    if b <= 0:
        return "—"
    mb = b / 1048576
    if mb >= 1024:
        return f"{mb / 1024:.2f} " + ("ГБ" if _lang == "ru" else "GB")
    unit = "МБ" if _lang == "ru" else "MB"
    if mb >= 10:
        return f"{mb:.0f} {unit}"
    if mb >= 0.1:
        return f"{mb:.1f} {unit}".replace(".", "," if _lang == "ru" else ".")
    return f"{max(1, round(b / 1024))} " + ("КБ" if _lang == "ru" else "KB")


STR = {
    "ru": {
        "title": "Сохранёнки", "sub": "YouTube, Instagram, TikTok и сотни других сайтов",
        "open_dir": "Открыть папку", "clear_list": "Очистить список",
        "clear_tip": "Убрать скачанное из списка — файлы останутся в папке",
        "url_ph": "Вставь ссылку на видео, Reels, пост или плейлист…", "paste": "Вставить",
        "link": "ссылка", "not_link": "не ссылка", "site": "сайт", "links_n": "{n} ссылки",
        "clip_found": "В буфере ссылка с {site} — вставить?", "clip_paste": "Вставить",
        "pasted_none": "В буфере нет ссылки",
        "probing": "Смотрю, что там…",
        "views": "{n} просмотров", "vertical": "вертикальное", "subs_tag": "субтитры: {l}",
        "playlist_n": "{n} видео", "upto": "до {q}", "was": "уже качала {when}",
        "picked": "Выбрано {n} из {m}", "pick_all": "Выбрать все", "pick_none": "Снять все", "have": "уже есть",
        "idle_t": "Сначала ссылка", "idle_s": "тут появятся качество, формат и куда сохранить",
        "err_idle_t": "Сначала вход", "err_idle_s": "без входа сайт это видео не отдаёт",
        # errors
        "e_login": "{site} просит войти, чтобы показать это видео",
        "e_login_s": "Так бывает с приватными аккаунтами, постами 18+ и иногда просто так. Тулкит может взять вход "
                     "из твоего браузера — пароль никуда не уходит.",
        "e_login_btn": "Включить вход через браузер",
        "e_private": "Это видео приватное", "e_private_s": "Его видит только автор — скачать не получится.",
        "e_unavailable": "Видео недоступно", "e_unavailable_s": "Его удалили, скрыли, или в посте нет видео.",
        "e_geo": "Недоступно в твоей стране", "e_geo_s": "Сайт не показывает это видео отсюда.",
        "e_unsupported": "Этот сайт не поддерживается", "e_unsupported_s": "yt-dlp не умеет качать с этой страницы.",
        "e_network": "Нет связи с сайтом", "e_network_s": "Проверь интернет и попробуй ещё раз.",
        "e_ratelimit": "Сайт просит подождать", "e_ratelimit_s": "Слишком много запросов — попробуй через пару минут.",
        "e_cookies": "Не получилось взять вход из браузера",
        "e_cookies_s": "Закрой браузер или выбери другой в настройках. Chrome и Edge на Windows часто не отдают вход — "
                       "надёжнее Firefox.",
        "e_other": "Не получилось", "e_other_s": "yt-dlp ответил ошибкой.",
        "e_tool": "Нужен yt-dlp", "e_tool_s": "Он скачивается вместе с аддоном — загляни в «Аддоны».",
        "not_link_t": "Это не похоже на ссылку", "not_link_s": "Нужен адрес вида https://… — видео, Reels, пост или плейлист",
        "details": "подробнее", "retry": "Ещё раз",
        # panel
        "b_what": "ЧТО КАЧАТЬ", "m_video": "Видео", "m_video_s": "со звуком, одним файлом",
        "m_audio": "Только звук", "m_audio_s": "музыка, подкасты",
        "b_quality": "КАЧЕСТВО", "q_best": "Лучшее", "vert_note": "Вертикальное видео — «1080p» тут значит 1080 по ширине.",
        "b_file": "ФАЙЛ", "f_mp4o": "MP4 оригинал", "f_mp4o_s": "как отдаёт сайт",
        "f_mp4": "MP4 для всех", "f_mp4_s": "пересожму, если надо", "f_orig": "WebM / MKV", "f_orig_s": "оригинал",
        "n_mp4o_hi": "Оригинал YouTube: выше 1080p внутри MP4 лежит AV1 или VP9. Быстро и без потерь, но старые плееры "
                     "и Premiere могут не открыть.",
        "n_mp4o": "Оригинал без пересжатия — до 1080p это обычный H.264, откроется везде.",
        "n_mp4_hi": "Пересожму в H.264 после скачивания — дольше, зато откроется где угодно.",
        "n_mp4": "Тут оригинал уже H.264 — пересжимать не нужно, будет быстро.",
        "n_orig": "Как отдаёт сайт, без потерь и быстро. Но Telegram, Premiere и часть плееров WebM/MKV не любят.",
        "b_audio": "ФОРМАТ ЗВУКА", "a_mp3": "MP3", "a_mp3_s": "320 кбит/с", "a_m4a": "M4A", "a_m4a_s": "как отдаёт сайт",
        "a_opus": "Opus", "a_opus_s": "лучшее · меньше",
        "n_mp3": "Открывается везде. Обложка и название трека запишутся в файл.",
        "n_m4a": "Без перекодирования — быстро и без потерь. Открывается почти везде.",
        "n_opus": "Самый маленький и чистый, но старые плееры его не знают.",
        "b_part": "КУСОК", "part_t": "Скачать только кусок", "part_s": "качается только он, не всё видео",
        "from": "С", "to": "По", "len": "Длина",
        "b_extra": "ДОПОЛНИТЕЛЬНО", "subs_t": "Субтитры", "subs_s": "отдельным .srt рядом с видео", "subs_auto": "авто",
        "thumb_t": "Превью картинкой", "thumb_s": ".jpg рядом — удобно для референсов",
        "cover_t": "Обложка отдельно", "cover_s": "ещё и .jpg рядом, кроме встроенной",
        "b_dest": "КУДА СОХРАНЯТЬ", "tk_t": "Как в настройках тулкита", "tk_s": "общая папка «Загрузки» для всех инструментов",
        "change": "Изменить", "own_dir_s": "своя папка для «Сохранёнок»", "tk_dir_s": "меняется в Настройках → Общие",
        "total": "Итого", "go": "Скачать", "go_again": "Скачать ещё раз", "go_part": "Скачать кусок",
        "go_n": "Скачать {n}", "saveto": "Сохранится:",
        "ex_hint": "Ctrl+V в любом месте окна — и ссылка уже тут",
        # list
        "tab_now": "Сейчас", "tab_hist": "История", "search": "Найти в истории",
        "empty_t": "Скопируй ссылку — и сюда", "empty_s": "Ctrl+V в любом месте окна. Несколько ссылок сразу — тоже можно.",
        "st_wait": "В очереди", "st_pause": "Пауза · {p}%", "st_done": "Готово · {s}", "st_cancel": "Отменено",
        "stage_video": "Видео", "stage_audio": "Звук", "stage_dl": "Скачиваю", "stage_merge": "Склеиваю",
        "stage_convert": "Перевожу", "stage_recode": "Пересжимаю в H.264", "stage_finish": "Дописываю теги",
        "stage_start": "Начинаю…", "eta": "ещё {t}",
        "a_folder": "Папка", "a_send": "Сжать", "a_send_tip": "Открыть в аддоне «Видео»", "a_pause": "Пауза",
        "a_resume": "Продолжить", "a_cancel": "Отменить", "a_remove": "Убрать из списка", "a_retry": "Ещё раз",
        "h_file": "Показать в папке", "h_link": "Открыть ссылку", "h_again": "Снова", "h_again_tip": "Скачать снова",
        "h_gone": "файла нет", "h_off_t": "История выключена", "h_off_s": "Тулкит не запоминает, что и когда скачано.",
        "h_off_btn": "Включить в настройках", "h_empty_t": "Пока пусто", "h_empty_s": "Всё, что скачаешь, появится здесь — со ссылкой и датой.",
        "h_none_t": "Ничего не нашла", "h_none_s": "Ищу по названию и сайту.",
        "today_h": "Сегодня", "yesterday_h": "Вчера",
        "months": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
                   "ноября", "декабря"],
        "queued": "В очереди {n} ✨", "started": "Качаю ✨", "all_done": "Всё скачано ✨", "all_done_dir": "Всё скачано — открыла папку ✨",
        "removed_n": "Убрала из списка: {n} — файлы остались в папке", "nothing_done": "Готовых пока нет",
        "again_hint": "Ссылка снова в строке — выбери качество ✨", "sent": "Открыла в «Видео» ✨",
        "skip_dupes": "Уже скачано — пропускаю: {n}",
        # settings
        "s_engine": "ДВИЖОК", "s_ytdlp": "yt-dlp {v}", "s_ytdlp_none": "yt-dlp не установлен",
        "s_ytdlp_s": "сайты часто меняются — свежий yt-dlp качает надёжнее", "s_update": "Обновить",
        "s_updating": "Обновляю…", "s_updated": "yt-dlp обновлён: {v} ✨", "s_uptodate": "yt-dlp последней версии ✨",
        "s_update_fail": "Не получилось обновить yt-dlp",
        "s_deno": "Deno {v}", "s_deno_none": "Deno не установлен",
        "s_deno_s": "нужен YouTube — без него часть видео не скачается",
        "s_autoupd": "Обновлять yt-dlp при запуске", "s_autoupd_s": "раз в день, тихо — старая версия перестаёт качать",
        "s_login": "ВХОД ДЛЯ INSTAGRAM И ПРИВАТНОГО", "c_none": "Не нужно",
        "s_login_note": "Нужно только для приватных аккаунтов и постов 18+. Тулкит берёт вход из браузера, где ты залогинена; "
                        "пароль никуда не уходит. <b>Firefox</b> работает надёжнее всего: Chrome и Edge на Windows "
                        "шифруют вход так, что его не всегда получается прочитать.",
        "s_defaults": "ПО УМОЛЧАНИЮ", "dq_best_s": "сколько есть", "dq_1080_s": "обычно хватает", "dq_720_s": "меньше файл",
        "s_naming": "ИМЯ ФАЙЛА", "n_title": "Название", "n_author": "Автор — название", "n_date": "Дата · автор — название",
        "s_nosfx": "Суффикса тут нет: у скачанного нет оригинала, который можно перезаписать — имя берётся из названия видео.",
        "s_comfort": "УДОБСТВА", "s_clip": "Замечать ссылку в буфере",
        "s_clip_s": "скопировала ссылку и открыла тулкит — он сам предложит скачать",
        "s_dupes": "Не качать одно и то же дважды", "s_dupes_s": "в плейлистах уже скачанное не отмечаю",
        "s_par3": "Качать по 3 сразу", "s_par3_s": "иначе по 2 — интернет делится меньше",
        "s_after": "КОГДА ВСЁ СКАЧАЛОСЬ", "af_none": "Ничего", "af_folder": "Открыть папку",
        "s_hist": "ИСТОРИЯ", "s_hist_t": "Хранить историю",
        "s_hist_s": "что, откуда и когда скачано — чтобы найти ссылку или скачать снова",
        "s_keep": "Сколько хранить", "k_month": "Месяц", "k_year": "Год", "k_all": "Всегда",
        "s_hist_clear": "Очистить историю", "s_hist_n": "{n} · сами файлы не трогаю", "s_hist_cleared": "История очищена ✨",
        "records": ["запись", "записи", "записей"],
    },
    "en": {
        "title": "Saves", "sub": "YouTube, Instagram, TikTok and hundreds of other sites",
        "open_dir": "Open folder", "clear_list": "Clear list",
        "clear_tip": "Remove finished downloads from the list — the files stay in the folder",
        "url_ph": "Paste a link to a video, Reel, post or playlist…", "paste": "Paste",
        "link": "link", "not_link": "not a link", "site": "site", "links_n": "{n} links",
        "clip_found": "There's a {site} link in the clipboard — paste it?", "clip_paste": "Paste",
        "pasted_none": "No link in the clipboard",
        "probing": "Looking at it…",
        "views": "{n} views", "vertical": "vertical", "subs_tag": "subtitles: {l}",
        "playlist_n": "{n} videos", "upto": "up to {q}", "was": "saved {when}",
        "picked": "{n} of {m} picked", "pick_all": "Pick all", "pick_none": "Unpick all", "have": "already saved",
        "idle_t": "A link first", "idle_s": "quality, format and destination will show up here",
        "err_idle_t": "Log in first", "err_idle_s": "the site won't give this video without it",
        "e_login": "{site} wants you to log in to see this video",
        "e_login_s": "Happens with private accounts, 18+ posts and sometimes just because. The toolkit can use your browser's "
                     "login — your password goes nowhere.",
        "e_login_btn": "Use my browser's login",
        "e_private": "This video is private", "e_private_s": "Only its author can see it — it can't be saved.",
        "e_unavailable": "Video unavailable", "e_unavailable_s": "It was removed or hidden, or the post has no video.",
        "e_geo": "Not available in your country", "e_geo_s": "The site doesn't show this video here.",
        "e_unsupported": "This site isn't supported", "e_unsupported_s": "yt-dlp can't download from this page.",
        "e_network": "Can't reach the site", "e_network_s": "Check your connection and try again.",
        "e_ratelimit": "The site asks to wait", "e_ratelimit_s": "Too many requests — try again in a couple of minutes.",
        "e_cookies": "Couldn't read the browser's login",
        "e_cookies_s": "Close the browser or pick another one in settings. Chrome and Edge on Windows often refuse — "
                       "Firefox is more reliable.",
        "e_other": "That didn't work", "e_other_s": "yt-dlp returned an error.",
        "e_tool": "yt-dlp is needed", "e_tool_s": "It downloads with the add-on — check Add-ons.",
        "not_link_t": "That doesn't look like a link", "not_link_s": "Paste an https://… address — a video, Reel, post or playlist",
        "details": "details", "retry": "Try again",
        "b_what": "WHAT TO SAVE", "m_video": "Video", "m_video_s": "with sound, one file",
        "m_audio": "Audio only", "m_audio_s": "music, podcasts",
        "b_quality": "QUALITY", "q_best": "Best", "vert_note": "A vertical video — “1080p” here means 1080 wide.",
        "b_file": "FILE", "f_mp4o": "MP4 original", "f_mp4o_s": "as the site gives it",
        "f_mp4": "MP4 for all", "f_mp4_s": "re-encoded if needed", "f_orig": "WebM / MKV", "f_orig_s": "original",
        "n_mp4o_hi": "YouTube's original: above 1080p the MP4 holds AV1 or VP9. Fast and lossless, but old players and "
                     "Premiere may not open it.",
        "n_mp4o": "The original, untouched — up to 1080p it's plain H.264 and opens anywhere.",
        "n_mp4_hi": "I'll re-encode it to H.264 after downloading — slower, but it opens anywhere.",
        "n_mp4": "The original is H.264 already — no re-encoding, it'll be quick.",
        "n_orig": "As the site gives it, lossless and fast. But Telegram, Premiere and some players dislike WebM/MKV.",
        "b_audio": "AUDIO FORMAT", "a_mp3": "MP3", "a_mp3_s": "320 kbit/s", "a_m4a": "M4A", "a_m4a_s": "as the site gives it",
        "a_opus": "Opus", "a_opus_s": "best · smaller",
        "n_mp3": "Opens anywhere. The cover and the track title go into the file.",
        "n_m4a": "No re-encoding — fast and lossless. Opens almost anywhere.",
        "n_opus": "Smallest and cleanest, but old players don't know it.",
        "b_part": "A PIECE", "part_t": "Save only a piece", "part_s": "only that part is downloaded",
        "from": "From", "to": "To", "len": "Length",
        "b_extra": "EXTRAS", "subs_t": "Subtitles", "subs_s": "a separate .srt next to the video", "subs_auto": "auto",
        "thumb_t": "Thumbnail as an image", "thumb_s": "a .jpg next to it — handy for references",
        "cover_t": "Cover as a file", "cover_s": "a .jpg next to it, besides the embedded one",
        "b_dest": "SAVE TO", "tk_t": "Same as toolkit settings", "tk_s": "the shared Downloads folder of all tools",
        "change": "Change", "own_dir_s": "a folder just for Saves", "tk_dir_s": "set in Settings → General",
        "total": "Total", "go": "Save", "go_again": "Save again", "go_part": "Save the piece",
        "go_n": "Save {n}", "saveto": "Saves to:",
        "ex_hint": "Ctrl+V anywhere in the window — and the link is here",
        "tab_now": "Now", "tab_hist": "History", "search": "Search history",
        "empty_t": "Copy a link — and drop it here", "empty_s": "Ctrl+V anywhere in the window. Several links at once work too.",
        "st_wait": "Queued", "st_pause": "Paused · {p}%", "st_done": "Done · {s}", "st_cancel": "Cancelled",
        "stage_video": "Video", "stage_audio": "Audio", "stage_dl": "Downloading", "stage_merge": "Merging",
        "stage_convert": "Converting", "stage_recode": "Re-encoding to H.264", "stage_finish": "Writing tags",
        "stage_start": "Starting…", "eta": "{t} left",
        "a_folder": "Folder", "a_send": "Compress", "a_send_tip": "Open in the Video add-on", "a_pause": "Pause",
        "a_resume": "Resume", "a_cancel": "Cancel", "a_remove": "Remove from the list", "a_retry": "Retry",
        "h_file": "Show in folder", "h_link": "Open link", "h_again": "Again", "h_again_tip": "Save again",
        "h_gone": "file is gone", "h_off_t": "History is off", "h_off_s": "The toolkit doesn't remember what was saved.",
        "h_off_btn": "Turn on in settings", "h_empty_t": "Nothing yet", "h_empty_s": "Everything you save shows up here — with its link and date.",
        "h_none_t": "Nothing found", "h_none_s": "I search titles and sites.",
        "today_h": "Today", "yesterday_h": "Yesterday",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                   "November", "December"],
        "queued": "{n} queued ✨", "started": "Saving ✨", "all_done": "All saved ✨", "all_done_dir": "All saved — folder opened ✨",
        "removed_n": "Removed from the list: {n} — the files stay in the folder", "nothing_done": "Nothing finished yet",
        "again_hint": "The link is back — pick the quality ✨", "sent": "Opened in Video ✨",
        "skip_dupes": "Already saved — skipping: {n}",
        "s_engine": "ENGINE", "s_ytdlp": "yt-dlp {v}", "s_ytdlp_none": "yt-dlp isn't installed",
        "s_ytdlp_s": "sites change often — a fresh yt-dlp works better", "s_update": "Update",
        "s_updating": "Updating…", "s_updated": "yt-dlp updated: {v} ✨", "s_uptodate": "yt-dlp is up to date ✨",
        "s_update_fail": "Couldn't update yt-dlp",
        "s_deno": "Deno {v}", "s_deno_none": "Deno isn't installed",
        "s_deno_s": "YouTube needs it — without it some videos won't download",
        "s_autoupd": "Update yt-dlp on start", "s_autoupd_s": "once a day, quietly — an old version stops working",
        "s_login": "LOGIN FOR INSTAGRAM AND PRIVATE VIDEOS", "c_none": "Not needed",
        "s_login_note": "Only needed for private accounts and 18+ posts. The toolkit reads the login of a browser you're "
                        "logged into; your password goes nowhere. <b>Firefox</b> is the most reliable: Chrome and Edge on "
                        "Windows encrypt it so it can't always be read.",
        "s_defaults": "DEFAULTS", "dq_best_s": "whatever there is", "dq_1080_s": "usually enough", "dq_720_s": "smaller file",
        "s_naming": "FILE NAME", "n_title": "Title", "n_author": "Author — title", "n_date": "Date · author — title",
        "s_nosfx": "No suffix here: a download has no original to replace — the name comes from the video's title.",
        "s_comfort": "CONVENIENCE", "s_clip": "Notice links in the clipboard",
        "s_clip_s": "copy a link, open the toolkit — it offers to save it",
        "s_dupes": "Don't save the same thing twice", "s_dupes_s": "in playlists, already saved videos stay unpicked",
        "s_par3": "Save 3 at once", "s_par3_s": "otherwise 2 — the connection is shared less",
        "s_after": "WHEN EVERYTHING IS SAVED", "af_none": "Nothing", "af_folder": "Open the folder",
        "s_hist": "HISTORY", "s_hist_t": "Keep history",
        "s_hist_s": "what was saved, from where and when — to find a link or save it again",
        "s_keep": "Keep for", "k_month": "A month", "k_year": "A year", "k_all": "Forever",
        "s_hist_clear": "Clear history", "s_hist_n": "{n} · the files stay", "s_hist_cleared": "History cleared ✨",
        "records": ["entry", "entries", "entries"],
    },
}


def t(key: str, **kw):
    s = STR[_lang].get(key, STR["en"].get(key, key))
    return s.format(**kw) if kw and isinstance(s, str) else s
