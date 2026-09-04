"""Security helper tests."""
import jwt
import pytest
from memes_shared.security import (
    create_access_token,
    decode_token,
    decrypt_credential,
    encrypt_credential,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("s3cret-password")
    assert h != "s3cret-password"
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token(42, {"role": "owner"}, expires_minutes=5)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "owner"


def test_jwt_expiry():
    token = create_access_token(1, expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_credential_encryption_roundtrip():
    secret = '{"access_token":"abc","ig_user_id":"123"}'
    enc = encrypt_credential(secret)
    assert enc != secret
    assert decrypt_credential(enc) == secret
    assert decrypt_credential("garbage") == ""
