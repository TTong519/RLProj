"""Background render thread that calls viewer.sync() at a target FPS."""

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class RenderThread(threading.Thread):
    """Daemon thread calling viewer.sync() at a configurable FPS.

    Args:
        viewer: Arbitrary viewer object with ``sync(state_only=True)``.
        target_fps: Desired frame-rate (e.g. 30.0).
    """

    def __init__(self, viewer: Any, target_fps: float = 30.0):
        super().__init__(daemon=True, name="SurgRLRenderThread")
        self._viewer = viewer
        self._target_interval = 1.0 / target_fps
        self._running = threading.Event()
        self._running.set()

    # ------------------------------------------------------------------ #
    #  Run loop
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Target method; called automatically when ``self.start()`` is used."""
        while self._running.is_set():
            loop_start = time.perf_counter()

            viewer = self._viewer
            if viewer is not None:
                try:
                    is_running = getattr(viewer, "is_running", lambda: True)
                    if is_running():
                        viewer.sync(state_only=True)
                except Exception:
                    pass

            elapsed = time.perf_counter() - loop_start
            sleep_time = self._target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ------------------------------------------------------------------ #
    #  Stop / cleanup
    # ------------------------------------------------------------------ #

    def stop(self) -> None:
        """Request the thread to terminate, wait (2 s max), then close the viewer."""
        self._running.clear()
        self.join(timeout=2.0)

        viewer = self._viewer
        if viewer is not None:
            try:
                viewer.close()
            except Exception:
                pass
            finally:
                self._viewer = None
