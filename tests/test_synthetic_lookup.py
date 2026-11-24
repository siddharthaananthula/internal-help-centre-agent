import asyncio


def test_synthetic_lookup_refuses_without_verified_session(monkeypatch):
    from mcp_server import lookup_service_status

    monkeypatch.delenv("VERIFIED_ACCOUNT_ID", raising=False)
    assert lookup_service_status("ACC-1001") == {"refused": True, "reason": "No verified account session"}


def test_synthetic_lookup_refuses_mismatch(monkeypatch):
    from mcp_server import lookup_service_status

    monkeypatch.setenv("VERIFIED_ACCOUNT_ID", "ACC-9999")
    assert lookup_service_status("ACC-1001")["refused"] is True


def test_synthetic_lookup_refuses_other_customer(monkeypatch):
    from mcp_server import lookup_service_status

    monkeypatch.setenv("VERIFIED_ACCOUNT_ID", "ACC-1001")
    assert lookup_service_status("ACC-1002")["refused"] is True


def test_synthetic_lookup_allows_match(monkeypatch):
    from mcp_server import lookup_service_status

    monkeypatch.setenv("VERIFIED_ACCOUNT_ID", "ACC-1001")
    assert lookup_service_status("ACC-1001")["status"] == "Active"


def test_model_cannot_supply_verified_account_id():
    from mcp_server import server

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    schema = tools["lookup_service_status"].inputSchema
    assert set(schema["properties"]) == {"account_id"}
