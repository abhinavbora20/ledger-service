import json
import os
from datetime import timedelta

import jwt
import pytest
from jwt.utils import base64url_encode

from app.security import (
    InvalidToken,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_the_password_and_verifies():
    password_hash = hash_password("correct horse battery")
    assert "correct horse" not in password_hash
    assert password_hash.startswith("$argon2id$")
    assert verify_password("correct horse battery", password_hash) is True


def test_wrong_password_fails():
    password_hash = hash_password("correct horse battery")
    assert verify_password("wrong password", password_hash) is False


def test_same_password_hashes_differently_because_of_salt():
    assert hash_password("same-password") != hash_password("same-password")


def test_garbage_hash_does_not_crash_verification():
    assert verify_password("anything", "not-a-real-hash") is False


def test_token_round_trip():
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token_is_rejected():
    token = create_access_token(42, expires_delta=timedelta(seconds=-1))
    with pytest.raises(InvalidToken):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token = create_access_token(42)
    header, _payload, signature = token.split(".")
    forged = base64url_encode(json.dumps({"sub": "43", "exp": 9999999999}).encode()).decode()
    with pytest.raises(InvalidToken):
        decode_access_token(f"{header}.{forged}.{signature}")


def test_token_signed_with_another_secret_is_rejected(monkeypatch):
    token = create_access_token(42)
    monkeypatch.setenv("JWT_SECRET", "a-completely-different-secret-value-123456789")
    with pytest.raises(InvalidToken):
        decode_access_token(token)


def test_unsigned_token_is_rejected():
    forged = jwt.encode({"sub": "42", "exp": 9999999999}, key=None, algorithm="none")
    with pytest.raises(InvalidToken):
        decode_access_token(forged)


def test_token_without_expiry_is_rejected():
    token = jwt.encode({"sub": "42"}, os.environ["JWT_SECRET"], algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_access_token(token)
