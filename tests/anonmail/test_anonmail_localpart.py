from mailu import utils

def test_generate_anonymous_alias_localpart_with_hostname():
    """Test anonymous alias generation with hostname"""
    result = utils.generate_anonymous_alias_localpart(hostname='www.example.com', mode='word')
    assert isinstance(result, str)
    assert '.' in result  # Should have format: hostname_prefix.word
    prefix, word = result.split('.', 1)
    assert prefix == 'example'
    assert word.isalpha()
    assert word.islower()
    assert 5 <= len(word) <= 10


def test_generate_anonymous_alias_localpart_without_hostname():
    """Test anonymous alias generation without hostname"""
    result = utils.generate_anonymous_alias_localpart()
    assert isinstance(result, str)
    # Should be a random token (not a word)
    assert len(result) > 0


def test_generate_anonymous_alias_localpart_consistency():
    """Test that generate_anonymous_alias_localpart returns different words (most of the time)"""
    words = [utils.generate_anonymous_alias_localpart(hostname='www.example.com', mode='word') for _ in range(10)]
    # At least some words should be different
    assert len(set(words)) > 1
