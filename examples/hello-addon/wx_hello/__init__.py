"""Smallest possible wxwx toolkit add-on. Zip this folder's contents (manifest.json + wx_hello/)
and use "Add-ons → + install from file" to try it."""
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

TEXT = {
    "ru": ("Привет из аддона ✨", "Язык: {lang} · тема: {theme}\nffmpeg: {ff}", "Показать уведомление"),
    "en": ("Hello from an add-on ✨", "Language: {lang} · theme: {theme}\nffmpeg: {ff}", "Show a toast"),
}


def create(host):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 24, 28, 24)
    title = QLabel()
    title.setObjectName("h1")
    info = QLabel()
    info.setObjectName("sub")
    btn = QPushButton()
    btn.setObjectName("accent")
    lay.addWidget(title)
    lay.addWidget(info)
    lay.addSpacing(16)
    lay.addWidget(btn)
    lay.addStretch()

    def retranslate(*_):
        h, i, b = TEXT.get(host.lang, TEXT["en"])
        title.setText(h)
        info.setText(i.format(lang=host.lang, theme=host.theme, ff=host.component("ffmpeg") or "—"))
        btn.setText(b)

    btn.clicked.connect(lambda: host.toast(TEXT.get(host.lang, TEXT["en"])[0]))

    preset = QLabel()
    preset.setObjectName("sub")
    lay.insertWidget(2, preset)
    if hasattr(host, "preset_received"):  # toolkit 1.1+
        host.preset_received.connect(lambda d: preset.setText(f"✓ preset: {d['name']} · {d['settings']}"))
    host.lang_changed.connect(retranslate)
    host.theme_changed.connect(retranslate)
    retranslate()
    return w
