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

"""
List of parameters that are allowed to track for commercial users. Add new events and/or values
there ONLY if parameters should be tracked for seated users.
See https://issues.redhat.com/browse/AAP-15568 for more details.
"""

ALLOW_LIST = {
    "contentmatch": {
        "suggestionId": None,
        "duration": None,
        "exception": None,
        "problem": None,
        "metadata": {"encode_duration:": None, "search_duration": None},
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "completion": {
        "duration": None,
        "response": {
            "exception": None,
            "error_type": None,
            "message": None,
            "status_code": None,
            "status_text": None,
        },
        "suggestionId": None,
        "metadata": {
            "activityId": None,
            "ansibleFileType": None,
        },
        "modelName": None,
        "imageTags": None,
        "tasks": [
            {
                "collection": None,
                "module": None,
            },
        ],
        "taskCount": None,
        "promptType": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "inlineSuggestionFeedback": {
        "action": None,
        "suggestionId": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "prediction": {
        "duration": None,
        "exception": None,
        "problem": None,
        "request": {
            "instances": [
                {
                    "organization_id": None,
                    "rh_user_has_seat": None,
                    "suggestionId": None,
                    "userId": None,
                }
            ]
        },
        "response": {
            "exception": None,
            "predictions": None,
            "status_code": None,
            "status_text": None,
        },
        "suggestionId": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "postprocessLint": {
        "exception": None,
        "problem": None,
        "duration": None,
        "suggestionId": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "postprocess": {
        "exception": None,
        "problem": None,
        "duration": None,
        "recommendation": None,
        "truncated": None,
        "suggestionId": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "segmentError": {
        "error_type": None,
        "details": None,
        "timestamp": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "plans": None,
    },
    "sentimentFeedback": {
        "value": None,
        "feedback": None,
        "exception": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "suggestionQualityFeedback": {
        "prompt": None,
        "providedSuggestion": None,
        "expectedSuggestion": None,
        "additionalComment": None,
        "exception": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "issueFeedback": {
        "title": None,
        "description": None,
        "type": None,
        "exception": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelApiKeyGet": {
        "duration": None,
        "exception": None,
        "problem": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelApiKeySet": {
        "duration": None,
        "exception": None,
        "problem": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelApiKeyDelete": {
        "duration": None,
        "exception": None,
        "problem": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelApiKeyValidate": {
        "duration": None,
        "exception": None,
        "problem": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelIdGet": {
        "duration": None,
        "exception": None,
        "problem": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelIdSet": {
        "duration": None,
        "exception": None,
        "problem": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "modelIdValidate": {
        "duration": None,
        "exception": None,
        "problem": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "telemetrySettingsGet": {
        "duration": None,
        "exception": None,
        "problem": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "opt_out": None,
        "timestamp": None,
        "plans": None,
    },
    "telemetrySettingsSet": {
        "duration": None,
        "exception": None,
        "problem": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "opt_out": None,
        "timestamp": None,
        "plans": None,
    },
    "trialExpired": {
        "type": None,
        "suggestionId": None,
        "modelName": None,
        "imageTags": None,
        "hostname": None,
        "groups": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "explainPlaybook": {
        "duration": None,
        "exception": None,
        "explanationId": None,
        "groups": None,
        "hostname": None,
        "imageTags": None,
        "playbook_length": None,
        "response": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "plans": None,
    },
    "codegenPlaybook": {
        "duration": None,
        "exception": None,
        "generationId": None,
        "groups": None,
        "hostname": None,
        "imageTags": None,
        "modelName": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "response": None,
        "timestamp": None,
        "wizardId": None,
        "plans": None,
    },
    "playbookGenerationAction": {
        "action": None,
        "fromPage": None,
        "groups": None,
        "hostname": None,
        "imageTags": None,
        "modelName": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "toPage": None,
        "wizardId": None,
        "plans": None,
    },
    "playbookExplanationFeedback": {
        "exception": None,
        "feedback": None,
        "groups": None,
        "hostname": None,
        "imageTags": None,
        "modelName": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "timestamp": None,
        "value": None,
        "plans": None,
    },
    "oneClickTrialStarted": {
        "exception": None,
        "groups": None,
        "hostname": None,
        "imageTags": None,
        "modelName": None,
        "problem": None,
        "request": None,
        "rh_user_has_seat": None,
        "rh_user_org_id": None,
        "plans": None,
    },
    "chatFeedbackEvent": {
        "*": None,
    },
    "chatOperationalEvent": {
        "*": None,
    },
    "streamingChatOperationalEvent": {
        "*": None,
    },
}
