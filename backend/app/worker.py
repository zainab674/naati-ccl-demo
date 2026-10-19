"""Background worker: python -m app.worker  (run one or more; jobs are claimed with SKIP LOCKED)."""
import logging
import signal
import time

from .jobs import run_one

log = logging.getLogger("worker")
_stop = False


def _graceful(*_):
    global _stop
    _stop = True
    log.info("stopping after the current job")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)
    log.info("worker started")
    idle = 0.5
    while not _stop:
        try:
            if run_one():
                idle = 0.5
                continue
        except Exception:  # noqa: BLE001  (database restart etc.: keep the worker alive)
            log.exception("worker loop error")
        time.sleep(idle)
        idle = min(idle * 2, 5)


if __name__ == "__main__":
    main()
