def remove_pii(strategy, details, backend, user=None, *args, **kwargs):
    details.pop('email', None)
    details.pop('fullname', None)
    details.pop('first_name', None)
    details.pop('last_name', None)
