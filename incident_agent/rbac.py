"""Multi-tenant RBAC support.

Provides tenant isolation (separate memory banks per team) and role-based
access control for SOC teams. Each tenant gets its own Hindsight memory
bank, calibration history, and cost tracking.
"""
from __future__ import annotations

import hashlib
import os
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .models import utc_now


class Role(str, Enum):
    ANALYST = "analyst"          # Can analyze, retain, view own team's data
    SENIOR_ANALYST = "senior"    # Can override, approve auto-close, view calibration
    SOC_LEAD = "soc_lead"       # Can configure thresholds, enable auto-close, view all teams
    ADMIN = "admin"             # Full access, manage tenants and users


class Permission(str, Enum):
    ANALYZE = "analyze"
    RETAIN = "retain"
    OVERRIDE = "override"
    VIEW_CALIBRATION = "view_calibration"
    CONFIGURE_THRESHOLDS = "configure_thresholds"
    ENABLE_AUTO_CLOSE = "enable_auto_close"
    MANAGE_TENANTS = "manage_tenants"
    MANAGE_USERS = "manage_users"
    VIEW_ALL_TEAMS = "view_all_teams"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ANALYST: {
        Permission.ANALYZE,
        Permission.RETAIN,
    },
    Role.SENIOR_ANALYST: {
        Permission.ANALYZE,
        Permission.RETAIN,
        Permission.OVERRIDE,
        Permission.VIEW_CALIBRATION,
    },
    Role.SOC_LEAD: {
        Permission.ANALYZE,
        Permission.RETAIN,
        Permission.OVERRIDE,
        Permission.VIEW_CALIBRATION,
        Permission.CONFIGURE_THRESHOLDS,
        Permission.ENABLE_AUTO_CLOSE,
        Permission.VIEW_ALL_TEAMS,
    },
    Role.ADMIN: set(Permission),
}


class Tenant(BaseModel):
    """A tenant represents a team or organization with isolated memory."""
    tenant_id: str
    name: str
    memory_bank_id: str  # Hindsight bank ID for this tenant
    created_at: str = Field(default_factory=utc_now)
    settings: dict[str, Any] = Field(default_factory=dict)
    # Per-tenant threshold overrides (defaults to global if not set)
    strong_match_threshold: float | None = None
    bypass_confidence_threshold: float | None = None
    auto_close_enabled: bool = False


class User(BaseModel):
    """A user within a tenant."""
    user_id: str
    tenant_id: str
    email: str
    display_name: str
    role: Role
    created_at: str = Field(default_factory=utc_now)
    api_key_hash: str = ""  # SHA-256 of the API key


class AuthContext(BaseModel):
    """Resolved auth context for a request."""
    user: User
    tenant: Tenant
    permissions: set[Permission] = Field(default_factory=set)


class TenantRegistry:
    """In-memory tenant and user registry.

    Production would back this with a database. For now, supports
    programmatic registration and API-key-based lookup.
    """

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._users: dict[str, User] = {}
        self._api_keys: dict[str, str] = {}  # hash -> user_id
        self._setup_default_tenant()

    def _setup_default_tenant(self) -> None:
        """Create a default tenant for backward compatibility."""
        bank_id = os.getenv("HINDSIGHT_BANK_ID", "openrecall")
        default = Tenant(
            tenant_id="default",
            name="Default Team",
            memory_bank_id=bank_id,
        )
        self._tenants["default"] = default

        # Default admin user (no auth required in single-tenant mode)
        admin = User(
            user_id="default-admin",
            tenant_id="default",
            email="admin@openrecall.local",
            display_name="Default Admin",
            role=Role.ADMIN,
        )
        self._users["default-admin"] = admin

    def create_tenant(self, name: str, bank_id: str | None = None) -> Tenant:
        """Create a new tenant with its own memory bank."""
        tenant_id = hashlib.sha256(f"{name}-{time.time()}".encode()).hexdigest()[:12]
        if bank_id is None:
            bank_id = f"openrecall-{tenant_id}"
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            memory_bank_id=bank_id,
        )
        self._tenants[tenant_id] = tenant
        return tenant

    def create_user(
        self,
        tenant_id: str,
        email: str,
        display_name: str,
        role: Role,
    ) -> tuple[User, str]:
        """Create a user and return (user, api_key)."""
        if tenant_id not in self._tenants:
            raise ValueError(f"Tenant {tenant_id} not found")

        user_id = hashlib.sha256(f"{email}-{time.time()}".encode()).hexdigest()[:16]
        api_key = f"or_{hashlib.sha256(os.urandom(32)).hexdigest()[:32]}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            display_name=display_name,
            role=role,
            api_key_hash=key_hash,
        )
        self._users[user_id] = user
        self._api_keys[key_hash] = user_id
        return user, api_key

    def authenticate(self, api_key: str) -> AuthContext | None:
        """Resolve an API key to an AuthContext."""
        if not api_key:
            # Single-tenant fallback: return default admin
            default_user = self._users.get("default-admin")
            default_tenant = self._tenants.get("default")
            if default_user and default_tenant:
                return AuthContext(
                    user=default_user,
                    tenant=default_tenant,
                    permissions=ROLE_PERMISSIONS[default_user.role],
                )
            return None

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        user_id = self._api_keys.get(key_hash)
        if not user_id:
            return None

        user = self._users.get(user_id)
        if not user:
            return None

        tenant = self._tenants.get(user.tenant_id)
        if not tenant:
            return None

        return AuthContext(
            user=user,
            tenant=tenant,
            permissions=ROLE_PERMISSIONS[user.role],
        )

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def list_tenants(self) -> list[Tenant]:
        return list(self._tenants.values())

    def check_permission(self, ctx: AuthContext, permission: Permission) -> bool:
        return permission in ctx.permissions
