import time
import random
import functools
from logging_utils import get_logger

logger = get_logger("mockai.pipeline.retry")


def retry(times: int = 3, base_delay: float = 2.0, exceptions=(Exception,)):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == times:
                        break
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    logger.warning(
                        f"{fn.__name__} failed (attempt {attempt}/{times}): {e!r}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            logger.error(f"{fn.__name__} failed after {times} attempts, giving up.")
            raise last_exc
        return wrapper
    return decorator
