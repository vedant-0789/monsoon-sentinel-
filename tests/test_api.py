"""API integration tests on the shipped artifacts (replay mode: no network needed)."""

DAY = "2024-07-25"


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_flood_day_bulletin(client):
    b = client.get(f"/api/bulletin?mode=replay&date={DAY}").json()
    assert b["headline_alert"] == "red"
    assert 0.5 < b["heavy_rain"]["probability"] <= 1
    assert b["heavy_rain"]["drivers"], "every forecast must carry its reasons"
    assert sum(b["road_alert_counts"].values()) > 20000
    assert b["impact"]["red_road_km"] > 100


def test_quiet_day_is_green(client):
    b = client.get("/api/bulletin?mode=replay&date=2023-07-10").json()
    assert b["headline_alert"] == "green"


def test_replay_validation(client):
    assert client.get("/api/bulletin?mode=replay").status_code == 400
    assert client.get("/api/bulletin?mode=replay&date=2024-12-01").status_code == 404


def test_roads_geojson(client):
    r = client.get(f"/api/roads?mode=replay&date={DAY}&min_alert=red")
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert fc["features"] and all(f["properties"]["a"] == "red" for f in fc["features"])


def test_point_lookup_ekta_nagar(client):
    p = client.get(f"/api/point?lat=18.4821&lon=73.8261&mode=replay&date={DAY}").json()
    assert p["covered"] and p["alert"] == "red"


def test_actions_respect_pump_fleet(client):
    zones = client.get(f"/api/actions?mode=replay&date={DAY}&limit=10").json()
    assert zones and zones[0]["rank"] == 1
    assert sum(z.get("rl_deploy_pump", False) for z in zones) <= 5
    assert all("depot" in z for z in zones)


def test_history(client):
    h = client.get(f"/api/history?mode=replay&date={DAY}").json()
    assert len(h) >= 10 and h[-1]["date"] == DAY


def test_classifier(client):
    c = client.post("/api/classify", json={"text": "Karve road pe ghutno tak paani, gaadi band"}).json()
    assert c["category"] == "waterlogging" and c["urgent"]


def test_report_roundtrip(client):
    r = client.post("/api/reports", json={"lat": 18.5, "lon": 73.85, "category": "waterlogging",
                                          "depth": "waist", "note": "test", "lang": "en"})
    assert r.status_code == 201 and r.json()["urgent"] is True
    rows = client.get("/api/reports?hours=1").json()
    assert any(x["id"] == r.json()["id"] for x in rows)


def test_model_card(client):
    card = client.get("/api/model-card").json()
    assert card["rain"]["deployed"] == "XGBoost"
