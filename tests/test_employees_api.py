from datetime import date, timedelta

from tests.helpers import (
    assert_error,
    employee_payload,
    make_department,
    make_employee,
)


# ============================================================ POST /employees

def test_create_employee(client):
    dept = make_department(client)
    response = client.post(
        "/employees",
        json={
            "first_name": "  Ada ",
            "last_name": "Lovelace",
            "work_email": "Ada.Lovelace@Example.com",
            "phone": "98400 12345",
            "hire_date": "2024-03-01",
            "department_id": dept["id"],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["first_name"] == "Ada"                       # trimmed
    assert body["work_email"] == "ada.lovelace@example.com"  # lowercase
    assert body["is_active"] is True
    assert body["manager_id"] is None
    assert body["department"] == {"id": dept["id"], "name": "Engineering"}
    assert body["created_at"] and body["updated_at"]


def test_create_employee_with_manager(client):
    dept = make_department(client)
    boss = make_employee(client, dept["id"])
    worker = make_employee(client, dept["id"], manager_id=boss["id"])
    assert worker["manager_id"] == boss["id"]


def test_create_rejects_invalid_email(client):
    dept = make_department(client)
    response = client.post(
        "/employees", json=employee_payload(dept["id"], work_email="not-an-email")
    )
    error = assert_error(response, 422, "validation_error")
    assert error["details"][0]["field"] == "work_email"


def test_create_rejects_empty_names(client):
    dept = make_department(client)
    for field in ("first_name", "last_name"):
        response = client.post("/employees", json=employee_payload(dept["id"], **{field: "   "}))
        error = assert_error(response, 422, "validation_error")
        assert error["details"][0]["field"] == field


def test_create_rejects_future_hire_date(client):
    dept = make_department(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = client.post("/employees", json=employee_payload(dept["id"], hire_date=tomorrow))
    error = assert_error(response, 422, "validation_error")
    assert error["details"][0]["field"] == "hire_date"


def test_create_accepts_today_as_hire_date(client):
    dept = make_department(client)
    response = client.post(
        "/employees", json=employee_payload(dept["id"], hire_date=date.today().isoformat())
    )
    assert response.status_code == 201


def test_create_rejects_bad_date_format(client):
    dept = make_department(client)
    response = client.post("/employees", json=employee_payload(dept["id"], hire_date="15-01-2024"))
    assert_error(response, 422, "validation_error")


def test_create_rejects_missing_fields(client):
    response = client.post("/employees", json={"first_name": "Only"})
    error = assert_error(response, 422, "validation_error")
    fields = {d["field"] for d in error["details"]}
    assert {"last_name", "work_email", "hire_date", "department_id"} <= fields


def test_create_rejects_unknown_fields(client):
    dept = make_department(client)
    response = client.post("/employees", json=employee_payload(dept["id"], salary=100))
    assert_error(response, 422, "validation_error")


def test_create_duplicate_email_is_409_even_with_different_case(client):
    dept = make_department(client)
    make_employee(client, dept["id"], work_email="same@example.com")
    response = client.post(
        "/employees", json=employee_payload(dept["id"], work_email="SAME@example.com")
    )
    assert_error(response, 409, "email_already_exists")


def test_create_with_unknown_department_is_422(client):
    response = client.post("/employees", json=employee_payload(99999))
    assert_error(response, 422, "invalid_reference")


def test_create_with_unknown_manager_is_422(client):
    dept = make_department(client)
    response = client.post("/employees", json=employee_payload(dept["id"], manager_id=99999))
    assert_error(response, 422, "invalid_reference")


def test_create_with_inactive_manager_is_422(client):
    dept = make_department(client)
    gone = make_employee(client, dept["id"])
    client.delete(f"/employees/{gone['id']}")
    response = client.post("/employees", json=employee_payload(dept["id"], manager_id=gone["id"]))
    assert_error(response, 422, "invalid_reference")


# ====================================================== GET /employees/{id}

def test_get_employee(client):
    dept = make_department(client)
    created = make_employee(client, dept["id"])
    response = client.get(f"/employees/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_employee_is_404(client):
    response = client.get("/employees/99999")
    error = assert_error(response, 404, "not_found")
    assert "99999" in error["message"]


def test_get_employee_with_bad_id_is_422(client):
    response = client.get("/employees/abc")
    assert_error(response, 422, "validation_error")


# ============================================================= GET /employees

def test_list_returns_page_with_total(client):
    dept = make_department(client)
    for _ in range(5):
        make_employee(client, dept["id"])

    first = client.get("/employees", params={"page": 1, "size": 2}).json()
    assert len(first["items"]) == 2
    assert (first["total"], first["page"], first["size"], first["pages"]) == (5, 1, 2, 3)

    last = client.get("/employees", params={"page": 3, "size": 2}).json()
    assert len(last["items"]) == 1
    assert last["total"] == 5


def test_list_pages_do_not_overlap(client):
    dept = make_department(client)
    for _ in range(5):
        make_employee(client, dept["id"])
    seen = []
    for page in (1, 2, 3):
        body = client.get("/employees", params={"page": page, "size": 2}).json()
        seen += [e["id"] for e in body["items"]]
    assert len(seen) == len(set(seen)) == 5


def test_list_page_past_the_end_is_empty_but_keeps_total(client):
    dept = make_department(client)
    make_employee(client, dept["id"])
    body = client.get("/employees", params={"page": 5, "size": 10}).json()
    assert body["items"] == []
    assert body["total"] == 1


def test_list_empty(client):
    body = client.get("/employees").json()
    assert body == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}


def test_list_rejects_bad_paging(client):
    for params in ({"page": 0}, {"size": 0}, {"size": 101}, {"page": "x"}):
        assert_error(client.get("/employees", params=params), 422, "validation_error")


def test_list_filters_by_department_ignoring_case(client):
    eng = make_department(client, "Engineering")
    hr = make_department(client, "HR")
    make_employee(client, eng["id"])
    make_employee(client, eng["id"])
    make_employee(client, hr["id"])

    body = client.get("/employees", params={"department": "engineering"}).json()
    assert body["total"] == 2
    assert {e["department"]["name"] for e in body["items"]} == {"Engineering"}

    assert client.get("/employees", params={"department": "Nowhere"}).json()["total"] == 0


def test_list_search_by_first_name_last_name_email_and_full_name(client):
    dept = make_department(client)
    make_employee(client, dept["id"], first_name="Ada", last_name="Lovelace",
                  work_email="ada@example.com")
    make_employee(client, dept["id"], first_name="Alan", last_name="Turing",
                  work_email="alan@example.com")

    def search(q):
        return [e["last_name"] for e in client.get("/employees", params={"q": q}).json()["items"]]

    assert search("ada") == ["Lovelace"]
    assert search("TURING") == ["Turing"]
    assert search("alan@example") == ["Turing"]
    assert search("Ada Lovelace") == ["Lovelace"]
    assert search("ovel") == ["Lovelace"]                    # partial match inside a word
    assert sorted(search("a")) == ["Lovelace", "Turing"]
    assert search("zzz") == []


def test_search_treats_percent_and_underscore_literally(client):
    dept = make_department(client)
    make_employee(client, dept["id"], first_name="Plain", last_name="Name")
    assert client.get("/employees", params={"q": "%"}).json()["total"] == 0
    assert client.get("/employees", params={"q": "_"}).json()["total"] == 0


def test_pagination_filter_and_search_work_together(client):
    eng = make_department(client, "Engineering")
    hr = make_department(client, "HR")
    for i in range(5):
        make_employee(client, eng["id"], first_name=f"Dev{i}", last_name="Smith")
    make_employee(client, eng["id"], first_name="Other", last_name="Jones")
    make_employee(client, hr["id"], first_name="Dev9", last_name="Smith")

    body = client.get(
        "/employees",
        params={"department": "Engineering", "q": "Dev", "page": 2, "size": 2},
    ).json()
    assert body["total"] == 5          # total reflects the filters, not the whole table
    assert body["pages"] == 3
    assert len(body["items"]) == 2
    assert all(e["department"]["name"] == "Engineering" for e in body["items"])
    assert all(e["first_name"].startswith("Dev") for e in body["items"])


def test_list_hides_inactive_unless_asked(client):
    dept = make_department(client)
    keep = make_employee(client, dept["id"])
    leave = make_employee(client, dept["id"])
    client.delete(f"/employees/{leave['id']}")

    ids = [e["id"] for e in client.get("/employees").json()["items"]]
    assert ids == [keep["id"]]

    body = client.get("/employees", params={"include_inactive": True}).json()
    assert body["total"] == 2


# ======================================================== PATCH /employees/{id}

def test_patch_changes_only_the_sent_fields(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"], first_name="Old", last_name="Name")
    response = client.patch(f"/employees/{emp['id']}", json={"first_name": "New"})
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "New"
    assert body["last_name"] == "Name"
    assert body["work_email"] == emp["work_email"]


def test_patch_can_move_department(client):
    eng = make_department(client, "Engineering")
    hr = make_department(client, "HR")
    emp = make_employee(client, eng["id"])
    body = client.patch(f"/employees/{emp['id']}", json={"department_id": hr["id"]}).json()
    assert body["department"]["name"] == "HR"


def test_patch_empty_body_changes_nothing(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])
    response = client.patch(f"/employees/{emp['id']}", json={})
    assert response.status_code == 200
    assert response.json()["first_name"] == emp["first_name"]


def test_patch_email_is_lowercased_and_must_stay_unique(client):
    dept = make_department(client)
    a = make_employee(client, dept["id"], work_email="a@example.com")
    make_employee(client, dept["id"], work_email="b@example.com")

    ok = client.patch(f"/employees/{a['id']}", json={"work_email": "NEW@Example.com"})
    assert ok.json()["work_email"] == "new@example.com"

    clash = client.patch(f"/employees/{a['id']}", json={"work_email": "b@example.com"})
    assert_error(clash, 409, "email_already_exists")


def test_patch_can_keep_own_email(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"], work_email="me@example.com")
    response = client.patch(f"/employees/{emp['id']}", json={"work_email": "me@example.com"})
    assert response.status_code == 200


def test_patch_validates_input(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])
    url = f"/employees/{emp['id']}"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    for bad in (
        {"work_email": "nope"},
        {"first_name": ""},
        {"hire_date": tomorrow},
        {"first_name": None},
        {"department_id": None},
        {"unknown_field": 1},
    ):
        assert_error(client.patch(url, json=bad), 422, "validation_error")


def test_patch_unknown_department_is_422(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])
    response = client.patch(f"/employees/{emp['id']}", json={"department_id": 99999})
    assert_error(response, 422, "invalid_reference")


def test_patch_unknown_employee_is_404(client):
    assert_error(client.patch("/employees/99999", json={"first_name": "X"}), 404, "not_found")


def test_patch_sets_and_clears_manager(client):
    dept = make_department(client)
    boss = make_employee(client, dept["id"])
    emp = make_employee(client, dept["id"])
    url = f"/employees/{emp['id']}"

    assert client.patch(url, json={"manager_id": boss["id"]}).json()["manager_id"] == boss["id"]
    assert client.patch(url, json={"manager_id": None}).json()["manager_id"] is None


def test_patch_employee_cannot_be_own_manager(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])
    response = client.patch(f"/employees/{emp['id']}", json={"manager_id": emp["id"]})
    assert_error(response, 422, "invalid_manager")


def test_patch_cannot_create_a_management_loop(client):
    dept = make_department(client)
    ceo = make_employee(client, dept["id"])
    mid = make_employee(client, dept["id"], manager_id=ceo["id"])
    low = make_employee(client, dept["id"], manager_id=mid["id"])

    # making the CEO report to someone below them would be a loop
    for below in (mid, low):
        response = client.patch(f"/employees/{ceo['id']}", json={"manager_id": below["id"]})
        assert_error(response, 422, "invalid_manager")


def test_patch_can_reactivate(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])
    client.delete(f"/employees/{emp['id']}")
    body = client.patch(f"/employees/{emp['id']}", json={"is_active": True}).json()
    assert body["is_active"] is True


# ====================================================== DELETE /employees/{id}

def test_delete_is_a_soft_delete(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])

    response = client.delete(f"/employees/{emp['id']}")
    assert response.status_code == 204
    assert response.content == b""

    # the record still exists, just inactive
    body = client.get(f"/employees/{emp['id']}").json()
    assert body["is_active"] is False
    assert emp["id"] not in [e["id"] for e in client.get("/employees").json()["items"]]


def test_delete_twice_is_fine(client):
    dept = make_department(client)
    emp = make_employee(client, dept["id"])
    assert client.delete(f"/employees/{emp['id']}").status_code == 204
    assert client.delete(f"/employees/{emp['id']}").status_code == 204


def test_delete_unknown_employee_is_404(client):
    assert_error(client.delete("/employees/99999"), 404, "not_found")


def test_cannot_delete_manager_with_active_reports(client):
    dept = make_department(client)
    boss = make_employee(client, dept["id"])
    worker = make_employee(client, dept["id"], manager_id=boss["id"])

    assert_error(client.delete(f"/employees/{boss['id']}"), 409, "has_active_reports")

    # after the report leaves (or gets a new manager) it works
    client.delete(f"/employees/{worker['id']}")
    assert client.delete(f"/employees/{boss['id']}").status_code == 204


# ================================================== GET /employees/{id}/team

def test_team_lists_direct_reports_only(client):
    dept = make_department(client)
    ceo = make_employee(client, dept["id"])
    mgr = make_employee(client, dept["id"], manager_id=ceo["id"])
    dev1 = make_employee(client, dept["id"], manager_id=mgr["id"])
    dev2 = make_employee(client, dept["id"], manager_id=mgr["id"])

    team = client.get(f"/employees/{mgr['id']}/team").json()
    assert {e["id"] for e in team} == {dev1["id"], dev2["id"]}

    ceo_team = client.get(f"/employees/{ceo['id']}/team").json()
    assert [e["id"] for e in ceo_team] == [mgr["id"]]     # not the grandchildren

    assert client.get(f"/employees/{dev1['id']}/team").json() == []


def test_team_hides_inactive_unless_asked(client):
    dept = make_department(client)
    boss = make_employee(client, dept["id"])
    stays = make_employee(client, dept["id"], manager_id=boss["id"])
    leaves = make_employee(client, dept["id"], manager_id=boss["id"])
    client.delete(f"/employees/{leaves['id']}")

    assert [e["id"] for e in client.get(f"/employees/{boss['id']}/team").json()] == [stays["id"]]
    both = client.get(f"/employees/{boss['id']}/team", params={"include_inactive": True}).json()
    assert len(both) == 2


def test_team_of_unknown_employee_is_404(client):
    assert_error(client.get("/employees/99999/team"), 404, "not_found")
