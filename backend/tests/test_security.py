from uuid import uuid4

from macrolens_api.security import TokenType, create_token, decode_token, hash_password, hash_refresh_token, verify_password


def test_password_hash_and_verify() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong", encoded)


def test_token_round_trip_and_refresh_hash() -> None:
    user_id = uuid4()
    session_id = uuid4()
    token = create_token(
        user_id=user_id,
        email="researcher@example.com",
        role="researcher",
        token_type=TokenType.ACCESS,
        session_id=session_id,
    )
    payload = decode_token(token, TokenType.ACCESS)
    assert payload.sub == user_id
    assert payload.sid == session_id
    assert hash_refresh_token(token) == hash_refresh_token(token)
