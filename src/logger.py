"""
Logging configuration driven by config/logging.yaml.

The log filename is generated dynamically with a timestamp (this can't
be expressed in static YAML), so the YAML value is overridden at
runtime before applying the configuration. The log level can be
overridden via config.yaml (logging.level key).
"""
import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path

import yaml

LOGGING_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "logging.yaml"
)


def setup_logger(config: dict | None = None) -> logging.Logger:
    """
    Loads config/logging.yaml, injects a filename with the current
    run's timestamp, applies an optional log level coming from
    config.yaml (logging.level key), and returns the logger named
    "mercadolibre_etl".
    """
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    with open(LOGGING_CONFIG_PATH, "r", encoding="utf-8") as file:
        logging_config = yaml.safe_load(file)

    logging_config["handlers"]["file"]["filename"] = log_filename

    if config and "logging" in config and "level" in config["logging"]:
        level = config["logging"]["level"]
        logging_config["handlers"]["console"]["level"] = level
        logging_config["handlers"]["file"]["level"] = level
        logging_config["loggers"]["mercadolibre_etl"]["level"] = level

    logging.config.dictConfig(logging_config)

    return logging.getLogger("mercadolibre_etl")