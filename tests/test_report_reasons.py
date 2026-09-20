from walle.report import status_reasons, _overall_status

OK = dict(health={"reachable": True, "unhealthy_count": 0}, audit={}, contract={}, resources={"git_status": {}, "disk_usage": {}})


def test_ok_has_no_reasons():
    assert status_reasons(**OK) == [] and _overall_status(**OK) == "ok"


def test_low_absolute_disk_is_a_reason_even_if_percent_ok():
    r = dict(OK, resources={"git_status": {}, "disk_usage": {"a": {"free_percent": 50.0, "free_bytes": 5 * 1024**3}}})
    assert any("low disk" in x for x in status_reasons(**r)) and _overall_status(**r) == "degraded"


def test_same_drive_reported_once():
    d = {"free_percent": 5.0, "free_bytes": 10 * 1024**3}
    r = dict(OK, resources={"git_status": {}, "disk_usage": {"a": d, "b": dict(d)}})
    assert len(status_reasons(**r)) == 1


def test_violation_is_critical():
    r = dict(OK, audit={"private_tier_violations": [1]})
    assert _overall_status(**r) == "critical"
