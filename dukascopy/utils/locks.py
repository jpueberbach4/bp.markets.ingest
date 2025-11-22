# utils/locks.py
import filelock
from pathlib import Path
from datetime import date

locks = {}

LOCK_PATH = "data/locks" # Locks path

def acquire_lock(symbol: str, dt: date) -> bool:
    """
    Acquire a file-based lock for a specific symbol and date.

    Creates a `.lck` file in the `locks/` directory to prevent
    concurrent access by multiple processes. Stores the lock
    in a global dictionary for later release.

    Parameters
    ----------
    symbol : str
        Trading symbol (e.g., "EURUSD", "BTCUSD").
    dt : date
        Date for which the lock should be created.

    Returns
    -------
    bool
        True if the lock was successfully acquired.
    """
    global locks
    key = dt.strftime(f"{symbol}_%Y%m%d")
    lock_path = Path(f"{LOCK_PATH}/{key}.lck")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock = filelock.FileLock(lock_path)
    lock.acquire()

    locks[key] = {"path": lock_path, "lock": lock}
    return True


def release_lock(symbol: str, dt: date) -> bool:
    """
    Release a previously acquired lock for a symbol and date.

    Removes the `.lck` file and deletes the entry from the global locks dictionary.

    Parameters
    ----------
    symbol : str
        Trading symbol (e.g., "EURUSD", "BTCUSD").
    dt : date
        Date corresponding to the previously acquired lock.

    Returns
    -------
    bool
        True if the lock was successfully released, False otherwise.
    """
    global locks
    key = dt.strftime(f"{symbol}_%Y%m%d")
    if key in locks:
        locks[key]["lock"].release()
        locks[key]["path"].unlink(missing_ok=True)
        locks.pop(key, None)
        return True
    return False
