from rest_framework import serializers


class ContentScanRequestSerializer(serializers.Serializer):
    class Meta:
        fields = ['fileContent', 'autoFix', 'ansibleFileType']

    fileContent = serializers.CharField(required=True)
    autoFix = serializers.BooleanField(default=False)
    ansibleFileType = serializers.CharField(
        required=False,
        label="Ansible File Type",
        help_text="Ansible file type (playbook/tasks_in_role/tasks)",
    )

class ContentScanResponseSerializer(serializers.Serializer):
    class Meta:
        fields = ['fileContent', 'diagnotics']

    diagnostics = serializers.JSONField(required=True)
    fileContent = serializers.CharField(required=True)
