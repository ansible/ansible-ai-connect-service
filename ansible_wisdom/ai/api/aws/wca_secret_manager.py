import logging
from enum import Enum
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils import timezone

from .exceptions import WcaSecretManagerError, WcaSecretManagerMissingCredentialsError

SECRET_KEY_PREFIX = 'wca'

logger = logging.getLogger(__name__)


class Suffixes(Enum):
    API_KEY = 'api_key'
    MODEL_ID = 'model_id'


class BaseSecretManager:
    def save_secret(self, org_id: int, suffix: Suffixes, secret):
        raise NotImplementedError

    def delete_secret(self, org_id: int, suffix: Suffixes) -> None:
        raise NotImplementedError

    def get_secret(self, org_id: int, suffix: Suffixes) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    def secret_exists(self, org_id: int, suffix: Suffixes) -> bool:
        raise NotImplementedError


class DummySecretEntry(dict):
    @staticmethod
    def from_string(secret_string):
        return DummySecretEntry(
            {"SecretString": secret_string, "CreatedDate": timezone.now().isoformat()}
        )


class DummySecretManager(BaseSecretManager):
    def __init__(self, *args, **kwargs):
        self._secrets: dict[int, DummySecretEntry] = DummySecretManager.load_secrets(
            settings.WCA_SECRET_DUMMY_SECRETS
        )

    @staticmethod
    def load_secrets(from_settings: str):
        output: dict[int, Any] = {}

        for i in from_settings.split(","):
            values = i.split(":", 1)

            if len(values) < 2 or not (values[0] or values[1]):
                continue

            org_id = int(values[0])

            fields = values[1].split("<|sepofid|>", 1)
            if len(fields) == 1 and fields[0]:
                output[org_id] = {
                    Suffixes.API_KEY: DummySecretEntry.from_string("some-key"),
                    Suffixes.MODEL_ID: DummySecretEntry.from_string(fields[0]),
                }
            elif len(fields) == 2 and fields[0] and fields[1]:
                output[org_id] = {
                    Suffixes.API_KEY: DummySecretEntry.from_string(fields[0]),
                    Suffixes.MODEL_ID: DummySecretEntry.from_string(fields[1]),
                }

        return output

    def save_secret(self, org_id: int, suffix: Suffixes, secret) -> None:
        logger.debug("I'm fake: Secret won't be saved")

    def delete_secret(self, org_id: int, suffix: Suffixes) -> None:
        logger.debug("I'm fake: Secret won't be deleted")

    def get_secret(self, org_id: int, suffix: Suffixes) -> Optional[dict[str, Any]]:
        try:
            return self._secrets[org_id][suffix]
        except KeyError:
            return None

    def secret_exists(self, org_id: int, suffix: Suffixes) -> bool:
        return bool(self.get_secret(org_id, suffix))


class AWSSecretManager(BaseSecretManager):
    def __init__(
        self,
        aws_access_key_id,
        aws_secret_access_key,
        kms_secret_id,
        primary_region,
        replica_regions: list[str],
    ):
        self.replica_regions = replica_regions
        self.kms_secret_id = kms_secret_id
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.primary_region = primary_region
        self._client = None

    def get_client(self):
        if not self._client:
            if not all([self.aws_access_key_id, self.aws_secret_access_key, self.primary_region]):
                logger.error("Cannot load the ssm client, credentials are missing.")
                raise WcaSecretManagerMissingCredentialsError

            self._client = boto3.client(
                'secretsmanager',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.primary_region,
            )
        return self._client

    @staticmethod
    def get_secret_id(org_id: int, suffix: Suffixes):
        return f"{SECRET_KEY_PREFIX}/{org_id}/{suffix.value}"

    def save_secret(self, org_id: int, suffix: Suffixes, secret: str):
        """
        Stores or updates the Secret for a given org_id and suffix.
        """
        secret_id = self.get_secret_id(org_id, suffix)

        if self.secret_exists(org_id, suffix):
            try:
                response = self.get_client().put_secret_value(
                    SecretId=secret_id, SecretString=secret
                )
            except ClientError as e:
                raise WcaSecretManagerError(e)

        else:
            replica_regions = [
                {'Region': region, 'KmsKeyId': self.kms_secret_id}
                for region in self.replica_regions
            ]
            try:
                response = self.get_client().create_secret(
                    Name=secret_id,
                    KmsKeyId=self.kms_secret_id,
                    SecretString=secret,
                    AddReplicaRegions=replica_regions,
                )
            except ClientError as e:
                raise WcaSecretManagerError(e)

        return response['Name']

    def delete_secret(self, org_id, suffix: Suffixes) -> None:
        """
        Deletes the Secret for the given org_id and suffix.
        """
        secret_id = self.get_secret_id(org_id, suffix)
        try:
            # we need to remove the replica(s) first.
            # If this fails, we still try to delete the secret.
            _ = self.get_client().remove_regions_from_replication(
                SecretId=secret_id, RemoveReplicaRegions=self.replica_regions
            )
        except self.get_client().exceptions.ResourceNotFoundException:
            logger.error(
                "Error removing replica regions, "
                "Secret does not exist for org_id '%s' with suffix '%s'.",
                org_id,
                suffix,
            )
        except self.get_client().exceptions.InvalidParameterException:
            logger.error(
                "Error removing replica regions, "
                "invalid region(s) for org_id '%s' with suffix '%s'.",
                org_id,
                suffix,
            )
        except ClientError as e:
            logger.error(e)

        try:
            _ = self.get_client().delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)
        except ClientError as e:
            logger.error("Error removing Secret for org_id '%s' with suffix '%s'.", org_id, suffix)
            raise WcaSecretManagerError(e)

    def get_secret(self, org_id: int, suffix: Suffixes):
        """
        Returns the Secret for the given org_id and suffix or None if not found
        """
        secret_id = self.get_secret_id(org_id, suffix)
        try:
            return self.get_client().get_secret_value(SecretId=secret_id)
        except self.get_client().exceptions.ResourceNotFoundException:
            logger.info("No Secret exists for org with id '%s' and suffix '%s'.", org_id, suffix)
            return None
        except ClientError as e:
            logger.error("Error reading Secret for org_id '%s' with suffix '%s'.", org_id, suffix)
            raise WcaSecretManagerError(e)

    def secret_exists(self, org_id: int, suffix: Suffixes) -> bool:
        """
        Returns True if a Secret exists for the given org_id and suffix.
        """
        return self.get_secret(org_id, suffix) is not None
