import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def user_login_log(sender, user, **kwargs):
    """Successful user login log to user log"""
    logger.info(f"User: {user} LOGIN successful")


@receiver(user_login_failed)
def user_login_failed_log(sender, user=None, **kwargs):
    """User failed login attempt log to user log"""
    if user:
        logger.info(f"User: {user} LOGIN failed")
    else:
        logger.info("LOGIN failed; unknown user")


@receiver(user_logged_out)
def user_logout_log(sender, user, **kwargs):
    """User logout log to user log"""
    logger.info(f"User: {user} LOGOUT successful")
