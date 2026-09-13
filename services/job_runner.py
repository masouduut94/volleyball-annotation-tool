"""
Shared plumbing for running a QObject worker on a background QThread with
a progress dialog. Every export/batch job in this app (YOLO export,
VideoMAE export, game-state classification) was wiring up the exact same
thread -> worker -> progress-dialog -> cleanup chain by hand; this module
does it once.

Expected worker contract (all workers in services/ already follow this):
    - a `run()` slot that does the actual work
    - a `progress` signal (optional — connected only if present)
    - a `cancel()` method (optional — only wired if the worker has it AND
      the progress dialog exposes a `cancel_button`)
    - `finished`, `cancelled`, and `error` signals

Usage:
    self._export_job = run_background_job(
        parent=self,
        worker=YOLOExportWorker(self.db, settings),
        progress_dialog=self.export_progress_dialog,
        on_finished=self._export_finished,
        on_cancelled=self._export_cancelled,
        on_error=self._export_error,
    )

The returned BackgroundJob holds the thread AND the worker alive for the
job's duration — keep a reference to it on `self` (as shown above) so
Python's GC doesn't collect them mid-job. Once finished/cancelled/error
fires, the thread and worker clean themselves up via deleteLater(); you
can drop your reference to the BackgroundJob at that point (or just leave
it — the next job overwrites the attribute).
"""

from dataclasses import dataclass

from PyQt6.QtCore import QThread


@dataclass
class BackgroundJob:
    """Keeps the thread and worker alive for as long as the job runs.
    Hold this object (not just the thread) on `self` at the call site."""
    thread: QThread
    worker: object


def run_background_job(
        parent,
        worker,
        progress_dialog,
        on_finished,
        on_cancelled,
        on_error,
        connect_progress=True
):
    """
    Move `worker` to a new QThread, wire up progress/cancel/finish/
    cancel/error, show `progress_dialog`, and start the thread.

    Args:
        on_finished:
        on_cancelled:
        on_error:
        connect_progress:
        parent: passed to QThread(parent) so it's parented into the Qt
            object tree (mirrors the existing QThread(self) calls).
        worker: an already-constructed worker instance (NOT yet moved to
            a thread — this function does that).
        progress_dialog: an ExportProgressDialog (or compatible) instance,
            already constructed. Must have `.set_progress(...)`. If it has
            a `cancel_button` and the worker has `.cancel()`, cancellation
            is wired automatically.
        on_finished / on_cancelled / on_error: callables connected to the
            worker's respective signals — these are your existing
            `_export_finished` / `_export_cancelled` / `_export_error`
            style methods, unchanged.

    Returns:
        BackgroundJob — store this on `self` to keep the thread/worker
        alive; see module docstring.
    """
    thread = QThread(parent)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)

    if connect_progress and hasattr(worker, "progress"):
        worker.progress.connect(progress_dialog.set_progress)

    if hasattr(worker, "cancel") and hasattr(progress_dialog, "cancel_button"):
        progress_dialog.cancel_button.clicked.connect(worker.cancel)

    worker.finished.connect(on_finished)
    worker.cancelled.connect(on_cancelled)
    worker.error.connect(on_error)

    worker.finished.connect(thread.quit)
    worker.cancelled.connect(thread.quit)
    worker.error.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    progress_dialog.show()
    thread.start()

    return BackgroundJob(thread=thread, worker=worker)
