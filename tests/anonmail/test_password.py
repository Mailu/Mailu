from mailu import models


def test_first_password_hash_can_be_verified(app):
    with app.app_context():
        models.User._ctx = None
        user = models.User(localpart='user', domain_name='example.com')
        user.set_password('password')

        assert user.check_password('password')
        assert not user.check_password('wrong-password')
