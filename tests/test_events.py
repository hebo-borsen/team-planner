from app import (
    add_team_member,
    get_team_members,
    create_event,
    get_all_events,
    get_event_by_id,
    delete_event,
    set_event_response,
    get_event_responses,
)


def _create_member(name="EvtTest"):
    add_team_member(name, "📅")
    return next(m[0] for m in get_team_members() if m[1] == name)


def _create_event(name="Team Lunch"):
    create_event(name)
    return next(e[0] for e in get_all_events() if e[1] == name)


def test_create_event():
    success, msg = create_event("Friday Drinks")
    assert success is True
    assert "successfully" in msg


def test_get_all_events():
    create_event("Sprint Review")
    events = get_all_events()
    names = [e[1] for e in events]
    assert "Sprint Review" in names


def test_get_event_by_id():
    event_id = _create_event("Retrospective")
    event = get_event_by_id(event_id)
    assert event is not None
    assert event[1] == "Retrospective"


def test_get_event_by_id_not_found():
    event = get_event_by_id(999999)
    assert event is None


def test_delete_event():
    event_id = _create_event("Temp Event")
    delete_event(event_id)
    assert get_event_by_id(event_id) is None


def test_set_and_get_event_responses():
    member_id = _create_member()
    event_id = _create_event()

    result = set_event_response(event_id, member_id, True)
    assert result is True

    responses = get_event_responses(event_id)
    member_resp = next(r for r in responses if r[0] == member_id)
    assert member_resp[3] == 1  # is_attending = True


def test_update_event_response():
    member_id = _create_member()
    event_id = _create_event()

    set_event_response(event_id, member_id, True)
    set_event_response(event_id, member_id, False)

    responses = get_event_responses(event_id)
    member_resp = next(r for r in responses if r[0] == member_id)
    assert member_resp[3] == 0  # changed to not attending
