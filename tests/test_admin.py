import pytest

from shop.app import create_app
from shop.config import DEFAULTS


@pytest.fixture
def client():
    return create_app(api_key="admin-test-key").test_client()


def unlock(client):
    response = client.post("/api/admin/login", headers={"X-API-Key": "admin-test-key"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.get_json()["csrf"]}


def test_admin_login_and_cookie_session(client):
    assert client.get("/admin/").status_code == 200
    assert b"admin-test-key" not in client.get("/admin/").data
    assert client.get("/api/admin/session").get_json() == {"authenticated": False, "csrf": None}
    response = client.post("/api/admin/login", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
    headers = unlock(client)
    response = client.get("/api/admin/session")
    assert response.get_json() == {"authenticated": True, "csrf": headers["X-CSRF-Token"]}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path", ["/api/selectors", "/api/selectors/reset", "/api/admin/preset", "/api/admin/logout"])
def test_anonymous_and_missing_csrf_cannot_change_state(client, path):
    assert client.post(path, json={}).status_code == 401
    unlock(client)
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"X-CSRF-Token": "wrong"}).status_code == 401
    assert client.get("/api/selectors").get_json()["config"] == DEFAULTS


def test_presets_replace_changes_and_leave_labs_unchanged(client):
    headers = unlock(client)
    response = client.post("/api/admin/preset", json={"name": "combined"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["config"]["title_class"] == "item-name"
    response = client.post("/api/admin/preset", json={"name": "pagination"}, headers=headers)
    state = response.get_json()
    assert state["config"]["title_class"] == DEFAULTS["title_class"]
    assert set(state["changed"]) == {"next_page_class"}
    assert 'class="forward"' in client.get("/coffee/beans/").text
    assert 'class="next"' in client.get("/labs/classic/coffee/beans/").text
    assert "/labs/classic/assets/site.css" in client.get("/admin/").text
    response = client.post("/api/selectors/reset", headers=headers)
    assert response.status_code == 200 and response.get_json()["changed"] == {}


def test_custom_edit_validation_and_logout(client):
    headers = unlock(client)
    response = client.patch("/api/selectors", json={"title_class": "my-title", "extra_wrapper": True}, headers=headers)
    assert response.status_code == 200
    assert 'class="my-title"' in client.get("/coffee/beans/").text
    before = client.get("/api/selectors").get_json()
    assert client.patch("/api/selectors", json={"title_class": "<script>"}, headers=headers).status_code == 400
    assert client.get("/api/selectors").get_json() == before
    assert client.post("/api/admin/logout", headers=headers).status_code == 200
    assert client.get("/api/admin/session").get_json()["authenticated"] is False
    assert client.patch("/api/selectors", json={"title_class": "other"}, headers=headers).status_code == 401


@pytest.mark.parametrize("body", [{"name": "nope"}, {"name": []}, [], None])
def test_invalid_preset_is_rejected_without_changing_state(client, body):
    headers = unlock(client)
    assert client.post("/api/admin/preset", json=body, headers=headers).status_code == 400
    assert client.get("/api/selectors").get_json()["config"] == DEFAULTS


def test_forged_session_and_separate_client_cannot_write(client):
    unlock(client)
    app = client.application
    stranger = app.test_client()
    stranger.set_cookie("session", "not-a-signed-session")
    assert stranger.post("/api/admin/preset", json={"name": "titles"}).status_code == 401
    assert stranger.get("/api/admin/session").get_json()["authenticated"] is False
