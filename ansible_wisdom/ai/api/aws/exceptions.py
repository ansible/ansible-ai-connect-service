class WcaSecretManagerError(Exception):
    """Request to AWS Secrets Manager failed"""


class WcaSecretManagerMissingCredentialsError(WcaSecretManagerError):
    """Cannot initialize the client because the credentials are not available"""
