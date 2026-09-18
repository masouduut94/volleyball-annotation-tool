from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QElapsedTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QPushButton,
    QProgressBar,
    QListWidget,
    QMessageBox,
)

from vb_gui.vb_annotator.ui.theme import Typography
from vb_gui.vb_annotator.services.job_runner import \
    run_background_job  # adjust path to match your project root if different


# States that count as "the ball is live" for the purposes of skipping
# dead time during batch inference. Kept as a module-level constant
# (rather than inlined in two places) so a future third "game-on" state
# is a one-line change instead of a search-and-replace.
GAME_ON_STATES = ("service", "play")


class BatchInferenceWorker(QObject):
    """
    Runs one or more AI models across an explicit list of frame numbers,
    one frame at a time.

    Takes `frame_numbers` (any sized iterable of ints — a `range` for a
    plain start..end sweep, or a plain `list` for a game-state-filtered
    subset) rather than a start/end pair, so the caller decides *which*
    frames matter and this class stays agnostic to why.

    Converted from a QThread subclass to a plain QObject so it can be run
    through run_background_job like every other worker in services/ —
    that also fixes two bugs the old QThread version had: a cancel
    request never told the dialog it had actually stopped (no signal was
    emitted, so the Run button stayed disabled forever), and an exception
    mid-loop would kill the thread silently with no error surfaced to
    the user at all.
    """

    progress = pyqtSignal(int, int)  # frames_done, frames_total
    status = pyqtSignal(str)  # human-readable "Processing frame N"
    finished = pyqtSignal(dict)  # {"frames": int, "imported": int}
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, main_window, selected_models, frame_numbers, mode="replace", parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.selected_models = selected_models
        self.frame_numbers = frame_numbers
        self.mode = mode  # Fix: "replace" or "keep"
        self._cancel_requested = False
    def cancel(self):
        self._cancel_requested = True

    def run(self):
        stats = {"frames": 0, "imported": 0, "skipped": 0}  # NEW "skipped"
        total = len(self.frame_numbers)
        try:
            for i, frame_number in enumerate(self.frame_numbers):
                if self._cancel_requested:
                    self.cancelled.emit()
                    return

                self.status.emit(f"Processing frame {frame_number}")
                self.progress.emit(i + 1, total)

                imported, skipped = self.main_window.run_batch_inference_on_frame(
                    frame_number=frame_number,
                    model_keys=self.selected_models,
                    mode=self.mode,
                )
                stats["frames"] += 1
                stats["imported"] += imported
                stats["skipped"] += skipped

            self.finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))


class BatchInferenceDialog(QDialog):
    def __init__(self, db, auto_annotator, main_window, parent=None):
        super().__init__(parent)

        self.db = db
        self.auto_annotator = auto_annotator
        self.main_window = main_window

        self._job = None  # BackgroundJob — keeps worker+thread alive while running
        self._last_status_text = ""

        # Elapsed-time tracking (QElapsedTimer for accurate monotonic
        # timing, driven by a QTimer that ticks once a second to refresh
        # the label) — created lazily in _start_elapsed_timer() so a
        # dialog that's opened but never run doesn't spin up a timer.
        self._elapsed_timer = None
        self._elapsed_refresh_timer = None

        # Game-state segments for the loaded video, restricted to the
        # "ball is live" states. Loaded once up front — this dialog is
        # short-lived (opened, used, closed), so there's no need to
        # re-query on every checkbox toggle.
        self.game_state_segments = self._load_game_on_segments()

        self.setWindowTitle("Quick-Annotate Menu")
        self.resize(560, 560)

        self.build_ui()

    # ---------------------------------------------------------
    # Game-state filtering
    # ---------------------------------------------------------

    def _load_game_on_segments(self):
        """
        Segments tagged Service or In-Play for the currently loaded
        video, or [] if no video is loaded (image sequences have no
        game-state concept) or nothing has been tagged yet.
        """
        if self.main_window.video_path is None:
            return []

        return [
            seg for seg in self.db.get_game_state_segments(self.main_window.video_path)
            if seg.state in GAME_ON_STATES
        ]

    def _current_range(self):
        """(start, end) frame numbers implied by the current Frames
        controls, without mutating anything."""
        if self.all_frames_cb.isChecked():
            if self.main_window.cap is None:
                return 0, -1
            return 0, self.main_window.total_frames - 1
        return self.start_spin.value(), self.end_spin.value()

    def _game_on_frames_in_range(self, start: int, end: int) -> list:
        """
        Sorted list of frame numbers in [start, end] that fall inside a
        Service/In-Play segment. Segments are guaranteed non-overlapping
        by DatabaseManager._trim_segments_for_range on every write, so a
        single pass per segment is enough — no de-duplication needed.
        """
        if start > end:
            return []

        frames = []
        for seg in self.game_state_segments:
            s = max(seg.start_frame, start)
            e = min(seg.end_frame, end)
            if s <= e:
                frames.extend(range(s, e + 1))

        frames.sort()
        return frames

    def update_frame_estimate(self):
        """
        Keeps the game-state checkbox's helper label in sync with
        whatever the Frames controls currently say, so the user always
        sees an accurate frame count *before* clicking Run rather than
        discovering it mid-job.
        """
        if not self.game_state_segments:
            self.game_on_checkbox.setEnabled(False)
            self.game_on_checkbox.setChecked(False)
            if self.main_window.video_path is None:
                self.game_state_info_label.setText(
                    "Game-state filtering isn't available for an image sequence."
                )
            else:
                self.game_state_info_label.setText(
                    "No Service/In-Play tags found for this video — "
                    "inference will run on every frame in the selected range."
                )
            return

        self.game_on_checkbox.setEnabled(True)

        start, end = self._current_range()
        total_in_range = max(0, end - start + 1)
        game_on_count = len(self._game_on_frames_in_range(start, end))

        if self.game_on_checkbox.isChecked():
            self.game_state_info_label.setText(
                f"Will process {game_on_count} of {total_in_range} frame(s) in range "
                f"(Service/In-Play only) — skipping {total_in_range - game_on_count} dead-time frame(s)."
            )
        else:
            self.game_state_info_label.setText(
                f"{game_on_count} of {total_in_range} frame(s) in range are tagged "
                f"Service/In-Play. Check the box above to process only those and save time."
            )

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def build_ui(self):
        layout = QVBoxLayout(self)

        # --------------------------------------------------
        # Use models
        # --------------------------------------------------

        title = QLabel("Models")
        layout.addWidget(title)

        self.ball_cb = QCheckBox("Ball segmentation")
        self.actions_cb = QCheckBox("Actions detection")
        self.players_cb = QCheckBox("Players detection")

        layout.addWidget(self.ball_cb)
        layout.addWidget(self.actions_cb)
        layout.addWidget(self.players_cb)

        # --------------------------------------------------
        # Target job
        # --------------------------------------------------
        layout.addSpacing(10)

        layer_title = QLabel("Target layers")
        layout.addWidget(layer_title)

        layout.addWidget(QLabel("Players model → Players layer"))
        layout.addWidget(QLabel("Ball model → Ball layer"))
        layout.addWidget(QLabel("Actions model → Actions layer"))

        # --------------------------------------------------
        # Frames
        # --------------------------------------------------

        layout.addSpacing(10)

        frames_title = QLabel("Frames")
        layout.addWidget(frames_title)

        self.all_frames_cb = QCheckBox("Annotate all frames")
        self.all_frames_cb.setChecked(True)
        self.all_frames_cb.toggled.connect(self.on_all_frames_changed)
        layout.addWidget(self.all_frames_cb)

        frame_row = QHBoxLayout()

        frame_row.addWidget(QLabel("From"))
        self.start_spin = QSpinBox()
        self.start_spin.setMaximum(10_000_000)
        self.start_spin.valueChanged.connect(self.update_frame_estimate)
        frame_row.addWidget(self.start_spin)

        frame_row.addWidget(QLabel("To"))
        self.end_spin = QSpinBox()
        self.end_spin.setMaximum(10_000_000)
        self.end_spin.valueChanged.connect(self.update_frame_estimate)
        frame_row.addWidget(self.end_spin)

        layout.addLayout(frame_row)

        # --------------------------------------------------
        # Game-state filtering — NEW
        # --------------------------------------------------

        layout.addSpacing(10)

        gs_title = QLabel("Game State Filtering")
        layout.addWidget(gs_title)

        self.game_on_checkbox = QCheckBox("Only run on Service / In-Play frames")
        # Default OFF: this restricts *what* gets annotated, so an
        # explicit opt-in is safer than silently skipping frames the
        # user expected to be processed. update_frame_estimate() makes
        # the savings obvious so opting in is an easy, informed choice.
        self.game_on_checkbox.setChecked(False)
        self.game_on_checkbox.toggled.connect(self.update_frame_estimate)
        layout.addWidget(self.game_on_checkbox)

        self.game_state_info_label = QLabel("")
        self.game_state_info_label.setWordWrap(True)
        self.game_state_info_label.setStyleSheet("color: #9096A3; font-size: 11px;")
        layout.addWidget(self.game_state_info_label)

        # --------------------------------------------------
        # Progress
        # --------------------------------------------------

        layout.addSpacing(10)

        progress_title = QLabel("Progress")
        layout.addWidget(progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Ready")
        layout.addWidget(self.progress_label)

        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        layout.addWidget(self.elapsed_label)

        # --------------------------------------------------
        # Buttons
        # --------------------------------------------------

        layout.addStretch()

        button_row = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.on_cancel)

        self.run_btn = QPushButton("Run inference")
        self.run_btn.clicked.connect(self.start_inference)

        button_row.addStretch()
        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.run_btn)

        layout.addLayout(button_row)

        self.initialize_frame_range()
        self.update_frame_estimate()

    # ---------------------------------------------------------
    # Frames
    # ---------------------------------------------------------

    def initialize_frame_range(self):
        if self.main_window.cap is not None:
            total = self.main_window.total_frames
            self.start_spin.setValue(0)
            self.end_spin.setValue(max(0, total - 1))

    def on_all_frames_changed(self, checked):
        self.start_spin.setEnabled(not checked)
        self.end_spin.setEnabled(not checked)
        self.update_frame_estimate()

    # ---------------------------------------------------------
    # Elapsed time
    # ---------------------------------------------------------

    def _start_elapsed_timer(self):
        self._elapsed_timer = QElapsedTimer()
        self._elapsed_timer.start()

        if self._elapsed_refresh_timer is None:
            self._elapsed_refresh_timer = QTimer(self)
            self._elapsed_refresh_timer.setInterval(1000)
            self._elapsed_refresh_timer.timeout.connect(self._update_elapsed_label)

        self._elapsed_refresh_timer.start()
        self._update_elapsed_label()

    def _update_elapsed_label(self):
        if self._elapsed_timer is None:
            return
        total_seconds = self._elapsed_timer.elapsed() // 1000
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_label.setText(f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _stop_elapsed_timer(self):
        # Freeze on the final duration rather than leaving it ticking
        # after the job is done/cancelled/errored.
        self._update_elapsed_label()
        if self._elapsed_refresh_timer is not None:
            self._elapsed_refresh_timer.stop()

    # ---------------------------------------------------------
    # Inference
    # ---------------------------------------------------------

    def selected_models(self):
        models = []
        if self.ball_cb.isChecked():
            models.append("ball")
        if self.actions_cb.isChecked():
            models.append("actions")
        if self.players_cb.isChecked():
            models.append("players")
        return models

    def start_inference(self):
        models = self.selected_models()
        if not models:
            QMessageBox.warning(self, "No model selected", "Please select at least one model.")
            return

        start, end = self._current_range()
        if start > end:
            QMessageBox.warning(self, "Invalid frame range",
                                "The start frame must be less than or equal to the end frame.")
            return

        # Fix: ask once how to handle frames that already have unconfirmed
        # AI annotations.
        # Confirmed / human-drawn annotations are never touched by either choice.
        box = QMessageBox(self)
        box.setWindowTitle("Existing AI Annotations")
        box.setText(
            "Some frames in this range may already have AI-generated "
            "annotations waiting for review.\n\n"
            "Replace them with the new results, or leave those frames "
            "untouched and only fill in frames that have nothing yet?"
        )
        replace_btn = box.addButton("Replace", QMessageBox.ButtonRole.AcceptRole)
        keep_btn = box.addButton("Keep Existing", QMessageBox.ButtonRole.RejectRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked not in (replace_btn, keep_btn):
            return
        mode = "replace" if clicked is replace_btn else "keep"

        if self.game_on_checkbox.isChecked() and self.game_state_segments:
            frame_numbers = self._game_on_frames_in_range(start, end)
            if not frame_numbers:
                QMessageBox.information(self, "No Matching Frames",
                                        "No Service/In-Play frames were found in the selected range.")
                return
        else:
            frame_numbers = range(start, end + 1)

        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting…")
        self._last_status_text = ""
        self._start_elapsed_timer()

        worker = BatchInferenceWorker(self.main_window, models, frame_numbers, mode=mode)  # NEW mode arg
        worker.progress.connect(self.update_progress)
        worker.status.connect(self._on_worker_status)

        self._job = run_background_job(
            parent=self, worker=worker, progress_dialog=self,
            on_finished=self.on_finished, on_cancelled=self.on_cancelled,
            on_error=self.on_error, connect_progress=False,
        )

    def _on_worker_status(self, text):
        self._last_status_text = text

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

        remaining = max(total - current, 0)
        frame_text = self._last_status_text or f"Processing frame {current}"
        self.progress_label.setText(
            f"{frame_text}  ({current}/{total} — {remaining} remaining)"
        )

    def on_finished(self, stats):
        self.run_btn.setEnabled(True)
        self._job = None
        self._stop_elapsed_timer()

        msg = (
            f"Frames processed: {stats['frames']}\n"
            f"Annotations imported: {stats['imported']}"
        )
        if stats["skipped"]:
            msg += f"\nSkipped (already had unreviewed AI annotations or exact duplicates): {stats['skipped']}"

        QMessageBox.information(self, "Batch inference complete", msg)
        self.main_window.load_annotations()

        self.main_window.load_annotations()

    def on_cancelled(self):
        """NEW — the old version never told the dialog a cancel actually
        completed, so the Run button stayed disabled and the progress
        label stayed frozen mid-run until the dialog was closed."""
        self.run_btn.setEnabled(True)
        self._job = None
        self._stop_elapsed_timer()
        self.progress_label.setText("Cancelled.")

    def on_error(self, message):
        """NEW — the old version had no error signal at all, so an
        exception partway through the frame loop killed the thread
        silently with no feedback to the user."""
        self.run_btn.setEnabled(True)
        self._job = None
        self._stop_elapsed_timer()
        self.progress_label.setText("Failed.")
        QMessageBox.critical(self, "Batch Inference Failed", f"Could not complete batch inference:\n\n{message}")

    def on_cancel(self):
        if self._job is not None and self._job.thread.isRunning():
            self._job.worker.cancel()
        else:
            self.reject()