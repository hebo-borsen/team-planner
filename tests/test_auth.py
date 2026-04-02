from app import hash_password, authenticate_user, register_user, update_password


def test_hash_password_deterministic():
    assert hash_password("hello") == hash_password("hello")


def test_hash_password_differs_for_different_input():
    assert hash_password("a") != hash_password("b")


def test_register_user():
    success, msg = register_user("testuser", "testpass")
    assert success is True
    assert "created" in msg.lower()


def test_register_duplicate_user():
    register_user("dupuser", "pass1")
    success, msg = register_user("dupuser", "pass2")
    assert success is False
    assert "already exists" in msg.lower()


def test_authenticate_user():
    register_user("authuser", "secret")
    user = authenticate_user("authuser", "secret")
    assert user is not None
    assert user[1] == "authuser"


def test_authenticate_user_wrong_password():
    register_user("authuser2", "correct")
    user = authenticate_user("authuser2", "wrong")
    assert user is None


def test_update_password():
    register_user("pwuser", "oldpass")
    user = authenticate_user("pwuser", "oldpass")
    user_id = user[0]

    update_password(user_id, "newpass")

    assert authenticate_user("pwuser", "oldpass") is None
    assert authenticate_user("pwuser", "newpass") is not None
