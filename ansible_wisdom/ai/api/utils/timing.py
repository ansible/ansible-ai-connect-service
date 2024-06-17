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

import contextlib
import logging
import timeit

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def time_activity(activity_name: str):
    """Context Manager to report duration of an activity"""
    logger.info(f"[Timing] {activity_name} start.")
    start = timeit.default_timer()
    try:
        yield
    finally:
        duration = timeit.default_timer() - start
        logger.info(f"[Timing] {activity_name} finished (Took {duration:.2f}s)")
