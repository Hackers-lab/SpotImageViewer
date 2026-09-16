import os
import time

_DIRS = []
try:
    from core import config
    _DIRS.append(os.path.join(config.BASE_DIR, "logs"))
except ImportError:
    pass

_WORKSPACE_LOGS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
if _WORKSPACE_LOGS not in _DIRS:
    _DIRS.append(_WORKSPACE_LOGS)

_BOOT_T0 = time.perf_counter()


def get_boot_t0():
    return _BOOT_T0


def log_perf(stage: str, elapsed_ms: float = None, details: str = ""):
    """Logs high-resolution milestone timing to console and disk."""
    try:
        now = time.strftime("%H:%M:%S")
        if elapsed_ms is None:
            since_boot = (time.perf_counter() - _BOOT_T0) * 1000
            elapsed_str = f"+{since_boot:7.1f}ms"
        else:
            elapsed_str = f" {elapsed_ms:7.1f}ms"

        line = f"[{now}] [PERF] {elapsed_str} | {stage:38s} | {details}\n"
        print(line, end="", flush=True)

        for d in _DIRS:
            try:
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "startup_perf.log"), "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass
    except Exception:
        pass


def clear_log():
    try:
        header = f"=== Performance & Latency Trace Started: {time.ctime()} ===\n"
        for d in _DIRS:
            try:
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "startup_perf.log"), "w", encoding="utf-8") as f:
                    f.write(header)
            except Exception:
                pass
    except Exception:
        pass
