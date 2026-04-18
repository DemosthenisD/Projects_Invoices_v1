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
