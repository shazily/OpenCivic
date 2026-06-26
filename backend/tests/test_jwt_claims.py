"""JWT claim extraction tests."""

from app.services.auth.jwt_claims import decode_jwt_payload, extract_roles_and_staff_role


def test_extract_staff_role_from_realm_roles() -> None:
    import base64
    import json

    payload = {
        "realm_access": {"roles": ["data_steward", "offline_access"]},
    }
    segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    token = f"header.{segment}.sig"
    roles, staff_role = extract_roles_and_staff_role(token)
    assert "data_steward" in roles
    assert staff_role == "steward"


def test_decode_jwt_payload_invalid() -> None:
    assert decode_jwt_payload("not-a-jwt") == {}
