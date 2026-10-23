"""
Tests run without a ServiceNow account or network access. A fake client
records every call so the tests can check what would have been sent.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gpu_to_incident as g  # noqa: E402


class FakeClient:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.created = []
        self.queries = []

    def find(self, table, query, **_):
        self.queries.append((table, query))
        return self.existing

    def create(self, table, payload):
        self.created.append((table, payload))
        return {"number": f"INC{len(self.created):07d}"}


def gpu(index=0, status="OK", issues=None, name="NVIDIA H100 80GB HBM3"):
    return {"index": index, "name": name, "status": status, "issues": issues or []}


def test_normalize_both_vocabularies():
    assert g.normalize_status({"status": "OK"}) == "ok"
    assert g.normalize_status({"status": "pass"}) == "ok"
    assert g.normalize_status({"status": "WARN"}) == "warn"
    assert g.normalize_status({"status": "CRIT"}) == "crit"
    assert g.normalize_status({"status": "fail"}) == "crit"


def test_unknown_status_raises():
    with pytest.raises(ValueError):
        g.normalize_status({"index": 3, "status": "maybe"})


def test_ok_gpus_create_nothing():
    client = FakeClient()
    results = g.run([gpu(status="OK"), gpu(index=1, status="pass")], "dgx-01", client)
    assert [r[0] for r in results] == ["skip_ok", "skip_ok"]
    assert client.created == []


def test_warn_maps_to_moderate_urgency_and_impact():
    client = FakeClient()
    g.run([gpu(status="WARN", issues=["temperature 85C (warning)"])], "dgx-01", client)
    table, payload = client.created[0]
    assert table == "incident"
    assert payload["urgency"] == "2" and payload["impact"] == "2"
    assert "temperature 85C" in payload["description"]


def test_crit_maps_to_high_urgency_and_impact():
    client = FakeClient()
    g.run([gpu(status="CRIT", issues=["2 uncorrected ECC errors"])], "dgx-01", client)
    payload = client.created[0][1]
    assert payload["urgency"] == "1" and payload["impact"] == "1"
    assert "ECC" in payload["description"]


def test_toolkit_format_problems_field_is_read():
    client = FakeClient()
    g.run([{"index": 0, "name": "Tesla T4", "status": "fail",
            "problems": ["temperature 92C"]}], "lab-01", client)
    assert "temperature 92C" in client.created[0][1]["description"]


def test_existing_open_incident_prevents_duplicate():
    client = FakeClient(existing=[{"number": "INC0010001"}])
    results = g.run([gpu(status="CRIT")], "dgx-01", client)
    assert results == [("skip_existing", 0, "INC0010001")]
    assert client.created == []


def test_dedup_query_is_scoped_to_host_and_gpu():
    client = FakeClient()
    g.run([gpu(index=2, status="WARN")], "dgx-07", client)
    table, query = client.queries[0]
    assert table == "incident"
    assert "active=true" in query
    assert "[dgx-07] GPU 2" in query


def test_dry_run_creates_nothing():
    client = FakeClient()
    results = g.run([gpu(status="CRIT")], "dgx-01", client, dry_run=True)
    assert results[0][0] == "would_create"
    assert client.created == []
