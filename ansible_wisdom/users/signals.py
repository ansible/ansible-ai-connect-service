from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
import logging


user_access_logger = logging.getLogger("user")


@receiver(user_logged_in)
def user_login_log(sender, user, **kwargs):
    """Successful user login log to user log"""
    user_access_logger.info(f"User: {user} LOGIN successful!")


@receiver(user_login_failed)
def user_login_failed_log(sender, user=None, **kwargs):
    """User failed login attempt log to user log"""
    if user:
        user_access_logger.info(f"User: {user} LOGIN failed!")
    else:
        user_access_logger.error("LOGIN failed; unknown user")


@receiver(user_logged_out)
def user_logout_log(sender, user, **kwargs):
    """User logout log to user log"""
    user_access_logger.info(f"User: {user} LOGOUT successful!")
