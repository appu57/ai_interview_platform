import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:  # avoid duplicate handlers if get_logger() is called twice
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
