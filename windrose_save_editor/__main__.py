from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--gui":
        from windrose_save_editor.gui.app import run_gui
        sys.exit(run_gui())
    else:
        from windrose_save_editor.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
