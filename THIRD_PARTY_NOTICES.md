# Third-party software

wxwx toolkit itself is MIT-licensed (see [LICENSE](LICENSE)). It uses or downloads:

| Component | License | How it is used |
|---|---|---|
| [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/) | LGPL-3.0 | bundled as separate, replaceable libraries |
| [PySide6-Frameless-Window](https://github.com/zhiyiYo/PyQt-Frameless-Window) | LGPL-3.0 | bundled as a separate Python package |
| [pywin32](https://github.com/mhammond/pywin32) | PSF | bundled |
| [FFmpeg](https://ffmpeg.org) ([BtbN builds](https://github.com/BtbN/FFmpeg-Builds)) | GPL-3.0 | **not bundled** — downloaded on demand from the official BtbN releases |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | **not bundled** — downloaded on demand from the official yt-dlp releases |

Add-ons are separate programs with their own licenses.
