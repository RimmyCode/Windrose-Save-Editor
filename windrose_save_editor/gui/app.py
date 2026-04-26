from __future__ import annotations

import sys

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from windrose_save_editor.gui.main_window import MainWindow
    from windrose_save_editor.gui.style import WINDROSE_DARK
    from windrose_save_editor import __version__
except ImportError as exc:
    print(f"GUI dependencies not installed: {exc}")
    print("Install with:  pip install 'windrose-save-editor[gui]'")
    sys.exit(1)


def run_gui() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyleSheet(WINDROSE_DARK)
    app.setApplicationName("Windrose Save Editor")
    app.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
    return app.exec()
