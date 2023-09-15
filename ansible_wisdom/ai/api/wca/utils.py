def is_org_id_invalid(org_id):
    try:
        numeric_org_id = int(org_id)
        return numeric_org_id <= 0
    except (ValueError, TypeError):
        return True
