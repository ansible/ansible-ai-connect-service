import os
import tempfile

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings, transient_settings

def scan_str_content(content, suffix=".txt"):
    """Detect secret keys in content
    Args:
        content (str): content to scan
        suffix (str): suffix of the file
    Returns:
        list: list of secrets found"""

    fp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode='w')
    fp.write(content)
    fp.close()
    secrets = SecretsCollection()
    # with transient_settings({'plugins_used': plugins, 'filters_used': filters}) as settings:
    with default_settings() as settings:
        secrets.scan_file(fp.name)
    os.unlink(fp.name)
    secrets_set = list(secrets.data.values())
    result = []
    if secrets_set:
        for secret in secrets_set[0]:
            result.append({
                'type': secret.type,
                'secret_value': secret.secret_value,
                'start_index': content.index(secret.secret_value),
                'end_index': content.index(secret.secret_value) + len(secret.secret_value),
            })
    return result


def scan_secrets_batch(examples):
    """Scan a batch of examples from a dataset for secret keys
    This add two columns to the dataset:
    - pii: (list) of secrets found
    - has_pii: (bool) whether the example contains secret"""

    list_secrets = []
    list_types = []
    list_limits = []
    has_secrets = []
    for text in examples["content"]:
        output = scan_str_content(text, suffix=".txt")
        if output:
            # get secret values of each element in output
            # to add this in datasets we need same number of samples in each row
            # we save it as str instead of list
            secrets = str([e['secret_value'] for e in output])
            types = str([e['type'] for e in output])
            limits = str([(e['start_index'], e['end_index']) for e in output])
            list_secrets.append(secrets)
            list_types.append(types)
            list_limits.append(limits)
            has_secrets.append(True)
        else:
            list_secrets.append("")
            list_types.append("")
            list_limits.append("")
            has_secrets.append(False)
    return {"secrets": list_secrets, "types": list_types, "has_secrets": has_secrets}

def get_secret(dict_val):
    if dict_val.get('secret_value'):
        return dict_val['secret_value']
    return None
