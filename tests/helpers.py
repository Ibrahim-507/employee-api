"""Small helpers so API tests stay short. They talk to the API like a real client."""
from itertools import count

_counter = count(1)


def make_department(client, name="Engineering"):
    response = client.post("/departments", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def employee_payload(department_id, **overrides):
    n = next(_counter)
    payload = {
        "first_name": f"First{n}",
        "last_name": f"Last{n}",
        "work_email": f"person{n}@example.com",
        "hire_date": "2024-01-15",
        "department_id": department_id,
    }
    payload.update(overrides)
    return payload


def make_employee(client, department_id, **overrides):
    response = client.post("/employees", json=employee_payload(department_id, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def assert_error(response, status, code):
    """Every error must use the same format."""
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    return body["error"]
