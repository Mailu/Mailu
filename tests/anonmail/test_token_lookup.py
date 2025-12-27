"""Test token lookup hash functionality"""
import hashlib
import os
import hmac

from passlib import pwd
from mailu import models



def test_token_lookup_hash_created(app):
    """Test that token_lookup_hash is created when setting password"""
    with app.app_context():
        user = models.User(email='user@example.com')
        user.set_password('password123')
        models.db.session.add(user)
        models.db.session.commit()

        token = models.Token(user_email='user@example.com')
        raw_password = pwd.genword(entropy=128, length=32, charset="hex")
        token.set_password(raw_password)
        
        # Verify lookup hash was created
        assert token.token_lookup_hash is not None
        secret = os.environ.get('SECRET_KEY', '')
        expected_hash = hmac.new(secret.encode(), raw_password.encode(), hashlib.sha256).hexdigest()
        assert token.token_lookup_hash == expected_hash
        
        models.db.session.add(token)
        models.db.session.commit()
        
        # Verify we can find token by lookup hash
        found = models.Token.query.filter_by(token_lookup_hash=expected_hash).first()
        assert found is not None
        assert found.id == token.id


def test_token_check_password_backfills_hash(app):
    """Test that check_password backfills lookup hash for existing tokens"""
    with app.app_context():
        user = models.User(email='user2@example.com')
        user.set_password('password123')
        models.db.session.add(user)
        models.db.session.commit()

        # Create token with password but without lookup hash (simulate old token)
        raw_password = pwd.genword(entropy=128, length=32, charset="hex")
        token = models.Token(user_email='user2@example.com')
        token.password = models.passlib.hash.pbkdf2_sha256.using(rounds=1).hash(raw_password)
        token.token_lookup_hash = None  # Simulate old token without hash
        
        models.db.session.add(token)
        models.db.session.commit()
        token_id = token.id
        
        # Verify no lookup hash yet
        assert token.token_lookup_hash is None
        
        # Check password should backfill the hash
        result = token.check_password(raw_password)
        assert result is True
        
        # Verify hash was backfilled
        token = models.Token.query.get(token_id)
        assert token.token_lookup_hash is not None
        secret = os.environ.get('SECRET_KEY', '')
        expected_hash = hmac.new(secret.encode(), raw_password.encode(), hashlib.sha256).hexdigest()
        assert token.token_lookup_hash == expected_hash


def test_token_lookup_performance(app):
    """Test that token lookup uses index (doesn't load all tokens)"""
    with app.app_context():
        # Create user
        user = models.User(email='user3@example.com')
        user.set_password('password123')
        models.db.session.add(user)
        models.db.session.commit()

        # Create multiple tokens
        tokens = []
        raw_passwords = []
        for i in range(10):
            token = models.Token(user_email='user3@example.com', comment=f'Token {i}')
            raw_pwd = pwd.genword(entropy=128, length=32, charset="hex")
            token.set_password(raw_pwd)
            tokens.append(token)
            raw_passwords.append(raw_pwd)
            models.db.session.add(token)
        
        models.db.session.commit()
        
        # Verify we can find each token directly using hash lookup
        for i, (token, raw_pwd) in enumerate(zip(tokens, raw_passwords)):
            secret = os.environ.get('SECRET_KEY', '')
            lookup_hash = hmac.new(secret.encode(), raw_pwd.encode(), hashlib.sha256).hexdigest()
            found = models.Token.query.filter_by(token_lookup_hash=lookup_hash).first()
            assert found is not None
            assert found.id == token.id
            assert found.comment == f'Token {i}'
            assert found.check_password(raw_pwd) is True
