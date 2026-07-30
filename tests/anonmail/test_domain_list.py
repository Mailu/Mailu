from sqlalchemy import event

from mailu import models


class TestDomainListCounts:
    """ Regression for #3996: the domain list page must count users/aliases
    with grouped aggregates instead of materializing every domain's full
    collection, which hangs the page on installs with many users. """

    def test_domain_list_does_not_materialize_collections(self, app, client):
        with app.app_context():
            for dname, nusers, naliases in (('a.example.com', 3, 1), ('b.example.com', 1, 2)):
                models.db.session.add(models.Domain(name=dname))
                for i in range(nusers):
                    user = models.User(localpart=f'u{i}', domain_name=dname)
                    user.set_password('password')
                    models.db.session.add(user)
                for i in range(naliases):
                    models.db.session.add(models.Alias(
                        localpart=f'al{i}', domain_name=dname, destination=[f'u0@{dname}']))
            admin = models.User(localpart='admin', domain_name='a.example.com', global_admin=True)
            admin.set_password('password')
            models.db.session.add(admin)
            models.db.session.commit()

            with client.session_transaction() as sess:
                sess['_user_id'] = admin.email
                sess['_auth_generation'] = admin.auth_generation
                sess['_fresh'] = True

            statements = []
            engine = models.db.engine

            def _capture(conn, cursor, statement, parameters, context, executemany):
                statements.append(statement)

            event.listen(engine, 'before_cursor_execute', _capture)
            try:
                rv = client.get(app.config['WEB_ADMIN'] + '/domain')
            finally:
                event.remove(engine, 'before_cursor_execute', _capture)

            assert rv.status_code == 200
            body = rv.get_data(as_text=True)
            # a.example.com: 3 users + the admin = 4 ; b.example.com: 2 aliases
            assert '4 /' in body
            assert '2 /' in body

            # The fix must not lazy-load each domain's user/alias collection,
            # which the old `domain.users | count` did (one query per row, of the
            # form ``... WHERE ? = user.domain_name``). The grouped aggregate the
            # fix uses has no WHERE clause, so it does not match.
            per_domain = [
                s for s in statements
                if 'where' in s.lower()
                and ('user.domain_name' in s.lower() or 'alias.domain_name' in s.lower())
            ]
            assert not per_domain, f'per-domain materialization still happens: {per_domain}'
