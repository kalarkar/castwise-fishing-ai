import os
from pathlib import Path
import tempfile

def test_local_journal_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        os.environ['FISHING_DB'] = str(Path(d) / 'test.db')
        from fastapi.testclient import TestClient
        from app import app
        client = TestClient(app)
        assert client.get('/').status_code == 200
        assert isinstance(client.get('/api/catches').json(), list)
        res = client.post('/api/catches', json={'species':'Steelhead','location':'Ganaraska River','caught_on':'2026-10-24','lure':'Roe bag'})
        assert res.status_code == 201, res.text
        cid = res.json()['id']
        assert any(c['id'] == cid for c in client.get('/api/catches').json())
        assert client.delete(f'/api/catches/{cid}').status_code == 204
