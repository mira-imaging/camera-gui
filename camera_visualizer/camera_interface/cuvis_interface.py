import logging
import time
from dataclasses import dataclass
from datetime import timedelta, datetime
from pathlib import Path
from typing import Type

import matplotlib.pyplot as plt
import cuvis
import numpy as np
import numpy.typing as npt

from camera_visualizer import Camera
from camera_visualizer.paths import load_data_path

# Camera Constants
CUVIS_MIN_EXPOSURE_MS = 15
CUVIS_MAX_EXPOSURE_MS = 33_333
CUVIS_EXPOSURE_INCREMENT_MS = 1

# Default Camera States
CUVIS_TIMEOUT_MS = 500
CUVIS_BIT_DEPTH = 12
CUVIS_SHAPE = (275, 290, 51)
CUVIS_VIEW_BANDS = (27, 9 ,4)
CUVIS_EXPOSURE_MS = 100
CUVIS_FPS_RANGE = (1, 15, 1)

@dataclass
class CuvisCameraState:
    save_folder: str | Path
    timeout_ms: int = CUVIS_TIMEOUT_MS
    bit_depth: int = CUVIS_BIT_DEPTH
    view_bands: list | tuple = CUVIS_VIEW_BANDS
    current_exposure: int = CUVIS_EXPOSURE_MS  # ms
    fps_range: tuple[int, int, int] = CUVIS_FPS_RANGE
    shape: tuple[int, ...] = CUVIS_SHAPE
    save_subfolder: str | None = None

    @property
    def save_path(self) -> Path:
        """
        Returns the full save_path directory: save_folder / save_subfolder.
        If save_subfolder is None, default to a time stamp.
        """
        save_folder = Path(self.save_folder)
        if self.save_subfolder is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]  # trim microseconds to milliseconds
            subfolder = f"rec_{timestamp}"
        else:
            subfolder = self.save_subfolder
        return save_folder / subfolder

    def dynamic_range(self) -> int:
        return 2 ** self.bit_depth - 1


class CuvisCamera(Camera):
    acquisition_context: cuvis.AcquisitionContext | None
    processing_context: cuvis.ProcessingContext | None
    state: CuvisCameraState

    def __init__(
            self,
            settings_path: str | Path | None = None,
            log_level: int = logging.INFO,
            logfile_name: str | None = None,
    ):
        if settings_path is None:
            settings_path = load_data_path() / "cuvis/factory"
        cuvis.init(
            settings_path=f"{settings_path}",
            global_loglevel=log_level,
            logfile_name=logfile_name,
        )
        # cuvis.set_log_level(log_level)

        self.acquisition_context = None
        self.processing_context = None

        data_dir = load_data_path()
        data_dir.mkdir(parents=True, exist_ok=True)
        records_dir = data_dir / f"cuvis/records"
        records_dir.mkdir(parents=True, exist_ok=True)
        self.state = CuvisCameraState(
            save_folder=records_dir,
        )

    def open(self, fps: float) -> None:
        factory_dir = load_data_path() / "cuvis/factory"
        calibration = cuvis.Calibration(base=factory_dir)

        self.acquisition_context = cuvis.AcquisitionContext(base=calibration)
        self.processing_context = cuvis.ProcessingContext(base=calibration)

        while self.acquisition_context.state == cuvis.HardwareState.Offline:
            print(".", end="")
            time.sleep(1)
        print("\nCamera is online.")

        self.acquisition_context.operation_mode = cuvis.OperationMode.Software
        self.acquisition_context.integration_time = self.state.current_exposure

    def close(self) -> None:
        cuvis.shutdown()
        print("Finished Recording.")

    def shape(self) -> tuple[int, ...]:
        return self.state.shape

    def bit_depth(self) -> int:
        return self.state.bit_depth

    def toggle_bit_depth(self) -> None:
        print(f"Bit-depth is fixed at {self.bit_depth()} bits.")

    def _get_frame_view(
            self,
            frame,
            view_bands: list[int] | tuple[int]
    ) -> npt.NDArray:
        frame_normalized = frame.astype(np.float32) / self.state.dynamic_range()
        frame_view = frame_normalized[:, :, view_bands]
        return frame_view

    def get_frame(self, fps: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns a numpy frame and its view.
        """
        measurement, result = self.acquisition_context.capture().get(timedelta(milliseconds=self.state.timeout_ms))
        self.processing_context.apply(mesu=measurement)
        image_data = measurement.cube  # cuvis ImageData class
        frame = image_data.array
        frame_view = self._get_frame_view(
            frame=frame,
            view_bands=self.state.view_bands,
        )
        return frame, frame_view

    def exposure(self) -> float:
        return self.state.current_exposure * 1000

    def exposure_range(self) -> tuple[int, int, int]:
        return (
            CUVIS_MIN_EXPOSURE_MS * 1000,
            CUVIS_MAX_EXPOSURE_MS * 1000,
            CUVIS_EXPOSURE_INCREMENT_MS * 1000,
        )

    def fps_range(self) -> tuple[int, int, int]:
        return self.state.fps_range

    def is_auto_exposure(self) -> bool:
        pass

    def toggle_auto_exposure(self) -> None:
        pass

    def set_exposure(self, exposure: int) -> bool:
        pass

    def init_exposure(self, max_exposure: int) -> None:
        pass

    def adjust_exposure(self) -> int:
        pass

    def check_exposure(self, frame: np.ndarray) -> bool:
        pass

    def toggle_view(self) -> None:
        pass

    def get_envi_options(self) -> None:
        pass

    def set_save_subfolder(self, subfolder: str) -> None:
        pass

    def save_folder(self) -> Path:
        pass

    def exception_type(self) -> Type[Exception]:
        return cuvis.cuvis_aux.SDKException


def main():
    cam = CuvisCamera()
    cam.open(fps=5)

    frame, frame_view = cam.get_frame(fps=5)
    print(f"frame type: {frame.dtype}, max: {frame.max()}")
    print(f"frame_view type: {frame_view.dtype}, max: {frame_view.max()}")

    fig, axs = plt.subplots(1, 1)
    axs.imshow(frame_view)
    plt.show()

    cam.close()


if __name__ == "__main__":
    main()
