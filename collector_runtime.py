"""Shared durable status and advisory collection lock (macOS/Linux)."""
import contextlib
import json
import os
from pathlib import Path
import tempfile
import threading
import signal

_held = threading.local()


@contextlib.contextmanager
def interruptible(cancel):
    """Restore signal handlers after CLI use; web threads use their cancel event."""
    previous = {}
    if threading.current_thread() is threading.main_thread():
        def stop(signum, frame):
            cancel.set()
            raise KeyboardInterrupt
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, stop)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class AlreadyRunning(RuntimeError):
    pass


@contextlib.contextmanager
def run_lock(database):
    """One kernel lock per database, shared by CLI, scheduler and web callers.

    Never unlink the lock file: kernel locks release on process exit, including
    crashes. The PID is diagnostic only, never grounds to delete a 'stale' lock.
    Reentrancy is limited to the owning thread and database.
    """
    import fcntl
    path = str(Path(database).resolve()) + '.collector.lock'
    held = getattr(_held, 'paths', set())
    if path in held:
        yield
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+', encoding='utf-8') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunning('A collector already owns this database') from exc
        held.add(path)
        _held.paths = held
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()) + '\n')
            handle.flush()
            yield
        finally:
            held.remove(path)
            fcntl.flock(handle, fcntl.LOCK_UN)
