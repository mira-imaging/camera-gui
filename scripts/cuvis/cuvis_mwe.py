import logging
import time
from datetime import timedelta, datetime

import cuvis
import numpy.typing as npt
import matplotlib.pyplot as plt

from camera_visualizer.paths import load_data_path


def update_visualize(
        frame: npt.NDArray,
        rgb_bands: tuple | list,
        im_display,
        ax: plt.Axes,
):
    image_vis = frame[:, :, rgb_bands]
    image_vis = image_vis / image_vis.max()

    if im_display is None:
        im_display = ax.imshow(image_vis)
    else:
        im_display.set_data(image_vis)

    ax.set_title("Live RGB preview")
    plt.pause(0.01)  # allow GUI event loop to update

    return im_display


def main():
    factory_dir = load_data_path() / "cuvis/factory"
    settings_dir = load_data_path() / "cuvis/factory"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]  # trim microseconds to milliseconds
    output_dir = load_data_path() / f"cuvis/data/record_{timestamp}"
    exposure = 100  # ms
    log_state = logging.INFO
    rgb_bands = (27, 9, 4)

    cuvis.init(
        settings_path=f"{settings_dir}",
        global_loglevel=log_state,
        logfile_name=None,
    )
    cuvis.set_log_level(log_state)

    calibration = cuvis.Calibration(base=factory_dir)
    acquisition_context = cuvis.AcquisitionContext(base=calibration)
    processing_context = cuvis.ProcessingContext(base=calibration)

    export_settings = cuvis.EnviExportSettings(export_dir=f"{output_dir}")
    exporter = cuvis.EnviExporter(ge=export_settings)

    while acquisition_context.state == cuvis.HardwareState.Offline:
        print(".", end="")
        time.sleep(1)
    print("\nCamera is online.")

    acquisition_context.operation_mode = cuvis.OperationMode.Software
    acquisition_context.integration_time = exposure

    print("Start recording (press Ctrl+C to stop)")

    # Setup live matplotlib figure
    plt.ion()
    fig, ax = plt.subplots()
    im_display = None

    try:
        while True:
            async_measurement = acquisition_context.capture()
            measurement, result = async_measurement.get(timedelta(milliseconds=500))

            if measurement is None:
                print("Failed measurement.")
                continue

            processing_context.apply(mesu=measurement)
            image_data = measurement.cube
            image_arr = image_data.data

            # Visualize
            im_display = update_visualize(
                frame=image_arr,
                rgb_bands=rgb_bands,
                im_display=im_display,
                ax=ax,
            )

            # Export
            exporter.apply(measurement)

    except KeyboardInterrupt:
        print("Stopped by user.")

    finally:
        cuvis.shutdown()
        print("Finished Recording.")


if __name__ == "__main__":
    main()
