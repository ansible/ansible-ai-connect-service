import requests
from django.conf import settings
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceUnavailable


class ModelServerHealthCheck(BaseHealthCheckBackend):
    # If this is set to False, the status endpoints will respond with a 200
    # status code even if the check errors.
    critical_service = True

    def __init__(self):
        super().__init__()
        self.api_type = settings.ANSIBLE_AI_MODEL_MESH_API_TYPE
        if self.api_type == 'http':
            self.url = f'{settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL}/ping'
        elif self.api_type == 'grpc':
            self.url = (
                f'{settings.ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL}://'
                f'{settings.ANSIBLE_AI_MODEL_MESH_HOST}:'
                f'{settings.ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT}/oauth/healthz'
            )
        else:  # 'mock' & 'wca'
            self.url = None

    def check_status(self):
        try:
            if self.url:
                # As of today (2023-03-27) SSL Certificate Verification falis with
                # the gRPC model server in the Staging environment.  The verify
                # option in the following line is just TEMPORARY and will be removed
                # as soon as the certificate is replaced with a valid one.
                res = requests.get(self.url, verify=(self.api_type != 'grpc'))  # !!!!! TODO !!!!!
                if res.status_code != 200:
                    raise Exception()
            else:
                pass
        except Exception as e:
            self.add_error(ServiceUnavailable('An error occurred'), e)

    def identifier(self):
        return self.__class__.__name__  # Display name on the endpoint.
