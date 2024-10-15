#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import json
import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import Signal, receiver

logger = logging.getLogger(__name__)

user_set_wca_api_key = Signal()
user_delete_wca_api_key = Signal()
user_set_wca_model_id = Signal()
user_delete_wca_model_id = Signal()
user_set_telemetry_settings = Signal()


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


@receiver(user_set_wca_api_key)
def user_set_wca_key_log(sender, user, org_id, api_key, **kwargs):
    """User set WCA API Key"""
    logger.info(
        f"User: '{user}' set WCA Key for Organisation '{org_id}' to '{_obfuscate(api_key)}'."
    )


@receiver(user_set_wca_model_id)
def user_set_wca_model_id_log(sender, user, org_id, model_id, **kwargs):
    """User set WCA Model Id"""
    logger.info(
        f"User: '{user}' set WCA Model Id for Organisation '{org_id}' to '{_obfuscate(model_id)}'."
    )


@receiver(user_set_telemetry_settings)
def user_set_telemetry_settings_log(sender, user, org_id, settings, **kwargs):
    """User set Telemetry settings"""
    data = json.dumps(settings, indent=2)
    message = f"User: '{user}' set Telemetry settings for Organisation " f"'{org_id}' to '{data}'."
    logger.info(message)


def _obfuscate(value: str) -> str:
    if len(value) < 4:
        return "*" * len(value)

    retention = 1
    if len(value) > 8:
        retention = 2
    if len(value) > 16:
        retention = 4
    repeat = len(value) - 2 * retention
    return value[:retention] + ("*" * repeat) + value[retention + repeat :]
