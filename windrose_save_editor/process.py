from __future__ import annotations

import sys
import threading
import time

try:
    import psutil as _psutil
except ImportError:
    _psutil = None  # type: ignore[assignment]

# Game process names to match against (name or cmdline on non-Windows).
GAME_PROCESS_NAMES: list[str] = ['R5.exe', 'Windrose.exe', 'R5-Win64-Shipping.exe']


def kill_game() -> bool:
    """Force-kill the game process.  Returns True if a process was killed.

    Requires psutil (``pip install psutil``).  Prints status messages and a
    brief wait so that RocksDB file handles are released before returning.
    """
    if _psutil is None:
        print("  [INFO] psutil not installed — can't auto-close game.")
        print("         Run:  pip install psutil  to enable this feature.")
        return False

    killed: list[str] = []
    for proc in _psutil.process_iter(['name', 'pid', 'cmdline']):
        try:
            should_kill: bool = proc.info['name'] in GAME_PROCESS_NAMES
            if not should_kill and sys.platform != 'win32' and proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if any(name in cmdline for name in GAME_PROCESS_NAMES):
                    should_kill = True

            if should_kill:
                proc.kill()
                killed.append(proc.info['name'] or 'Game Process')
        except (_psutil.NoSuchProcess, _psutil.AccessDenied):
            pass

    if killed:
        print(f"  Killed: {', '.join(killed)}")
        print("  Waiting for process to exit…", end=' ', flush=True)
        time.sleep(2)   # brief pause so RocksDB releases file handles
        print("done")
        return True
    else:
        print("  Game doesn't appear to be running.")
        return False


def _wait_for_game_exit() -> None:
    """Ask the user to quit the game normally, then block until all game
    processes are gone.

    A graceful quit via the in-game menu flushes all RocksDB databases cleanly,
    preventing partial WAL writes that can cause infinite loading screens.
    Falls back to a plain ``input()`` prompt when psutil is not available.
    Press **S** to skip the wait if the game is already closed.
    """
    if _psutil is None:
        input("  Close the game completely, then press Enter…")
        return

    def game_running() -> bool:
        for p in _psutil.process_iter(['name', 'cmdline']):
            try:
                if p.info['name'] and any(
                    name.lower() == p.info['name'].lower()
                    for name in GAME_PROCESS_NAMES
                ):
                    return True
                if sys.platform != 'win32' and p.info['cmdline']:
                    cmdline = ' '.join(p.info['cmdline']).lower()
                    if any(name.lower() in cmdline for name in GAME_PROCESS_NAMES):
                        return True
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                pass
        return False

    if not game_running():
        return   # already closed — proceed immediately

    print()
    print("  +----------------------------------------------------------+")
    print("  |  QUIT THE GAME NOW via the in-game menu (Esc -> Quit).  |")
    print("  |  Do NOT Alt+F4 or use Task Manager.                     |")
    print("  |  The editor will write your changes once it's closed.   |")
    print("  +----------------------------------------------------------+")
    print()
    print("  Waiting for game to close… (press S to skip if already closed)")
    print("  ", end='', flush=True)

    skip = threading.Event()

    def watch_key() -> None:
        if sys.platform == 'win32':
            try:
                import msvcrt
            except ImportError:
                return
            while not skip.is_set():
                if msvcrt.kbhit():
                    if msvcrt.getch().lower() == b's':
                        skip.set()
                time.sleep(0.05)
        else:
            import select
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while not skip.is_set():
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        if sys.stdin.read(1).lower() == 's':
                            skip.set()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    watcher = threading.Thread(target=watch_key, daemon=True)
    watcher.start()

    while not skip.is_set() and game_running():
        time.sleep(1)
        print('.', end='', flush=True)

    skip.set()
    if not game_running():
        time.sleep(2)
        print(" closed!")
    else:
        print(" skipped.")
    print()
