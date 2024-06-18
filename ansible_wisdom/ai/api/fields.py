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
from rest_framework import serializers

from . import formatter as fmtr


class AnonymizedFieldMixin:
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        data = anonymizer.anonymize_struct(data)
        return data


# For multitask completion requests, the prompt is contained in a comment,
# which by default is removed by the anonymizer. This field therefore
# requires special handling to anonymize the comment rather than strip it.
class AnonymizedPromptMixin:
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        prompt, context = fmtr.extract_prompt_and_context(data)
        if fmtr.is_multi_task_prompt(prompt):
            anon_context = anonymizer.anonymize_struct(context)
            # Split the prompt to preserve the original leading whitespace
            segs = prompt.split("#", 1)
            anon_prompt = segs[0] + "#" + anonymizer.anonymize_text_block(segs[1])
            return f"{anon_context}{anon_prompt}"
        else:
            return anonymizer.anonymize_struct(data)


class AnonymizedCharField(AnonymizedFieldMixin, serializers.CharField):
    pass


class AnonymizedPromptCharField(AnonymizedPromptMixin, serializers.CharField):
    pass
