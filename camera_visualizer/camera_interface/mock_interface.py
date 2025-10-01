from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Type

import numpy as np

from camera_visualizer.paths import load_data_path
from camera_visualizer.serializer import save_frame, SaveFormatEnum


class Camera(ABC):

    @abstractmethod
    def open(self, fps: float) -> None:
        """
        Instructions to open the device and start the stream.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """
        Instructions to end the stream and close the camera
        """
        ...

    @abstractmethod
    def toggle_bit_depth(self) -> None:
        """
        Change the camera status to a different bit depth
        """
        ...

    @abstractmethod
    def bit_depth(self) -> int:
        """
        Retrieve the current bit depth
        """
        ...

    @abstractmethod
    def get_frame(self, fps: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns a tuple of raw frame and frame for visualization as NumPy
        arrays. The second output is expected to be a float32 between 0 and 1.
        """
        ...

    @abstractmethod
    def shape(self) -> tuple[int, int]:
        """
        Gets the shape of the image.
        """
        ...

    @abstractmethod
    def exposure(self) -> int:
        """
        Gets the current exposure level in microseconds.
        """
        ...

    @abstractmethod
    def exposure_range(self) -> tuple[int, int, int]:
        """
        Gets a tuple of minimum, maximum and allowed increase for the exposure
        level in microseconds.
        """
        ...

    @abstractmethod
    def fps_range(self) -> tuple[int, int, int]:
        """
        Gets a tuple for the minimum, maximum and step for the allowed fps
        in a camera.
        """
        ...

    @abstractmethod
    def is_auto_exposure(self) -> bool:
        """
        Returns True if camera is set to automatic exposure
        """
        ...

    @abstractmethod
    def toggle_auto_exposure(self) -> None:
        """
        Toggles auto exposure if camera has it available as option
        """

    @abstractmethod
    def set_exposure(self, exposure: int) -> bool:
        """
        Sets the exposure level (in microseconds).
        """
        ...

    @abstractmethod
    def init_exposure(self, max_exposure: int) -> None:
        """
        Initialize the exposure level for the automatic exposure assessment.
        """
        ...

    @abstractmethod
    def adjust_exposure(self) -> int:
        """
        Return the exposure level during the automatic exposure assessment.
        """
        ...

    @abstractmethod
    def check_exposure(self, frame: np.ndarray) -> bool:
        """
        Checks if the automatic exposure assessment has reached convergence.
        """
        ...

    @abstractmethod
    def toggle_view(self) -> None:
        """
        FLips the state of the camera to allow for a different frame view.
        """
        ...

    @abstractmethod
    def get_envi_options(self) -> None:
        """
        Gets the envi metadata for the savefile.
        """
        ...

    @abstractmethod
    def set_save_subfolder(self, subfolder: str) -> None:
        """
        Sets the save subfolder
        """
        ...

    @abstractmethod
    def save_folder(self) -> Path:
        """
        Returns the save path folder for saving data.
        """
        ...

    @abstractmethod
    def exception_type(self) -> Type[Exception]:
        """
        Returns the camera specific exception type.
        """

        ...

    def save_frame(
        self,
        frame: np.ndarray,
        filename_stem: str,
        fmt: SaveFormatEnum
    ) -> None:
        """
        Saves the current frame.
        """
        save_frame(
            frame=frame,
            save_folder=self.save_folder(),
            filename_stem=filename_stem,
            envi_options=self.get_envi_options(),
            fmt=fmt,
        )


class MockCamera(Camera):

    def __init__(self):
        self._shape = [480, 640]
        self._exposure = 10_000
        self._exposure_max = 500_000
        self._exposure_min = 100
        self._auto_exposure = False
        self._bit_depth = 8
        self._counter = 0
        self._toggle_view = 0
        data_path = load_data_path() / "mock"
        data_path.mkdir(parents=True, exist_ok=True)
        self._save_folder = data_path
        self._subfolder = None

    def open(self, fps: float) -> None:
        pass

    def close(self) -> None:
        pass

    def toggle_bit_depth(self):
        self._bit_depth = 8 if self._bit_depth == 16 else 16

    def toggle_view(self):
        self._toggle_view = 0 if self._toggle_view == 1 else 1

    def bit_depth(self) -> int:
        return self._bit_depth

    def shape(self):
        return self._shape

    def exposure(self):
        return self._exposure

    def exposure_range(self) -> tuple[int, int, int]:
        return 100, 500_000, 20

    def fps_range(self) -> tuple[int, int, int]:
        return 5, 50, 5

    def set_exposure(self, exposure: int) -> bool:
        if exposure >= self._exposure_max or exposure <= self._exposure_min:
            return False
        self._exposure = exposure
        return True
    
    def is_auto_exposure(self) -> bool:
        return self._auto_exposure

    def toggle_auto_exposure(self) -> None:
        self._auto_exposure = not self._auto_exposure

    def init_exposure(self, max_exposure: int) -> None:
        self._exposure_max = min(max_exposure, 500_000)
        self._exposure_min = 100

    def adjust_exposure(self) -> int:
        return int((self._exposure_min + self._exposure_max) // 2)

    def check_exposure(self, frame: np.ndarray) -> bool:
        if self._exposure > 10000:
            self._exposure_max = self._exposure - 1
        else:
            self._exposure_min = self._exposure + 1
        if 8000 <= self.exposure() <= 12000:
            self._exposure_max = 500_000
            self._exposure_min = 100
            return True
        else:
            return False

    def get_frame(self, fps: float) -> tuple[np.ndarray, np.ndarray]:
        """Returns a (H, W) grayscale float32 NumPy array in [0, 1]"""
        img = np.zeros(self.shape(), dtype=np.float32)
        if self._toggle_view == 0:
            x = (self._counter % self.shape()[1])
            img[:, x:x + 5] = 1.0  # moving white bar
        else:
            y = (self._counter % self.shape()[0])
            img[y:y + 5, :] = 1.0
        self._counter += 1
        return img, img

    def get_envi_options(self) -> dict:
        return {
            'samples': self._shape[1],
            'lines': self._shape[0],
            'bands': 1,
            'interleave': 'bsq',
            'byte order': 0,
            'data type': 4,
            'acquisition time': datetime.now().isoformat(),
        }

    def set_save_subfolder(self, subfolder: str) -> None:
        self._subfolder = subfolder
        self.save_folder().mkdir(parents=False, exist_ok=True)

    def save_folder(self):
        if self._subfolder is None:
            return self._save_folder
        return self._save_folder / self._subfolder
    
    def exception_type(self) -> Type[Exception]:
        return Exception


class CameraEnum(str, Enum):
    MOCK = "mock"
    XIMEA = "ximea"
    TIS = "tis"
    CUVIS = "cuvis"


def camera(camera_id: CameraEnum | str) -> Camera:
    
    if camera_id == CameraEnum.MOCK:
        return MockCamera()
    elif camera_id == CameraEnum.XIMEA:
        from camera_visualizer.camera_interface.ximea_interface import XimeaCamera
        return XimeaCamera()
    elif camera_id == CameraEnum.TIS:
        from camera_visualizer.camera_interface.tis_interface import TisCamera
        return TisCamera()
    elif camera_id == CameraEnum.CUVIS:
        from camera_visualizer.camera_interface.cuvis_interface import CuvisCamera
        return CuvisCamera()
    else:
        raise ValueError(f"Camera f{camera_id} not known.")
