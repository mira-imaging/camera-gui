from pathlib import Path
import os

import dotenv


def load_project_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_data_path():
    dotenv.load_dotenv()
    data_path = os.getenv("DATA_PATH")
    if data_path is not None:
        data_path = Path(data_path)
        if data_path.is_dir():
            return data_path
        else:
            raise NotADirectoryError(f"The data directory '{data_path}', loaded from '.env', does not exist.")
    return load_project_dir() / "data"


def main():
    print(load_project_dir())
    print(load_data_path())


if __name__ == "__main__":
    main()
