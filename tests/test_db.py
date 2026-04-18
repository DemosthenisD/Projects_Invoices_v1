"""Smoke tests for backend/db.py using an isolated temp database."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    """Redirect DB_PATH to a throwaway file for each test."""
    db_file = str(tmp_path / "test.db")
    import shared.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", db_file)
    import backend.db as db
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.init_db()
    return db


def test_client_add_and_get(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme", name_for_invoices="Acme Ltd", client_code="ACM", vat_number="CY123")
    clients = db.get_clients()
    assert len(clients) == 1
    assert clients[0].id == cid
    assert clients[0].name == "Acme"
    assert clients[0].vat_number == "CY123"


def test_client_add_duplicate_is_idempotent(tmp_db):
    db = tmp_db
    id1 = db.add_client("Acme")
    id2 = db.add_client("Acme")
    assert id1 == id2
    assert len(db.get_clients()) == 1


def test_client_update_and_delete(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    db.update_client(cid, name_for_invoices="Acme Corp", client_code="A1", vat_number="CY999")
    c = db.get_clients()[0]
    assert c.name_for_invoices == "Acme Corp"
    assert c.vat_number == "CY999"
    db.delete_client(cid)
    assert db.get_clients() == []


def test_address_add_and_get(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    aid = db.add_address(cid, "123 Main St")
    addrs = db.get_addresses(cid)
    assert len(addrs) == 1
    assert addrs[0].id == aid
    assert addrs[0].address == "123 Main St"


def test_address_delete(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    aid = db.add_address(cid, "123 Main St")
    db.delete_address(aid)
    assert db.get_addresses(cid) == []


def test_project_add_and_filter(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    pid = db.add_project(cid, "Alpha", description="Desc", vat_pct=19.0, status="Active")
    db.add_project(cid, "Beta", status="Inactive")
    active = db.get_projects(client_id=cid, status="Active")
    assert len(active) == 1
    assert active[0].id == pid
    assert active[0].name == "Alpha"


def test_project_update_and_delete(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    pid = db.add_project(cid, "Alpha")
    db.update_project(pid, description="Updated", vat_pct=0.0, template="t2", status="Inactive")
    proj = db.get_projects(client_id=cid)[0]
    assert proj.description == "Updated"
    assert proj.vat_pct == 0.0
    db.delete_project(pid)
    assert db.get_projects(client_id=cid) == []


def test_invoice_add_and_get(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    iid = db.add_invoice(
        client_id=cid, invoice_number="1", year=2026, date="2026-04-18",
        amount=1000.0, vat_amount=190.0, vat_pct=19.0,
    )
    invoices = db.get_invoices()
    assert len(invoices) == 1
    assert invoices[0].id == iid
    assert invoices[0].amount == 1000.0


def test_get_next_invoice_number(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    assert db.get_next_invoice_number(2026) == 1
    db.add_invoice(cid, "1", 2026, "2026-04-18", 1000.0, 190.0)
    assert db.get_next_invoice_number(2026) == 2
    assert db.get_next_invoice_number(2025) == 1


def test_pipeline_upsert(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme")
    pid = db.add_project(cid, "Alpha")
    db.upsert_pipeline(pid, stage="Proposal", value=5000.0)
    entries = db.get_pipeline()
    assert len(entries) == 1
    assert entries[0]["stage"] == "Proposal"
    assert entries[0]["value"] == 5000.0
    db.upsert_pipeline(pid, stage="Won", value=6000.0)
    entries = db.get_pipeline()
    assert len(entries) == 1
    assert entries[0]["stage"] == "Won"


# ---------------------------------------------------------------------------
# Project Code tests
# ---------------------------------------------------------------------------

def test_project_code_add_and_get(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme", client_code="0478ACM")
    pid = db.add_project(cid, "Alpha")
    code_id = db.add_project_code(pid, "0478ACM", "01", name="Alpha Phase 1", budget_amount=10000.0)
    codes = db.get_project_codes(project_id=pid)
    assert len(codes) == 1
    assert codes[0].id == code_id
    assert codes[0].client_code == "0478ACM"
    assert codes[0].client_suffix == "01"
    assert codes[0].budget_amount == 10000.0


def test_project_code_lookup_by_keys(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme", client_code="0478ACM")
    pid = db.add_project(cid, "Alpha")
    db.add_project_code(pid, "0478ACM", "01")
    pc = db.get_project_code_by_keys("0478ACM", "01")
    assert pc is not None
    assert pc.project_id == pid
    assert db.get_project_code_by_keys("0478ACM", "99") is None


def test_project_code_update(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme", client_code="0478ACM")
    pid = db.add_project(cid, "Alpha")
    code_id = db.add_project_code(pid, "0478ACM", "01", budget_amount=5000.0)
    db.update_project_code(code_id, name="Updated", description="Desc", budget_amount=9000.0, status="Active")
    codes = db.get_project_codes(project_id=pid)
    assert codes[0].name == "Updated"
    assert codes[0].budget_amount == 9000.0


def test_project_code_delete_guard(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme", client_code="0478ACM")
    pid = db.add_project(cid, "Alpha")
    code_id = db.add_project_code(pid, "0478ACM", "01")
    entry = {
        "period": "202206", "emp_nbr": "001", "consultant": "DD",
        "client_code": "0478ACM", "client_suffix": "01",
        "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
        "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0,
        "batch_ref": "test",
    }
    db.add_time_entries_bulk([entry])
    import pytest
    with pytest.raises(ValueError):
        db.delete_project_code(code_id)


# ---------------------------------------------------------------------------
# Time Entry tests
# ---------------------------------------------------------------------------

def _setup_project_with_code(db):
    cid = db.add_client("Acme", client_code="0478ACM")
    pid = db.add_project(cid, "Alpha")
    db.add_project_code(pid, "0478ACM", "01", budget_amount=10000.0)
    return cid, pid


def test_time_entries_bulk_insert(tmp_db):
    db = tmp_db
    _, pid = _setup_project_with_code(db)
    entries = [
        {"period": "202206", "emp_nbr": "001", "consultant": "DD",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
         "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "b1"},
        {"period": "202207", "emp_nbr": "001", "consultant": "DD",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 5, "non_z_hours": 5, "z_hours": 0,
         "total_charges": 600, "non_z_charges": 600, "z_charges": 0, "batch_ref": "b1"},
    ]
    result = db.add_time_entries_bulk(entries)
    assert result["inserted"] == 2
    assert result["skipped"] == 0
    assert result["unmatched"] == 0
    assert len(db.get_time_entries(project_id=pid)) == 2


def test_time_entries_duplicate_skipped(tmp_db):
    db = tmp_db
    _setup_project_with_code(db)
    entry = {"period": "202206", "emp_nbr": "001", "consultant": "DD",
              "client_code": "0478ACM", "client_suffix": "01",
              "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
              "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "b1"}
    db.add_time_entries_bulk([entry])
    result = db.add_time_entries_bulk([entry])
    assert result["skipped"] == 1
    assert result["inserted"] == 0


def test_time_entries_unmatched(tmp_db):
    db = tmp_db
    _setup_project_with_code(db)
    entry = {"period": "202206", "emp_nbr": "001", "consultant": "DD",
              "client_code": "UNKNOWN", "client_suffix": "99",
              "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
              "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "b1"}
    result = db.add_time_entries_bulk([entry])
    assert result["unmatched"] == 1
    assert result["inserted"] == 0


def test_delete_time_batch(tmp_db):
    db = tmp_db
    _, pid = _setup_project_with_code(db)
    entries = [
        {"period": "202206", "emp_nbr": "001", "consultant": "DD",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
         "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "batch_A"},
    ]
    db.add_time_entries_bulk(entries)
    deleted = db.delete_time_batch("batch_A")
    assert deleted == 1
    assert db.get_time_entries(project_id=pid) == []


def test_get_time_summary(tmp_db):
    db = tmp_db
    _, pid = _setup_project_with_code(db)
    entries = [
        {"period": "202206", "emp_nbr": "001", "consultant": "DD",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
         "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "b1"},
    ]
    db.add_time_entries_bulk(entries)
    summary = db.get_time_summary(pid)
    assert len(summary) == 1
    assert summary[0]["non_z_charges"] == 1000
    assert summary[0]["write_off_amount"] == 0
    assert summary[0]["net_charges"] == 1000


# ---------------------------------------------------------------------------
# Write-off tests
# ---------------------------------------------------------------------------

def test_write_off_adhoc(tmp_db):
    db = tmp_db
    _, pid = _setup_project_with_code(db)
    code_id = db.get_project_codes(project_id=pid)[0].id
    wo_id = db.add_write_off_adhoc(pid, code_id, "001", "DD", 200.0, "Client discount")
    wos = db.get_write_offs(project_id=pid)
    assert len(wos) == 1
    assert wos[0].id == wo_id
    assert wos[0].amount == 200.0
    assert wos[0].allocation_type == "adhoc"


def test_write_off_project_prorata(tmp_db):
    db = tmp_db
    cid = db.add_client("Acme", client_code="0478ACM")
    pid = db.add_project(cid, "Alpha")
    db.add_project_code(pid, "0478ACM", "01", budget_amount=10000.0)
    entries = [
        {"period": "202206", "emp_nbr": "001", "consultant": "DD",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
         "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "b1"},
        {"period": "202206", "emp_nbr": "002", "consultant": "JK",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 4, "non_z_hours": 4, "z_hours": 0,
         "total_charges": 500, "non_z_charges": 500, "z_charges": 0, "batch_ref": "b1"},
    ]
    db.add_time_entries_bulk(entries)
    ids = db.add_write_off_project(pid, 300.0, "Budget overrun")
    wos = db.get_write_offs(project_id=pid)
    assert len(wos) == 2
    total_written = sum(w.amount for w in wos)
    assert abs(total_written - 300.0) < 0.01


def test_write_off_reverse(tmp_db):
    db = tmp_db
    _, pid = _setup_project_with_code(db)
    code_id = db.get_project_codes(project_id=pid)[0].id
    wo_id = db.add_write_off_adhoc(pid, code_id, "001", "DD", 200.0, "Test")
    db.reverse_write_off(wo_id, "Reversed by user")
    active = db.get_write_offs(project_id=pid, include_reversed=False)
    assert active == []
    all_wos = db.get_write_offs(project_id=pid, include_reversed=True)
    assert all_wos[0].reversed == 1
    assert all_wos[0].reversed_reason == "Reversed by user"


def test_time_summary_reflects_write_offs(tmp_db):
    db = tmp_db
    _, pid = _setup_project_with_code(db)
    code_id = db.get_project_codes(project_id=pid)[0].id
    entries = [
        {"period": "202206", "emp_nbr": "001", "consultant": "DD",
         "client_code": "0478ACM", "client_suffix": "01",
         "total_hours": 8, "non_z_hours": 8, "z_hours": 0,
         "total_charges": 1000, "non_z_charges": 1000, "z_charges": 0, "batch_ref": "b1"},
    ]
    db.add_time_entries_bulk(entries)
    db.add_write_off_adhoc(pid, code_id, "001", "DD", 200.0, "Discount")
    summary = db.get_time_summary(pid)
    assert summary[0]["write_off_amount"] == 200.0
    assert summary[0]["net_charges"] == 800.0
