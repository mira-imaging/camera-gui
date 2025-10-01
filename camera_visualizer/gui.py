import sys
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QLineEdit,
    QFormLayout,
    QComboBox,
    QSlider,
    QHBoxLayout,
    QCheckBox,
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

from camera_visualizer.camera_interface.mock_interface import (
    Camera,
    CameraEnum,
    camera,
)
from camera_visualizer.serializer import SaveFormatEnum


EXPOSURE_DEFAULT_RANGE = (1_000, 1_000_000, 100)
EXPOSURE_DEFAULT_VALUE = 10_000
FPS_DEFAULT_RANGE = (1, 500, 1)
FPS_DEFAULT_VALUE = 30


@dataclass
class GuiState:
    selected_camera: CameraEnum = CameraEnum.MOCK
    exposure: int = EXPOSURE_DEFAULT_VALUE
    fps: float = FPS_DEFAULT_VALUE
    frame_counter: int = 0
    dropped_frames: int = 0
    recording: bool = False
    running: bool = False
    paused: bool = False
    estimating_exposure: bool = False
    exposure_tries: int = 0
    recording_format: SaveFormatEnum = SaveFormatEnum.ENVI
    filename_stem: str = "frame"


class VideoPlayer(QWidget):
    camera: Camera
    state: GuiState
    current_image: QPixmap | None

    def __init__(
        self,
        fps: float,
        camera_id: CameraEnum | str = CameraEnum.MOCK,
    ):
        super().__init__()
        self.camera = camera(camera_id=camera_id)
        self.state = GuiState(selected_camera=camera_id, fps=fps)
        self.current_image = None

        self.setWindowTitle("Camera Video Player")
        self.label = QLabel("")

        self.play_button = QPushButton("")
        self.play_button.clicked.connect(self.toggle_running)
        self.pause_button = QPushButton("")
        self.pause_button.clicked.connect(self.toggle_pausing)

        self.camera_select = QComboBox()
        self.camera_select.addItems([e.value for e in CameraEnum])
        self.camera_select.currentIndexChanged.connect(self.choose_camera)
        self.camera_select.setCurrentText(self.state.selected_camera)
        camera_select = QFormLayout()
        camera_select.addRow("Camera:", self.camera_select)

        play_layout = QHBoxLayout()
        play_layout.addWidget(self.play_button)
        play_layout.addWidget(self.pause_button)
        play_layout.addLayout(camera_select)
        
        self.view_button = QPushButton("Toggle view")
        self.view_button.clicked.connect(self.toggle_view)

        self.bit_depth_button = QPushButton(f"Toggle bit depth: {self.camera.bit_depth()}")
        self.bit_depth_button.clicked.connect(self.toggle_bit_depth)

        view_layout = QHBoxLayout()
        view_layout.addWidget(self.view_button)
        view_layout.addWidget(self.bit_depth_button)

        # FPS and Exposure Inputs
        self.fps_input = QLineEdit("")
        self.fps_input.editingFinished.connect(self.update_fps_from_input)

        self.fps_slider = QSlider(Qt.Horizontal)
        self.fps_slider.valueChanged.connect(lambda value: self.fps_input.setText(f"{value:d}"))
        self.fps_slider.sliderReleased.connect(self.update_fps_from_slider)

        self.init_fps_slider(
            slider=self.fps_slider,
            text_input=self.fps_input,
            value=int(self.state.fps),
        )

        layout_fps = QHBoxLayout()
        layout_fps.addWidget(self.fps_slider)
        layout_fps.addWidget(self.fps_input)

        self.exposure_input = QLineEdit(f"{self.camera.exposure():d}")
        self.exposure_input.editingFinished.connect(self.update_exposure_from_input)

        self.exposure_slider = QSlider(Qt.Horizontal)  # Or Qt.Vertical
        self.exposure_slider.setValue(EXPOSURE_DEFAULT_VALUE)
        self.exposure_slider.valueChanged.connect(lambda value: self.exposure_input.setText(f"{value}"))
        self.exposure_slider.sliderReleased.connect(self.update_exposure_from_slider)

        self.init_exposure_slider(
            slider=self.exposure_slider,
            text_input=self.exposure_input,
            value=EXPOSURE_DEFAULT_VALUE,
        )

        self.exposure_button = QPushButton("Estimate Exposure Time")
        self.exposure_button.clicked.connect(self.estimate_exposure)

        self.exposure_checkbox = QCheckBox("Auto")
        self.exposure_checkbox.toggled.connect(self.toggle_auto_exposure)

        layout_exposure = QHBoxLayout()
        layout_exposure.addWidget(self.exposure_slider)
        layout_exposure.addWidget(self.exposure_input)
        layout_exposure.addWidget(self.exposure_button)
        layout_exposure.addWidget(self.exposure_checkbox)

        self.filename_input = QLineEdit(self.state.filename_stem)

        self.recording_label = QLabel("")
        self.recording_label.setStyleSheet("color: red; font-weight: bold")
        self.open_label = QLabel("")
        self.open_label.setStyleSheet("color: red; font-weight: bold")
        self.frame_label = QLabel("")
        self.frame_label.setStyleSheet("color: red; font-weight: bold")
        warning_layout = QHBoxLayout()
        warning_layout.addWidget(self.recording_label)
        warning_layout.addWidget(self.open_label)
        warning_layout.addWidget(self.frame_label)

        self.record_button = QPushButton("Record")
        self.record_button.clicked.connect(self.toggle_recording)

        self.record_format = QComboBox()
        self.record_format.addItems([e.value for e in SaveFormatEnum])
        self.record_format.currentIndexChanged.connect(self.set_record_format)
        self.record_format.setCurrentText(self.state.recording_format)
        record_format = QFormLayout()
        record_format.addRow("Format:", self.record_format)
        record_filename = QFormLayout()
        record_filename.addRow("Filename:", self.filename_input)

        record_layout = QHBoxLayout()
        record_layout.addWidget(self.record_button)
        record_layout.addLayout(record_format)
        record_layout.addLayout(record_filename)

        # Layouts
        control_layout = QFormLayout()
        control_layout.addRow("FPS:", layout_fps)
        control_layout.addRow("Exposure (μs):", layout_exposure)

        layout = QVBoxLayout()
        layout.addWidget(self.label, stretch=40)
        layout.addLayout(play_layout, stretch=0)
        layout.addLayout(view_layout, stretch=0)
        layout.addLayout(warning_layout, stretch=0)
        layout.addLayout(record_layout, stretch=0)
        layout.addLayout(control_layout, stretch=0)
        layout.addStretch()
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(int(1000 // self.state.fps))

        self.disable_running()

        self.setStyleSheet(
            """
            QLabel, QPushButton, QSlider, QComboBox, QLabel, QLineEdit, QCheckBox {
                font-size: 14pt;
            }
            QPushButton, QComboBox, QFormLayout, QLabel, QLineEdit, QCheckBox {
                min-height: 48px;
            }
            QSlider {
                min-height: 40px;
            }
            
            QSlider::groove:horizontal {
                height: 16px;
                background: #bbb;
                border-radius: 8px;
            }
        
            QSlider::handle:horizontal {
                background: #444;
                border: 1px solid #666;
                width: 24px;
                height: 24px;
                margin: -5px 0;  /* centers the handle on the groove */
                border-radius: 12px;
            }
            """
        )
        self.initial_scale()

    def initial_scale(self) -> None:
        screen = QApplication.primaryScreen()
        size = screen.availableGeometry()
        aspect_ratio = size.width() / size.height()
        if aspect_ratio >= 1:  # Landscape
            initial_w = int(0.4 * size.width())
            initial_h = int(0.9 * size.height())
        else: # Portrait
            initial_w = int(0.9 * size.width())
            initial_h = int(0.9 * size.width())

        self.label.setFixedHeight(int(0.6 * initial_h))
        self.resize(initial_w, initial_h)

    def toggle_running(self) -> None:
        self.disable_running() if self.state.running else self.enable_running()

    def enable_running(self):
        try:
            self.camera = camera(camera_id=self.state.selected_camera)
            self.camera.open(fps=self.state.fps)
            self.open_label.setText("")
        except (self.camera.exception_type(), ModuleNotFoundError) as e:
            print(e)
            self.open_label.setText("Device unavailable.")
            return
        self.state.running = True
        scale_ratio = self.camera.shape()[1] / self.camera.shape()[0]
        self.label.setFixedWidth(int(scale_ratio * self.label.height()))

        self.fps_input.setEnabled(False)
        self.fps_slider.setEnabled(False)
        self.camera_select.setEnabled(False)
        self.init_auto_exposure()
        self.setup_fps_slider(fps_val=self.state.fps)
        exposure = self.camera.exposure()
        self.setup_exposure_slider(exposure_val=exposure)
        self.bit_depth_button.setText(f"Toggle bit depth: {self.camera.bit_depth()}")
        self.disable_pausing()
        self.play_button.setText("Stop")

    def disable_running(self):
        if self.state.running:
            self.camera.close()
        self.state.running = False
        self.fps_input.setEnabled(True)
        self.fps_slider.setEnabled(True)
        self.camera_select.setEnabled(True)
        self.exposure_input.setEnabled(False)
        self.exposure_slider.setEnabled(False)
        self.exposure_button.setEnabled(False)
        self.exposure_checkbox.setEnabled(False)
        self.init_fps_slider(
            slider=self.fps_slider,
            text_input=self.fps_input,
            value=int(self.state.fps),
        )
        self.init_exposure_slider(
            slider=self.exposure_slider,
            text_input=self.exposure_input,
            value=self.exposure_slider.value(),
        )
        self.disable_pausing()
        self.play_button.setText("Play")
        self.label.setText("Waiting for image...")

    def toggle_pausing(self) -> None:
        self.disable_pausing() if self.state.paused else self.enable_pausing()

    def enable_pausing(self) -> None:
        if not self.state.running:
            return
        self.state.paused = True
        self.pause_button.setText("Resume")

    def disable_pausing(self) -> None:
        self.state.paused = False
        self.pause_button.setText("Pause")

    def toggle_view(self) -> None:
        if (not self.state.running) or self.state.paused:
            return
        self.camera.toggle_view()
        
    def toggle_bit_depth(self):
        if (not self.state.running) or self.state.paused or self.state.recording:
            return
        self.camera.toggle_bit_depth()
        self.bit_depth_button.setText(f"Toggle bit depth: {self.camera.bit_depth()}")

    def toggle_recording(self):
        if (not self.state.running) or self.state.paused:
            return
        self.state.recording = not self.state.recording
        if self.state.recording:
            self.record_format.setEnabled(False)
            self.filename_input.setEnabled(False)
            self.state.frame_counter = 0
            self.record_button.setText("Stop Recording")
            self.recording_label.setText("RECORDING")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.camera.set_save_subfolder(subfolder=timestamp)
        else:
            self.record_format.setEnabled(True)
            self.filename_input.setEnabled(True)
            self.record_button.setText("Record")
            self.recording_label.setText("")

    def init_auto_exposure(self):
        self.exposure_checkbox.setEnabled(True)
        if self.camera.is_auto_exposure():
            self.exposure_input.setEnabled(False)
            self.exposure_slider.setEnabled(False)
            self.exposure_button.setEnabled(False)
            self.exposure_checkbox.blockSignals(True)
            self.exposure_checkbox.setChecked(True)
            self.exposure_checkbox.blockSignals(False)
        else:
            self.exposure_input.setEnabled(True)
            self.exposure_slider.setEnabled(True)
            self.exposure_button.setEnabled(True)
            self.exposure_checkbox.blockSignals(True)
            self.exposure_checkbox.setChecked(False)
            self.exposure_checkbox.blockSignals(False)

    def toggle_auto_exposure(self):
        self.camera.toggle_auto_exposure()
        self.init_auto_exposure()

    def estimate_exposure(self):
        if (not self.state.running) or self.state.paused or self.state.estimating_exposure:
            return
        self.state.estimating_exposure = True
        self.state.exposure_tries = 0
        self.exposure_button.setText("Estimating exposure time...")
        self.exposure_input.setEnabled(False)
        self.exposure_slider.setEnabled(False)
        self.exposure_checkbox.setEnabled(False)
        self.camera.init_exposure(max_exposure=int(1_000_000 // self.state.fps))

    def set_record_format(self):
        selected_value = self.record_format.currentText()
        self.state.recording_format = SaveFormatEnum(selected_value)

    def choose_camera(self):
        if self.state.running:
            return
        selected_value = self.camera_select.currentText()
        self.state.selected_camera = CameraEnum(selected_value)

    @staticmethod
    def numpy_to_pixmap_format(arr: np.ndarray) -> QImage:
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        if arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1):  # Grayscale
            qimg = QImage(
                arr.data,
                arr.shape[1],
                arr.shape[0],
                arr.shape[1],
                QImage.Format_Grayscale8,
            )
        elif arr.ndim == 3 and arr.shape[2] >= 3:  # RGB
            arr = arr[..., :3]
            qimg = QImage(
                arr.tobytes(),  # <- use bytes, not memoryview
                arr.shape[1],
                arr.shape[0],
                arr.shape[1] * arr.shape[2],
                QImage.Format_RGB888,
            )
        else:
            ValueError("Image not displayable")
        return qimg.copy()


    def update_frame(self):
        if (not self.state.running) or self.state.paused:
            return
        if self.state.estimating_exposure:
            exposure = self.camera.adjust_exposure()
            self.update_exposure(exposure_val=exposure)
        try:
            frame_save, frame_view = self.camera.get_frame(fps=self.state.fps)
            self.state.dropped_frames = 0
            self.frame_label.setText("")
        except self.camera.exception_type():
            frame_save, frame_view = None, None
            self.state.dropped_frames += 1
            date = datetime.now().isoformat()
            self.frame_label.setText(f"[{date}]: Dropped frame")
        if self.state.dropped_frames >= 3:
            self.disable_running()
        if frame_view is not None:
            self.current_image = self.numpy_to_pixmap_format(arr=frame_view)
            pixmap = QPixmap.fromImage(self.current_image)
            self.label.setPixmap(pixmap.scaled(
                self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        if self.state.recording and frame_save is not None:
            filename = f"frame_{self.state.frame_counter:04d}"
            self.camera.save_frame(
                filename_stem=filename,
                frame=frame_save,
                fmt=self.state.recording_format,
            )
            self.state.frame_counter += 1
        if self.state.estimating_exposure and frame_save is not None:
            converged = self.camera.check_exposure(frame=frame_save)
            self.state.estimating_exposure = not converged
            self.state.exposure_tries += 1
            if self.state.exposure_tries >=50:
                self.state.estimating_exposure = False
            if not self.state.estimating_exposure:
                self.state.exposure_tries = 0
                self.exposure_input.setEnabled(True)
                self.exposure_slider.setEnabled(True)
                self.exposure_checkbox.setEnabled(True)
                self.exposure_checkbox.blockSignals(True)
                self.exposure_checkbox.setChecked(False)
                self.exposure_checkbox.blockSignals(False)
                self.exposure_button.setText("Estimate Exposure Time")

    def update_fps_from_input(self):
        fps_val = self.fps_input.text()
        self.update_fps(fps_val=fps_val)

    def update_fps_from_slider(self):
        self.update_fps(fps_val=self.fps_slider.value())

    def update_fps(self, fps_val: float):
        try:
            fps_val = int(fps_val)
            if fps_val < self.fps_slider.minimum():
                fps_val = self.fps_slider.minimum()
            if fps_val > self.fps_slider.maximum():
                fps_val = self.fps_slider.maximum()
            if float(fps_val) != self.state.fps:
                self.state.fps = float(fps_val)
                self.timer.setInterval(int(1_000 // self.state.fps))
            self.fps_slider.setValue(int(fps_val))
            self.fps_input.setText(f"{fps_val:d}")
        except (ValueError, TypeError):
            self.fps_slider.setValue(int(self.state.fps))
            self.fps_input.setText(f"{int(self.state.fps):d}")

    def update_exposure_from_input(self):
        self.update_exposure(exposure_val=self.exposure_input.text())

    def update_exposure_from_slider(self):
        self.update_exposure(exposure_val=self.exposure_slider.value())

    @staticmethod
    def init_exposure_slider(slider: QSlider, text_input: QLineEdit,value: int):
        slider.setRange(EXPOSURE_DEFAULT_RANGE[0], EXPOSURE_DEFAULT_RANGE[1])
        slider.setSingleStep(EXPOSURE_DEFAULT_RANGE[2])
        slider.setPageStep(EXPOSURE_DEFAULT_RANGE[2])
        if value < EXPOSURE_DEFAULT_RANGE[0]:
            value = EXPOSURE_DEFAULT_RANGE[0]
        if value > EXPOSURE_DEFAULT_RANGE[1]:
            value = EXPOSURE_DEFAULT_RANGE[1]
        value = value - value % EXPOSURE_DEFAULT_RANGE[2]
        slider.setValue(value)
        text_input.setText(f"{value:d}")

    @staticmethod
    def init_fps_slider(slider: QSlider, text_input: QLineEdit, value: int):
        slider.setRange(FPS_DEFAULT_RANGE[0], FPS_DEFAULT_RANGE[1])
        slider.setSingleStep(FPS_DEFAULT_RANGE[2])
        slider.setPageStep(FPS_DEFAULT_RANGE[2])
        if value < FPS_DEFAULT_RANGE[0]:
            value = FPS_DEFAULT_RANGE[0]
        if value > FPS_DEFAULT_RANGE[1]:
            value = FPS_DEFAULT_RANGE[1]
        value = value - value % FPS_DEFAULT_RANGE[2]
        value = int(value)
        slider.setValue(value)
        text_input.setText(f"{value:d}")
        # No need to update self.state.fps here, since it is a mock value

    def update_exposure(self, exposure_val: int):
        if (not self.state.running) or self.state.paused:
            return
        try:
            exposure_val = int(exposure_val)
            if exposure_val > self.exposure_slider.maximum():
                exposure_val = self.exposure_slider.maximum()
            if exposure_val < self.exposure_slider.minimum():
                exposure_val = self.exposure_slider.minimum()
            exposure_val = exposure_val - exposure_val % self.camera.exposure_range()[2]
            if exposure_val != self.state.exposure:
                self.camera.set_exposure(exposure_val)
            self.exposure_input.setText(f"{exposure_val}")
            self.exposure_slider.setValue(exposure_val)
        except (ValueError, self.camera.exception_type()):
            exposure_val = self.camera.exposure()
            self.exposure_input.setText(f"{exposure_val}")
            self.exposure_slider.setValue(exposure_val)

    def setup_exposure_slider(self, exposure_val: int):
        cam_range = self.camera.exposure_range()
        max_exposure = int(min(1_000_000 // self.state.fps, cam_range[1]))
        self.exposure_slider.setRange(int(cam_range[0]), max_exposure)
        self.exposure_slider.setSingleStep(int(cam_range[2]))
        self.update_exposure(exposure_val=exposure_val)

    def setup_fps_slider(self, fps_val: float):
        fps_range = self.camera.fps_range()
        self.fps_slider.setRange(int(fps_range[0]), int(fps_range[1]))
        self.fps_slider.setSingleStep(int(fps_range[2]))
        self.update_fps(fps_val=fps_val)


    def update_filename(self):
        try:
            exposure_val = str(self.exposure_input.text())
            self.state.filename_stem = exposure_val
        except ValueError:
            pass


def main():

    app = QApplication(sys.argv)
    try:
        from camera_visualizer.camera_interface.ximea_interface import XimeaCamera
        camera_id = CameraEnum.XIMEA
    except ImportError:
        camera_id = CameraEnum.MOCK
    except Exception as e:
        raise e

    player = VideoPlayer(camera_id=camera_id, fps=5)
    player.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
