"""Tests for anonmail alias behavior when user is deactivated or deleted"""

import pytest
from mailu import models


TOKEN = 'a' * 32


@pytest.fixture
def setup_user_with_aliases(app):
    """Create a user with multiple anonmail aliases and return their identifiers"""
    def _setup():
        with app.app_context():
            # Create domain
            domain = models.Domain(name='example.com', anonmail_enabled=True)
            models.db.session.add(domain)
            models.db.session.commit()

            # Create user
            user = models.User(
                localpart='testuser',
                domain_name='example.com'
            )
            user.set_password('password')
            models.db.session.add(user)
            models.db.session.commit()

            user_email = user.email  # Store the email string before session closes

            # Create multiple anonmail aliases for this user
            alias_emails = []
            for i in range(3):
                alias = models.Alias(
                    localpart=f'anon{i}',
                    domain_name='example.com',
                    destination=['testuser@example.com'],
                    owner_email=user_email,
                    hostname=f'site{i}.com'
                )
                models.db.session.add(alias)
                models.db.session.commit()
                alias_emails.append(alias.email)

            return user_email, alias_emails
    return _setup


class TestUserDeactivation:
    """Test alias behavior when user is deactivated (enabled = False)"""

    def test_deactivation_stops_resolving_anonmail_aliases(self, app, setup_user_with_aliases):
        """When a user is deactivated, their anonmail aliases should stop resolving,
        but alias.disabled should remain unchanged (independent flag)."""
        user_email, alias_emails = setup_user_with_aliases()

        with app.app_context():
            # Verify aliases are enabled before deactivation
            for alias_email in alias_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                assert alias_obj is not None
                assert alias_obj.disabled is False

            # Get the user and deactivate them
            user_obj = models.db.session.get(models.User, user_email)
            user_obj.enabled = False
            models.db.session.commit()

            # alias.disabled should remain False — the flags are independent
            for alias_email in alias_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                assert alias_obj is not None
                assert alias_obj.disabled is False, (
                    f"Alias {alias_email}: alias.disabled should not be touched when owner is deactivated"
                )

    def test_deactivation_only_affects_owned_aliases(self, app, setup_user_with_aliases):
        """Deactivating a user should only stop resolution of their owned aliases"""
        user1_email, aliases1_emails = setup_user_with_aliases()

        with app.app_context():
            # Create second user with their own aliases
            user2 = models.User(
                localpart='otheruser',
                domain_name='example.com'
            )
            user2.set_password('password')
            models.db.session.add(user2)
            models.db.session.commit()

            alias2 = models.Alias(
                localpart='anon-other',
                domain_name='example.com',
                destination=['otheruser@example.com'],
                owner_email=user2.email
            )
            models.db.session.add(alias2)
            models.db.session.commit()
            alias2_email = alias2.email
            alias2_localpart = alias2.localpart

            # Deactivate first user
            user1_obj = models.db.session.get(models.User, user1_email)
            user1_obj.enabled = False
            models.db.session.commit()

            # Verify first user's aliases no longer resolve
            for alias_email in aliases1_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                assert alias_obj.disabled is False  # flag is independent
                resolved = models.Alias.resolve(alias_obj.localpart, 'example.com')
                assert resolved is None, f"Alias {alias_email} should not resolve when owner is disabled"

            # Verify second user's alias still resolves
            resolved2 = models.Alias.resolve(alias2_localpart, 'example.com')
            assert resolved2 is not None

    def test_disabled_aliases_not_resolved(self, app, setup_user_with_aliases):
        """Disabled aliases should not be resolved for email delivery"""
        user_email, alias_emails = setup_user_with_aliases()

        with app.app_context():
            # Get first alias and verify it can be resolved
            alias_localpart = models.Alias.query.filter_by(email=alias_emails[0]).first().localpart
            resolved = models.Alias.resolve(alias_localpart, 'example.com')
            assert resolved is not None

            # Deactivate user
            user_obj = models.db.session.get(models.User, user_email)
            user_obj.enabled = False
            models.db.session.commit()

            # Verify alias can no longer be resolved
            resolved = models.Alias.resolve(alias_localpart, 'example.com')
            assert resolved is None

    def test_reactivation_restores_alias_resolution(self, app, setup_user_with_aliases):
        """Re-enabling a user should automatically restore alias resolution"""
        user_email, alias_emails = setup_user_with_aliases()

        with app.app_context():
            # Deactivate user
            user_obj = models.db.session.get(models.User, user_email)
            user_obj.enabled = False
            models.db.session.commit()

            # Verify aliases no longer resolve while owner is disabled
            for alias_email in alias_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                resolved = models.Alias.resolve(alias_obj.localpart, 'example.com')
                assert resolved is None

            # Re-enable user
            user_obj = models.db.session.get(models.User, user_email)
            user_obj.enabled = True
            models.db.session.commit()

            # Aliases should resolve again without any manual intervention
            for alias_email in alias_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                resolved = models.Alias.resolve(alias_obj.localpart, 'example.com')
                assert resolved is not None, (
                    f"Alias {alias_email} should resolve again after owner is re-enabled"
                )


class TestUserDeletion:
    """Test alias behavior when user is permanently deleted"""

    def test_deletion_removes_anonmail_aliases(self, app, setup_user_with_aliases):
        """When a user is deleted, their anonmail aliases should be deleted"""
        user_email, alias_emails = setup_user_with_aliases()

        with app.app_context():
            # Verify aliases exist before deletion
            for alias_email in alias_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                assert alias_obj is not None

            # Delete the user
            user_obj = models.db.session.get(models.User, user_email)
            models.db.session.delete(user_obj)
            models.db.session.commit()

            # Verify all aliases are now deleted
            for alias_email in alias_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                assert alias_obj is None, f"Alias {alias_email} should be deleted"

    def test_deletion_only_affects_owned_aliases(self, app, setup_user_with_aliases):
        """Deleting a user should only delete their owned aliases"""
        user1_email, aliases1_emails = setup_user_with_aliases()

        with app.app_context():
            # Create regular (non-owned) alias pointing to this user
            regular_alias = models.Alias(
                localpart='regular',
                domain_name='example.com',
                destination=['testuser@example.com'],
                owner_email=None  # Not owned by any user
            )
            models.db.session.add(regular_alias)
            models.db.session.commit()
            regular_alias_email = regular_alias.email

            # Create second user with their own aliases
            user2 = models.User(
                localpart='otheruser',
                domain_name='example.com'
            )
            user2.set_password('password')
            models.db.session.add(user2)
            models.db.session.commit()

            alias2 = models.Alias(
                localpart='anon-other',
                domain_name='example.com',
                destination=['otheruser@example.com'],
                owner_email=user2.email
            )
            models.db.session.add(alias2)
            models.db.session.commit()
            alias2_email = alias2.email

            # Delete first user
            user1_obj = models.db.session.get(models.User, user1_email)
            models.db.session.delete(user1_obj)
            models.db.session.commit()

            # Verify first user's owned aliases are deleted
            for alias_email in aliases1_emails:
                alias_obj = models.Alias.query.filter_by(email=alias_email).first()
                assert alias_obj is None

            # Verify regular alias (not owned) still exists
            regular_alias_obj = models.Alias.query.filter_by(email=regular_alias_email).first()
            assert regular_alias_obj is not None

            # Verify second user's aliases still exist
            alias2_obj = models.Alias.query.filter_by(email=alias2_email).first()
            assert alias2_obj is not None
