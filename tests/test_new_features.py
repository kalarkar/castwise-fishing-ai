from fastapi.testclient import TestClient
import app


def test_conditions_show_missing_buoy_without_faking_water(monkeypatch):
    def fake_fetch(key, url, ttl=900):
        if key.startswith('weather:'):
            return b'{"current":{"temperature_2m":12.3,"wind_speed_10m":14,"wind_direction_10m":270},"daily":{"time":["2026-10-24"]}}'
        raise OSError('Station offline')
    monkeypatch.setattr(app, 'fetch_cached', fake_fetch)
    res=TestClient(app.app).get('/api/conditions',params={'location':'Lake Ontario — Whitby'})
    assert res.status_code==200
    j=res.json()
    assert j['weather']['current']['wind_speed_10m']==14
    assert j['water']['celsius'] is None


def test_quota_separate_browser_cookies():
    a=TestClient(app.app)
    b=TestClient(app.app)
    qa=a.get('/api/quota').json()
    qb=b.get('/api/quota').json()
    assert qa['limit']==3 and qb['limit']==3
    assert a.cookies.get('castwise_id') != b.cookies.get('castwise_id')
