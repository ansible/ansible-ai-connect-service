import logging

from boto3 import client
from boto3.exceptions import ResourceNotExistsError

SECRET_KEY_PREFIX = 'wca/apikeys'
DELETE_GRACE_PERIOD_DAYS = 7

logger = logging.getLogger(__name__)


class WcaApiKeysClient:
    def __init__(
        self, access_key, secret_access_key, kms_secret_id, primary_region, replica_regions
    ):
        self.kms_secret_id = kms_secret_id
        self.replica_regions = replica_regions
        self._client = client(
            'secretsmanager',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_access_key,
            region_name=primary_region,
        )

    @staticmethod
    def __get_secret_id(org_id):
        return f"{SECRET_KEY_PREFIX}/{org_id}"

    def save_key(self, org_id, key):
        """
        Stores or updates the API Key for a given org_id
        """
        secret_id = self.__get_secret_id(org_id)

        if self.key_exists(org_id):
            response = self._client.put_secret_value(SecretId=secret_id, SecretString=key)
        else:
            replica_regions = list(
                map(
                    lambda region: {
                        'Region': region,
                        'KmsKeyId': self.kms_secret_id,
                    },
                    self.replica_regions,
                )
            )

            response = self._client.create_secret(
                Name=secret_id,
                KmsKeyId=self.kms_secret_id,
                SecretString=key,
                AddReplicaRegions=replica_regions,
            )

        return response['Name']

    def delete_key(self, org_id):
        """
        Deletes the API Key for the given org_id
        """
        secret_id = self.__get_secret_id(org_id)
        try:
            # we need to remove the replica(s) first
            _ = self._client.remove_regions_from_replication(
                SecretId=secret_id, RemoveReplicaRegions=self.replica_regions
            )
            _ = self._client.delete_secret(
                SecretId=secret_id, RecoveryWindowInDays=DELETE_GRACE_PERIOD_DAYS
            )
            return True
        except ResourceNotExistsError:
            logger.warning("Cannot delete non-existing API Key for org '%s'", org_id)
            return False

    def get_key(self, org_id):
        """
        Returns the API Key for the given org_id or None if not found
        """
        secret_id = self.__get_secret_id(org_id)
        try:
            response = self._client.get_secret_value(SecretId=secret_id)
            return response['SecretString']
        except ResourceNotExistsError:
            logger.info("No API Key exists for org with id '%s'", org_id)
            return None

    def key_exists(self, org_id):
        """
        Returns True if a key exists for the given org_id
        """
        return self.get_key(org_id) is not None
