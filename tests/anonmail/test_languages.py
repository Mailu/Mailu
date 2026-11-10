"""Language negotiation, persisted preferences and shared UI labels."""
import re

import flask
import pytest
from flask_babel import get_locale as babel_locale, gettext
from mailu import models, utils


@pytest.mark.parametrize('header,expected', [
    ('zh-TW,zh;q=0.9', 'zh_Hant'),
    ('zh-HK,zh;q=0.9', 'zh_Hant'),
    ('zh-MO,zh;q=0.9', 'zh_Hant'),
    ('zh-Hant', 'zh_Hant'),
    ('zh-Hant-HK', 'zh_Hant'),
    ('zh-Hant-TW', 'zh_Hant'),
    ('zh-Hant-MO', 'zh_Hant'),
    ('zh-HK-u-ca-chinese', 'zh_Hant'),
    ('ZH-hAnT-hK', 'zh_Hant'),
    ('zh-CN,zh;q=0.9', 'zh'),
    ('zh-SG', 'zh'),
    ('zh-Hans', 'zh'),
    ('zh-Hans-CN', 'zh'),
    ('zh-Hans-SG', 'zh'),
    ('zh-Hans-TW', 'zh'),
    ('zh-Hant-CN', 'zh_Hant'),
    ('zh', 'zh'),
    ('en-US,zh-TW;q=0.8', 'en'),
    ('zh-TW,en-US;q=0.8', 'zh_Hant'),
    ('zh-TW;q=0.5,en-US;q=0.8', 'en'),
    ('zh-TW,en', 'zh_Hant'),
    ('en,zh-TW', 'en'),
    ('zh-TW;q=0,en;q=0.8', 'en'),
    ('zh-Hant;q=0,zh;q=0.8', 'zh'),
    ('zh;q=0,zh-HK;q=0.8', 'zh_Hant'),
    ('zh-Hant;q=0,*;q=0.5', None),
    ('zh;q=0,zh-Hant;q=0,en;q=0.8', 'en'),
    ('de-DE,de;q=0.9,en;q=0.8', 'de'),
    ('fr-CA', 'fr'),
    ('pt-BR', 'pt'),
    ('pt', 'pt'),
    ('zz-ZZ', 'en'),
    ('', 'en'),
])
def test_negotiation(app, header, expected):
    with app.test_request_context(headers={'Accept-Language': header}):
        selected = utils.get_locale()
        if expected is None:
            assert selected != 'zh_Hant'
        else:
            assert selected == expected
        # Anonymous language detection must not create a session cookie.
        assert 'language' not in flask.session


def test_configured_default(app):
    app.config['BABEL_DEFAULT_LOCALE'] = 'de'
    with app.test_request_context(headers={'Accept-Language': 'zz-ZZ'}):
        assert utils.get_locale() == 'de'


@pytest.mark.parametrize('header,expected', [
    ('*', 'zh'),
    ('zh;q=0,*;q=0.5', 'en'),
    ('zh-Hant;q=0,*;q=0.5', 'zh'),
    ('*;q=0,zh-TW;q=0.8', 'zh_Hant'),
    ('en-US;q=0,*;q=0.5', 'zh'),
    ('en-US;q=0,zh-TW;q=0.8', 'zh_Hant'),
])
def test_wildcard_and_exclusions(app, header, expected):
    app.config.translations = {key: app.config.translations[key] for key in ('zh', 'zh_Hant', 'en')}
    with app.test_request_context(headers={'Accept-Language': header}):
        assert utils.get_locale() == expected


@pytest.mark.parametrize('language,expected', [
    ('zh', 'zh'), ('zh_Hant', 'zh_Hant'), ('zh_Hant_TW', 'zh_Hant'),
    ('invalid', 'zh_Hant'),
])
def test_session_preference(app, client, language, expected):
    with client.session_transaction() as session:
        session['language'] = language
    response = client.get('/sso/login', headers={'Accept-Language': 'zh-HK'})
    assert response.status_code == 200
    assert f'lang="{expected.replace("_", "-")}"' in response.text
    with client.session_transaction() as session:
        assert session['language'] == expected


def test_compiled_catalog(app):
    assert 'zh_Hant' in app.config.translations
    assert 'zh_Hant_TW' not in app.config.translations
    with app.test_request_context(headers={'Accept-Language': 'zh-TW'}):
        assert str(babel_locale()) == 'zh_Hant'
        assert gettext('Password') == '密碼'


@pytest.mark.parametrize('surface', ['sso', 'ui'])
def test_language_menu_and_switch(app, client, surface):
    if surface == 'ui':
        domain = models.Domain(name='language.example')
        user = models.User(localpart='alice', domain=domain)
        user.set_password('test-password')
        models.db.session.add_all([domain, user])
        models.db.session.commit()
        with client.session_transaction() as session:
            session['_user_id'] = user.email
            session['_fresh'] = True
    path = '/admin/user/settings' if surface == 'ui' else '/sso/login'
    prefix = '/admin' if surface == 'ui' else '/sso'
    response = client.get(path, headers={'Accept-Language': 'zh-TW'})
    assert response.status_code == 200
    assert 'lang="zh-Hant"' in response.text
    assert f'href="{prefix}/language/zh">简体中文</a>' in response.text
    assert f'href="{prefix}/language/zh_Hant">繁體中文</a>' in response.text
    assert re.search(r'(?:>|: )繁體中文</(?:span|button)>', response.text)
    assert 'zh_Hant_TW' not in response.text
    for language, label in [('zh', '简体中文'), ('zh_Hant', '繁體中文'), ('de', 'Deutsch')]:
        assert client.post(f'{prefix}/language/{language}').status_code == 200
        for _ in range(2):
            refreshed = client.get(path, headers={'Accept-Language': 'en-US'})
            assert refreshed.status_code == 200
            assert f'lang="{language.replace("_", "-")}"' in refreshed.text
            assert re.search(f'(?:>|: ){label}</(?:span|button)>', refreshed.text)
        with client.session_transaction() as session:
            assert session['language'] == language
