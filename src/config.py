import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def load_config() -> dict:
    """
    Loads the YAML configuration file and injects OAuth credentials
    (coming from .env) under the "oauth" key.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    config["oauth"] = {
        "client_id": os.getenv("ML_CLIENT_ID"),
        "client_secret": os.getenv("ML_CLIENT_SECRET"),
    }

    return config