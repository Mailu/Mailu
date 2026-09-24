""" Regression test: `flask mailu config-import --update` (merge mode) must leave
    a field that the YAML omits unchanged.

    AliasSchema.disabled declared `load_default=False`, so when an alias entry in
    the imported YAML omitted `disabled`, marshmallow injected `disabled=False`
    and the merge re-enabled an alias an admin had disabled. Every other column
    relies on "field absent => keep existing value" (auto-generated fields never
    set a load_default); disabled must behave the same.
"""

from mailu import models
from mailu.schemas import MailuSchema


def _update_import(source):
    context = {'import': True, 'update': True, 'clear': False, 'callback': lambda *a, **k: None}
    schema = MailuSchema(only=MailuSchema.Meta.order, context=context)
    with models.db.session.no_autoflush:
        schema.loads(source)
    models.db.session.commit()


def test_context_is_propagated_to_nested_schemas():
    context = {'import': True, 'update': True}
    schema = MailuSchema(context=context)

    user_schema = schema.fields['user'].schema
    assert user_schema.context is context
    assert user_schema.fields['tokens'].schema.context is context


def test_update_import_omitting_disabled_keeps_alias_disabled(app):
    with app.app_context():
        models.db.session.add(models.Domain(name='example.com'))
        models.db.session.add(models.Alias(
            localpart='info', domain_name='example.com',
            destination=['alice@example.com'], disabled=True))
        models.db.session.commit()
        assert models.Alias.query.filter_by(email='info@example.com').first().disabled is True

        # merge-import the same alias WITHOUT the `disabled` field
        _update_import(
            "alias:\n"
            "  - email: info@example.com\n"
            "    destination:\n"
            "      - alice@example.com\n"
        )

        alias = models.Alias.query.filter_by(email='info@example.com').first()
        assert alias.disabled is True, "merge-import re-enabled a disabled alias"


def test_update_import_can_still_toggle_disabled_explicitly(app):
    with app.app_context():
        models.db.session.add(models.Domain(name='example.com'))
        models.db.session.add(models.Alias(
            localpart='info', domain_name='example.com',
            destination=['alice@example.com'], disabled=True))
        models.db.session.commit()

        # an explicit `disabled: false` must still re-enable it
        _update_import(
            "alias:\n"
            "  - email: info@example.com\n"
            "    destination:\n"
            "      - alice@example.com\n"
            "    disabled: false\n"
        )

        alias = models.Alias.query.filter_by(email='info@example.com').first()
        assert alias.disabled is False


def test_import_creating_new_alias_defaults_disabled_false(app):
    with app.app_context():
        models.db.session.add(models.Domain(name='example.com'))
        models.db.session.commit()

        # a newly-created alias without `disabled` must default to enabled
        _update_import(
            "alias:\n"
            "  - email: fresh@example.com\n"
            "    destination:\n"
            "      - alice@example.com\n"
        )

        alias = models.Alias.query.filter_by(email='fresh@example.com').first()
        assert alias is not None
        assert alias.disabled is False
