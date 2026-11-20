# Changelog

Each section becomes the release notes and the "what's new" tooltip in the update bar.

## 1.3.1
- Ready for the new Saves add-on: the toolkit can download Deno (yt-dlp needs it for YouTube), and add-ons can hand files to each other — e.g. «Compress» on a finished download opens it in Video.
- Add-ons share one set of widgets, so the look and the «fewer hints» switch behave the same everywhere.
- Готовность к новому аддону «Сохранёнки»: тулкит умеет скачивать Deno (он нужен yt-dlp для YouTube), а аддоны могут передавать друг другу файлы — например, «Сжать» у готовой загрузки открывает её в «Видео».
- У аддонов теперь общий набор виджетов, поэтому вид и переключатель «меньше подсказок» везде работают одинаково.

## 1.3.0
- Fewer hints: one switch in Settings → General hides the explanations under options, in the toolkit and in every add-on.
- Finished file suffix: `_wx`, `_trim` or your own, set once for the whole toolkit. Each add-on can keep it or use its own (Video got its own Settings tab for that).
- Everything in one folder: settings, add-ons and ffmpeg now live next to the program in `data`. The installer no longer needs admin rights and installs for your user (or wherever you pick). Old data is moved over on first start; uninstalling asks whether to delete it.
- The program starts in the language picked in the installer (or the Windows language for the portable version).
- Меньше подсказок: один переключатель в «Настройки → Общие» убирает пояснения под пунктами — в тулките и во всех аддонах.
- Суффикс готовых файлов: `_wx`, `_trim` или свой — один на весь тулкит. В каждом аддоне можно оставить его или поставить свой (у «Видео» ради этого появилась вкладка в настройках).
- Всё в одной папке: настройки, аддоны и ffmpeg теперь лежат рядом с программой в `data`. Установщику больше не нужны права администратора — ставится для тебя (или куда выберешь). Старые данные переносятся при первом запуске, а при удалении тулкит спросит, удалять ли их.
- Программа запускается на языке, выбранном в установщике (portable-версия — на языке Windows).

## 1.2.0
- "Check for updates" button in Add-ons, plus a quiet re-check every 30 minutes — no restart needed to see new versions.
- Add-ons update on the fly: the page reloads in place. If an add-on is busy (say, compressing), a silent update waits until it finishes.
- Add-ons can have their own tab in Settings.
- Video and audio playback built in (for the upcoming Clips add-on).
- Our add-ons now live in the toolkit repo and update on their own, without a new toolkit version.
- Кнопка «Проверить обновления» в «Аддонах» и тихая проверка раз в 30 минут — перезапускать ничего не нужно.
- Аддоны обновляются на лету: страница перезагружается на месте. Если аддон занят (например, сжимает), тихое обновление подождёт, пока он закончит.
- У аддонов может быть своя вкладка в настройках.
- Встроенное воспроизведение видео и звука (для будущего аддона «Клипы»).
- Наши аддоны теперь живут в репозитории тулкита и обновляются сами, без новой версии тулкита.

## 1.1.0
- Folders in Settings: one place for finished files and downloads, shared by all tools.
- `.wtp` presets: double-click a preset file (or drop it on the window) and the toolkit opens the right add-on with it.
- Opening the toolkit again brings the running window to the front instead of starting a second copy.
- Папки в настройках: одно место для готовых файлов и загрузок, общее для всех инструментов.
- Пресеты `.wtp`: двойной клик по файлу пресета (или перетащить в окно) — тулкит откроет нужный аддон с этим пресетом.
- Повторный запуск тулкита выводит уже открытое окно вперёд вместо второй копии.

## 1.0.1
- One combined title bar, like VS Code: logo, name, theme toggle and our own window buttons. Moving, resizing, Win+arrows and double-click to maximize still work.
- Одна общая полоса заголовка, как у VS Code: лого, название, переключатель темы и свои кнопки окна. Перетаскивание, растягивание, Win+стрелки и двойной клик работают как раньше.

## 1.0.0
- First release: add-on store with auto-updates, shared ffmpeg / yt-dlp, black & white themes, Russian / English, self-update.
- Первый релиз: магазин аддонов с автообновлением, общие ffmpeg / yt-dlp, чёрная и белая темы, русский / английский, самообновление.
