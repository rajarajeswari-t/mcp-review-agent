import logging

logger = logging.getLogger(__name__)


def connect(api_key, password):
    logger.info(f"Connecting with api_key={api_key} password={password}")
    logger.debug("User email on file: jane.doe@example.com")
