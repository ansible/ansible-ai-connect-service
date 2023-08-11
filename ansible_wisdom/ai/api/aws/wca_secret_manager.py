import logging

import boto3
from botocore.exceptions import ClientError

from .exceptions import WcaSecretManagerError

SECRET_KEY_PREFIX = 'wca'
DELETE_GRACE_PERIOD_DAYS = 7

logger = logging.getLogger(__name__)


class WcaSecretManager:
    def __init__(
        self, access_key, secret_access_key, kms_secret_id, primary_region, replica_regions
    ):
        if not isinstance(replica_regions, list):
            raise TypeError("Expected replica_regions to be a list")

        self.replica_regions = replica_regions
        self.kms_secret_id = kms_secret_id
        self._client = boto3.client(
            'secretsmanager',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_access_key,
            region_name=primary_region,
        )

    @staticmethod
    def get_secret_id(org_id):
        return f"{SECRET_KEY_PREFIX}/{org_id}/wca_key"

    def save_key(self, org_id, key):
        """
        Stores or updates the API Key for a given org_id
        """
        secret_id = self.get_secret_id(org_id)

        if self.key_exists(org_id):
            try:
                response = self._client.put_secret_value(SecretId=secret_id, SecretString=key)
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
                    SecretString=key,
                    AddReplicaRegions=replica_regions,
                )
            except ClientError as e:
                raise WcaSecretManagerError(e)

        return response['Name']

    def delete_key(self, org_id) -> None:
        """
        Deletes the API Key for the given org_id
        """
        secret_id = self.get_secret_id(org_id)
        try:
            # we need to remove the replica(s) first.
            # If this fails, we still try to delete the secret.
            _ = self._client.remove_regions_from_replication(
                SecretId=secret_id, RemoveReplicaRegions=self.replica_regions
            )
        except self._client.exceptions.ResourceNotFoundException:
            logger.error(
                "Error removing replica regions, secret does not exist for org_id '%s'", org_id
            )
        except self._client.exceptions.InvalidParameterException:
            logger.error(
                "Error removing replica regions, invalid region(s) for org_id '%s'", org_id
            )
        except ClientError:
            logger.error("Error removing replica regions for org_id '%s'", org_id)

        try:
            _ = self._client.delete_secret(
                SecretId=secret_id, RecoveryWindowInDays=DELETE_GRACE_PERIOD_DAYS
            )
        except ClientError as e:
            logger.error("Error removing secret for org_id '%s'", org_id)
            raise WcaSecretManagerError(e)

    def get_key(self, org_id):
        """
        Returns the API Key for the given org_id or None if not found
        """
        secret_id = self.get_secret_id(org_id)
        try:
            response = self._client.get_secret_value(SecretId=secret_id)
            return response['SecretString']
        except self._client.exceptions.ResourceNotFoundException:
            logger.info("No API Key exists for org with id '%s'", org_id)
            return None
        except ClientError as e:
            logger.error("Error reading secret for org_id '%s'", org_id)
            raise WcaSecretManagerError(e)

    def key_exists(self, org_id):
        """
        Returns True if a key exists for the given org_id
        """
        return self.get_key(org_id) is not None
