import pytest
from fastapi import HTTPException

from app.deps import ensure_access, has_active_plan, is_locked, requires_active_plan
from app.models import SubscriptionStatus, User, UserRole


def make(status=SubscriptionStatus.INACTIVE, role=UserRole.STUDENT):
    return User(first_name="T", email="t@example.com", password_hash="x", role=role, subscription_status=status)


@pytest.mark.parametrize("status,expected", [
    (SubscriptionStatus.ACTIVE, True), (SubscriptionStatus.TRIAL, True),
    (SubscriptionStatus.EXPIRED, False), (SubscriptionStatus.INACTIVE, False),
])
def test_has_active_plan(status, expected):
    assert has_active_plan(make(status)) is expected


def test_admin_always_has_access():
    assert has_active_plan(make(role=UserRole.ADMIN))


def test_free_content_open_paid_content_locked():
    student = make()
    ensure_access(student, is_free=True)
    with pytest.raises(HTTPException) as e:
        ensure_access(student, is_free=False)
    assert e.value.status_code == 402
    assert is_locked(student, False) and not is_locked(student, True)
    ensure_access(make(SubscriptionStatus.ACTIVE), is_free=False)


def test_requires_active_plan_dependency():
    from app.deps import CurrentUser

    with pytest.raises(HTTPException):
        requires_active_plan(CurrentUser(make(SubscriptionStatus.EXPIRED), "sid"))
    assert requires_active_plan(CurrentUser(make(SubscriptionStatus.ACTIVE), "sid"))
