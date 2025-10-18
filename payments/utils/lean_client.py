from .lean_requests import lean_get


def lean_get_accounts(entity_id: str) -> dict:
    """
    Calls Lean API to fetch accounts for a given entity using lean_get helper.
    """
    path = f"/data/v2/accounts?entity_id={entity_id}"
    response = lean_get(path)
    return response.get("data", {}).get("accounts", [])
