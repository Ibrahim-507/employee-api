from tests.helpers import assert_error, make_department, make_employee


def test_create_department(client):
    response = client.post(
        "/departments", json={"name": "  Engineering ", "description": "Builds things"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Engineering"
    assert body["description"] == "Builds things"
    assert body["is_active"] is True
    assert body["employee_count"] == 0


def test_create_department_rejects_empty_name(client):
    assert_error(client.post("/departments", json={"name": "  "}), 422, "validation_error")
    assert_error(client.post("/departments", json={}), 422, "validation_error")


def test_create_department_duplicate_is_409_ignoring_case(client):
    make_department(client, "Finance")
    response = client.post("/departments", json={"name": "FINANCE"})
    assert_error(response, 409, "department_name_exists")


def test_list_departments_with_employee_counts(client):
    eng = make_department(client, "Engineering")
    make_department(client, "HR")
    make_employee(client, eng["id"])
    leaver = make_employee(client, eng["id"])
    client.delete(f"/employees/{leaver['id']}")   # inactive people are not counted

    body = client.get("/departments").json()
    assert [d["name"] for d in body] == ["Engineering", "HR"]    # sorted by name
    counts = {d["name"]: d["employee_count"] for d in body}
    assert counts == {"Engineering": 1, "HR": 0}


def test_list_departments_empty(client):
    assert client.get("/departments").json() == []


def test_department_employees_are_paginated_and_filtered(client):
    eng = make_department(client, "Engineering")
    hr = make_department(client, "HR")
    for i in range(3):
        make_employee(client, eng["id"], first_name=f"Dev{i}")
    make_employee(client, eng["id"], first_name="Zed")
    make_employee(client, hr["id"], first_name="Dev9")

    page = client.get(f"/departments/{eng['id']}/employees", params={"size": 3}).json()
    assert page["total"] == 4
    assert page["pages"] == 2
    assert len(page["items"]) == 3
    assert all(e["department"]["id"] == eng["id"] for e in page["items"])

    searched = client.get(f"/departments/{eng['id']}/employees", params={"q": "dev"}).json()
    assert searched["total"] == 3


def test_department_employees_unknown_department_is_404(client):
    assert_error(client.get("/departments/99999/employees"), 404, "not_found")


def test_department_employees_hides_inactive(client):
    eng = make_department(client)
    emp = make_employee(client, eng["id"])
    client.delete(f"/employees/{emp['id']}")
    assert client.get(f"/departments/{eng['id']}/employees").json()["total"] == 0
    shown = client.get(
        f"/departments/{eng['id']}/employees", params={"include_inactive": True}
    ).json()
    assert shown["total"] == 1
