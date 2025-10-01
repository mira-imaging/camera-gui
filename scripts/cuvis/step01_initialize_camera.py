import logging

import cuvis

from camera_visualizer.paths import load_data_path


def main():
    print(cuvis.version())

    factory_dir = load_data_path() / "cuvis_factory"
    cuvis.init(
        settings_path=f"{factory_dir}",
        global_loglevel=logging.DEBUG,
        logfile_name="cuvis_camera",
    )


if __name__ == "__main__":
    main()
