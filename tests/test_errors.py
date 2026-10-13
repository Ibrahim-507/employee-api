from tests.helpers import assert_error


def test_unknown_route_uses_the_error_format(client):
    assert_error(client.get("/no-such-page"), 404, "not_found")


def test_wrong_method_uses_the_error_format(client):
    assert_error(client.put("/health"), 405, "method_not_allowed")


def test_validation_error_lists_each_problem(client):
    response = client.post("/employees", json={"work_email": "bad"})
    error = assert_error(response, 422, "validation_error")
    assert error["message"] == "Request validation failed"
    assert all({"field", "in", "message"} == set(d) for d in error["details"])
    assert {d["in"] for d in error["details"]} == {"body"}


def test_query_validation_error_says_where_the_problem_is(client):
    error = assert_error(client.get("/employees", params={"size": 500}), 422, "validation_error")
    assert error["details"][0]["in"] == "query"
    assert error["details"][0]["field"] == "size"
