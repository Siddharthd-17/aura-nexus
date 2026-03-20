import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "AURA NEXUS" in response.text

def test_admin_unauthorized_redirect():
    # Should redirect to login (303) because of the guard
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"

def test_valid_login():
    response = client.post("/login", data={"username": "user", "password": "user"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/user"

def test_invalid_login():
    response = client.post("/login", data={"username": "wrong", "password": "password"})
    assert response.status_code == 401

def test_get_responders():
    response = client.get("/responders")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
