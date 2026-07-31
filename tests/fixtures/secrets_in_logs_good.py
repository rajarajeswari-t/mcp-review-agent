import logging

logger = logging.getLogger(__name__)


def connect(api_key, password):
    logger.info("Connecting to database")
    logger.debug("Authentication succeeded for user")
