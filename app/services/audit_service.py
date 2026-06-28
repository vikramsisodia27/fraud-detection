import logging

logger = logging.getLogger(__name__)


class AuditService:

    def log_investigation(
            self,
            result
    ):
        logger.info(result)