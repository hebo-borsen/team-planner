from app import add_team_member, get_team_members, delete_team_member


def test_add_team_member():
    success, msg = add_team_member("Alice", "🎉")
    assert success is True
    assert "successfully" in msg


def test_add_duplicate_team_member():
    add_team_member("Bob", "🚀")
    success, msg = add_team_member("Bob", "🚀")
    assert success is False
    assert "already exists" in msg


def test_get_team_members_returns_added():
    add_team_member("Charlie", "🐍")
    members = get_team_members()
    names = [m[1] for m in members]
    assert "Charlie" in names


def test_delete_team_member():
    add_team_member("Dave", "🎸")
    members = get_team_members()
    dave_id = next(m[0] for m in members if m[1] == "Dave")

    delete_team_member(dave_id)

    members = get_team_members()
    names = [m[1] for m in members]
    assert "Dave" not in names
