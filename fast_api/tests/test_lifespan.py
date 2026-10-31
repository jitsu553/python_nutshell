from fastapi.testclient import TestClient
from main import app

def test_app_starts_and_stops():
    with TestClient(app) as c:      # entering the block runs startup
        assert c.get("/docs").status_code == 200
    # leaving the block ran shutdown; an unhandled error would have raised here