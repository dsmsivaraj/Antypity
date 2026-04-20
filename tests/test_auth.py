"""Unit tests for AuthService and RBAC permission checks."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.auth import AuthService, ROLE_PERMISSIONS, generate_key, hash_key


class TestKeyHashing:
    def test_hash_is_deterministic(self):
        key = "act_test123"
        assert hash_key(key) == hash_key(key)

    def test_different_keys_different_hashes(self):
        assert hash_key("key-a") != hash_key("key-b")

    def test_generated_key_has_prefix(self):
        key = generate_key()
        assert key.startswith("act_")

    def test_generated_keys_are_unique(self):
        keys = {generate_key() for _ in range(100)}
        assert len(keys) == 100


class TestAuthServiceDisabled:
    def test_validate_key_returns_admin_when_disabled(self):
        db = MagicMock()
        db.is_configured = False
        service = AuthService(db=db, config_enabled=False)
        principal = service.validate_key("any-key")
        assert principal["role"] == "admin"

    def test_check_permission_passes_for_admin(self):
        db = MagicMock()
        db.is_configured = False
        service = AuthService(db=db, config_enabled=False)
        principal = {"role": "admin", "name": "test"}
        # Should not raise
        service.check_permission(principal, "execute")
        service.check_permission(principal, "keys:manage")


class TestAuthServiceEnabled:
    @pytest.fixture()
    def mock_db(self):
        db = MagicMock()
        db.is_configured = True
        return db

    @pytest.fixture()
    def service(self, mock_db):
        return AuthService(db=mock_db, config_enabled=True)

    def test_validate_key_calls_db(self, service, mock_db):
        mock_db.get_api_key_by_hash.return_value = {
            "id": "key-1", "name": "test", "role": "operator"
        }
        raw_key = generate_key()
        result = service.validate_key(raw_key)
        assert result["role"] == "operator"
        mock_db.get_api_key_by_hash.assert_called_once_with(hash_key(raw_key))

    def test_validate_key_returns_none_for_unknown(self, service, mock_db):
        mock_db.get_api_key_by_hash.return_value = None
        assert service.validate_key("unknown-key") is None

    def test_create_key_returns_raw_key(self, service, mock_db):
        mock_db.create_api_key.return_value = {
            "id": "new-id", "name": "ci-key", "role": "operator",
            "created_at": "2026-04-20T10:00:00+00:00", "is_active": True,
        }
        result = service.create_key(name="ci-key", role="operator")
        assert "key" in result
        assert result["key"].startswith("act_")

    def test_create_key_invalid_role_raises(self, service):
        with pytest.raises(ValueError, match="Invalid role"):
            service.create_key(name="bad", role="superadmin")

    def test_bootstrap_required_true_when_no_keys_exist(self, service, mock_db):
        mock_db.has_any_api_key.return_value = False
        assert service.bootstrap_required() is True

    def test_bootstrap_required_false_when_keys_exist(self, service, mock_db):
        mock_db.has_any_api_key.return_value = True
        assert service.bootstrap_required() is False

    def test_bootstrap_admin_creates_first_admin_key(self, service, mock_db):
        mock_db.has_any_api_key.return_value = False
        mock_db.create_api_key.return_value = {
            "id": "boot-id",
            "name": "bootstrap-admin",
            "role": "admin",
            "created_at": "2026-04-20T10:00:00+00:00",
            "is_active": True,
        }
        result = service.bootstrap_admin(
            provided_token="bootstrap-token",
            configured_token="bootstrap-token",
            name="bootstrap-admin",
        )
        assert result["role"] == "admin"
        assert "key" in result

    def test_bootstrap_admin_rejects_bad_token(self, service, mock_db):
        mock_db.has_any_api_key.return_value = False
        with pytest.raises(PermissionError):
            service.bootstrap_admin(
                provided_token="wrong-token",
                configured_token="bootstrap-token",
                name="bootstrap-admin",
            )

    def test_bootstrap_admin_rejects_when_keys_exist(self, service, mock_db):
        mock_db.has_any_api_key.return_value = True
        with pytest.raises(RuntimeError):
            service.bootstrap_admin(
                provided_token="bootstrap-token",
                configured_token="bootstrap-token",
                name="bootstrap-admin",
            )


class TestRBACPermissions:
    @pytest.fixture()
    def service(self):
        db = MagicMock()
        db.is_configured = True
        return AuthService(db=db, config_enabled=True)

    def test_admin_can_do_anything(self, service):
        principal = {"role": "admin"}
        # None of these should raise
        for perm in ["execute", "keys:manage", "metrics:read", "logs:read", "agents:read"]:
            service.check_permission(principal, perm)

    def test_operator_can_execute(self, service):
        principal = {"role": "operator"}
        service.check_permission(principal, "execute")

    def test_operator_cannot_manage_keys(self, service):
        principal = {"role": "operator"}
        with pytest.raises(HTTPException) as exc_info:
            service.check_permission(principal, "keys:manage")
        assert exc_info.value.status_code == 403

    def test_viewer_can_read_agents(self, service):
        principal = {"role": "viewer"}
        service.check_permission(principal, "agents:read")

    def test_viewer_cannot_execute(self, service):
        principal = {"role": "viewer"}
        with pytest.raises(HTTPException) as exc_info:
            service.check_permission(principal, "execute")
        assert exc_info.value.status_code == 403

    def test_viewer_cannot_manage_keys(self, service):
        principal = {"role": "viewer"}
        with pytest.raises(HTTPException):
            service.check_permission(principal, "keys:manage")

    def test_all_roles_defined(self):
        for role in ("admin", "operator", "viewer"):
            assert role in ROLE_PERMISSIONS
