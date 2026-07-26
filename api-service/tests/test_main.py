from unittest.mock import AsyncMock, MagicMock, patch


def mock_transcription_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_data)
    return response

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_success(client):
    response = client.post("/register", json={"email": "alice@example.com", "password": "secret123"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client):
    client.post("/register", json={"email": "bob@example.com", "password": "secret123"})
    response = client.post("/register", json={"email": "bob@example.com", "password": "other123"})
    assert response.status_code == 400


def test_login_success(client):
    client.post("/register", json={"email": "carol@example.com", "password": "secret123"})
    response = client.post("/login", data={"username": "carol@example.com", "password": "secret123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    client.post("/register", json={"email": "dave@example.com", "password": "secret123"})
    response = client.post("/login", data={"username": "dave@example.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_jobs_requires_auth(client):
    response = client.get("/jobs")
    assert response.status_code == 401


def test_jobs_isolated_per_user(client):
    client.post("/register", json={"email": "userA@example.com", "password": "secret123"})
    client.post("/register", json={"email": "userB@example.com", "password": "secret123"})
    token_a = client.post("/login", data={"username": "userA@example.com", "password": "secret123"}).json()["access_token"]
    token_b = client.post("/login", data={"username": "userB@example.com", "password": "secret123"}).json()["access_token"]

    with patch("app.main.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_transcription_response(
            {"text": "hello", "language": "en", "duration_seconds": 1.0}
        )
        client.post(
            "/transcribe",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("test.wav", b"fake audio bytes", "audio/wav")},
        )

    jobs_a = client.get("/jobs", headers={"Authorization": f"Bearer {token_a}"}).json()
    jobs_b = client.get("/jobs", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert len(jobs_a) == 1
    assert len(jobs_b) == 0


def test_transcribe_mocked_success(client):
    client.post("/register", json={"email": "eve@example.com", "password": "secret123"})
    token = client.post("/login", data={"username": "eve@example.com", "password": "secret123"}).json()["access_token"]

    with patch("app.main.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_transcription_response(
            {"text": "hello world", "language": "en", "duration_seconds": 0.5}
        )
        response = client.post(
            "/transcribe",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.wav", b"fake audio bytes", "audio/wav")},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_transcribe_rejects_oversized_file(client):
    client.post("/register", json={"email": "frank@example.com", "password": "secret123"})
    token = client.post("/login", data={"username": "frank@example.com", "password": "secret123"}).json()["access_token"]

    big_file = b"0" * (26 * 1024 * 1024)
    response = client.post(
        "/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("big.wav", big_file, "audio/wav")},
    )
    assert response.status_code == 413