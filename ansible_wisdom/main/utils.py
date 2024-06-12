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

from ansible_anonymizer import anonymizer
from django.http import QueryDict

def anonymize_request_data(data):
    if isinstance(data, QueryDict):
        # See: https://github.com/ansible/ansible-wisdom-service/pull/201#issuecomment-1483015431  # noqa: E501
        new_data = data.copy()
        new_data.update(anonymizer.anonymize_struct(data.dict()))
    else:
        new_data = anonymizer.anonymize_struct(data)
    return new_data
