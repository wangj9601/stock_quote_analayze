"""
前端三级权限控制单元测试
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.database import SessionLocal
from backend_api.models import FrontendRole, User
from backend_api.permissions import (
    build_permissions_response,
    get_role_permission_codes,
    resolve_user_role,
    user_has_permission,
    build_permission_tree,
)
from backend_api.permission_registry_data import PERMISSION_REGISTRY


def test_registry_not_empty():
    assert len(PERMISSION_REGISTRY) >= 7
    levels = {p["level"] for p in PERMISSION_REGISTRY}
    assert levels == {1, 2, 3}


def test_standard_role_has_permissions():
    db = SessionLocal()
    try:
        role = db.query(FrontendRole).filter(FrontendRole.code == "standard").first()
        assert role is not None
        codes = get_role_permission_codes(db, role)
        assert "channel.home" in codes
        assert "channel.screening" in codes
        assert len(codes) >= len(PERMISSION_REGISTRY)
    finally:
        db.close()


def test_anonymous_gets_standard_permissions():
    db = SessionLocal()
    try:
        resp = build_permissions_response(db, None)
        assert resp.role.code == "standard"
        assert "channel.home" in resp.permissions
    finally:
        db.close()


def test_permission_tree_structure():
    db = SessionLocal()
    try:
        tree = build_permission_tree(db)
        assert len(tree) >= 7
        screening = next((n for n in tree if n["code"] == "channel.screening"), None)
        assert screening is not None
        assert len(screening.get("children", [])) > 0
    finally:
        db.close()


def test_user_role_resolution():
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            return
        role = resolve_user_role(db, user)
        assert role is not None
        assert user_has_permission(db, user, "channel.home") or not get_role_permission_codes(db, role)
    finally:
        db.close()


def test_user_permission_override():
    from backend_api.models import UserPermission, FrontendPermission
    from backend_api.permissions import (
        set_user_effective_permissions,
        get_effective_permission_codes,
        clear_user_permission_overrides,
    )

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            return
        role_codes = set(get_effective_permission_codes(db, user))
        if not role_codes:
            return
        # 撤销一项角色默认权限
        target = "channel.screening" if "channel.screening" in role_codes else next(iter(role_codes))
        new_effective = role_codes - {target}
        set_user_effective_permissions(db, user, sorted(new_effective))
        db.refresh(user)
        effective = set(get_effective_permission_codes(db, user))
        assert target not in effective
        clear_user_permission_overrides(db, user.id)
        db.refresh(user)
        assert target in set(get_effective_permission_codes(db, user))
    finally:
        db.close()


if __name__ == "__main__":
    test_registry_not_empty()
    test_standard_role_has_permissions()
    test_anonymous_gets_standard_permissions()
    test_permission_tree_structure()
    test_user_role_resolution()
    test_user_permission_override()
    print("All permission tests passed.")
