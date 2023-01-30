from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers

from ..models import AIModel


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Request Sample',
            description='A valid sample request.',
            value={
                'context': '---\n- hosts: all\n  become: yes\n\n  tasks:\n',
                'prompt': '- name: Install Apache\n',
            },
            request_only=True,
            response_only=False,
        ),
    ]
)
class CompletionRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['context', 'prompt', 'userId', 'suggestionId']

    context = serializers.CharField(
        trim_whitespace=False,
        default='',
        allow_blank=True,
        label='Context',
        help_text='Editor context.',
    )
    prompt = serializers.CharField(
        trim_whitespace=False,
        required=False,
        label='Prompt',
        help_text='Editor prompt.',
    )
    userId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="User ID",
        help_text="A UUID that identifies a user.",
    )
    suggestionId = serializers.UUIDField(
        format='hex_verbose',
        required=False,
        label="Suggestion ID",
        help_text="A UUID that identifies a suggestion.",
    )

    def validate(self, data):
        data = super().validate(data)
        CompletionRequestSerializer.extract_prompt_from_context(data)
        return data

    @staticmethod
    def extract_prompt_from_context(data):
        #
        # If prompt is not specified in the incoming data, set the last line
        # of context to prompt and set the remaining to context. Note that
        # usually both prompt and context end with '\n'.
        #
        if 'context' in data and 'prompt' not in data:
            s = data['context'][:-1].rpartition('\n')
            if s[1] == '\n':
                data['prompt'] = s[2].lstrip() + data['context'][-1]
                data['context'] = s[0] + s[1]
            else:
                data['prompt'] = ''


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Valid example',
            summary='Response sample',
            description='A valid sample response.',
            value={'predictions': ['  package:\n    name: apache2\n    state: present\n']},
            request_only=False,
            response_only=True,
        ),
    ]
)
class CompletionResponseSerializer(serializers.Serializer):
    class Meta:
        fields = ['predictions']

    predictions = serializers.ListField(child=serializers.CharField(trim_whitespace=False))


class AIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = "__all__"
