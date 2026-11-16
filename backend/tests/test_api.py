def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_fleet(client):
    data = client.get("/api/fleet").json()
    assert len(data["engines"]) == 3
    assert all(e["rul_mean"] is not None for e in data["engines"])


def test_engine_detail_and_predictions(client):
    d = client.get("/api/engines/1").json()
    assert d["latest"]["rul_lower"] <= d["latest"]["rul_mean"] <= d["latest"]["rul_upper"]
    preds = client.get("/api/engines/1/predictions").json()
    assert len(preds) == d["last_cycle"]
    assert preds[-1]["true_rul"] == d["true_final_rul"]


def test_sensors_and_validation(client):
    s = client.get("/api/engines/1/sensors?sensors=s2,s11").json()
    assert set(s["series"]) == {"s2", "s11"}
    assert client.get("/api/engines/1/sensors?sensors=bogus").status_code == 422
    assert client.get("/api/engines/999").status_code == 404


def test_explain(client):
    e = client.get("/api/engines/1/explain").json()
    assert len(e["features"]) > 5 and "name" in e["features"][0]
    assert len(e["temporal"]) == len(e["window_cycles"])


def test_ingest_cycle(client):
    last = client.get("/api/engines/2/sensors?sensors=" + ",".join(f"s{i}" for i in range(1, 22))).json()
    sensors = {k: v[-1] for k, v in last["series"].items()}
    before = client.get("/api/engines/2").json()["last_cycle"]
    r = client.post("/api/engines/2/cycles", json={
        "settings": {"setting_1": 0.0, "setting_2": 0.0, "setting_3": 100.0}, "sensors": sensors})
    assert r.status_code == 200, r.text
    assert r.json()["cycle"] == before + 1
    dup = client.post("/api/engines/2/cycles", json={
        "cycle": before, "settings": {"setting_1": 0, "setting_2": 0, "setting_3": 100}, "sensors": sensors})
    assert dup.status_code == 409


def test_alert_ack(client):
    alerts = client.get("/api/alerts").json()
    if alerts:
        a = client.patch(f"/api/alerts/{alerts[0]['id']}/ack").json()
        assert a["acknowledged"] is True
