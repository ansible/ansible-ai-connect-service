import logging
from enum import Enum
from typing import Union

import boto3
from botocore.exceptions import ClientError

from .exceptions import WcaSecretManagerError

SECRET_KEY_PREFIX = 'wca'

logger = logging.getLogger(__name__)


class Suffixes(Enum):
    API_KEY = 'api_key'
    MODEL_ID = 'model_id'


class WcaSecretManager:
    def __init__(
        self,
        access_key,
        secret_access_key,
        kms_secret_id,
        primary_region,
        replica_regions: list[str],
    ):
        self.replica_regions = replica_regions
        self.kms_secret_id = kms_secret_id
        self._client = boto3.client(
            'secretsmanager',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_access_key,
            region_name=primary_region,
        )

    @staticmethod
    def get_secret_id(org_id, suffix: Suffixes):
        return f"{SECRET_KEY_PREFIX}/{org_id}/{suffix.value}"

    def save_secret(self, org_id, suffix: Suffixes, secret):
        """
        Stores or updates the Secret for a given org_id and suffix.
        """
        secret_id = self.get_secret_id(org_id, suffix)

        if self.secret_exists(org_id, suffix):
            try:
                response = self._client.put_secret_value(SecretId=secret_id, SecretString=secret)
            except ClientError as e:
                raise WcaSecretManagerError(e)

        else:
            replica_regions = [
                {'Region': region, 'KmsKeyId': self.kms_secret_id}
                for region in self.replica_regions
            ]
            try:
                response = self._client.create_secret(
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
            _ = self._client.remove_regions_from_replication(
                SecretId=secret_id, RemoveReplicaRegions=self.replica_regions
            )
        except self._client.exceptions.ResourceNotFoundException:
            logger.error(
                "Error removing replica regions, "
                "Secret does not exist for org_id '%s' with suffix '%s'.",
                org_id,
                suffix,
            )
        except self._client.exceptions.InvalidParameterException:
            logger.error(
                "Error removing replica regions, "
                "invalid region(s) for org_id '%s' with suffix '%s'.",
                org_id,
                suffix,
            )
        except ClientError as e:
            logger.error(e)

        try:
            _ = self._client.delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)
        except ClientError as e:
            logger.error("Error removing Secret for org_id '%s' with suffix '%s'.", org_id, suffix)
            raise WcaSecretManagerError(e)

    def get_secret(self, org_id, suffix: Suffixes):
        """
        Returns the Secret for the given org_id and suffix or None if not found
        """
        secret_id = self.get_secret_id(org_id, suffix)
        try:
            return self._client.get_secret_value(SecretId=secret_id)
        except self._client.exceptions.ResourceNotFoundException:
            logger.info("No Secret exists for org with id '%s' and suffix '%s'.", org_id, suffix)
            return None
        except ClientError as e:
            logger.error("Error reading Secret for org_id '%s' with suffix '%s'.", org_id, suffix)
            raise WcaSecretManagerError(e)

    def secret_exists(self, org_id, suffix: Suffixes):
        """
        Returns True if a Secret exists for the given org_id and suffix.
        """
        return self.get_secret(org_id, suffix) is not None
