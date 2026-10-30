from mailu import models, setup_tokens


def test_user_and_admin_groups_list_add_and_remove_accounts(app):
    runner = app.test_cli_runner()

    result = runner.invoke(app.cli, [
        'mailu', 'user', 'add', 'firstadmin@example.com',
    ])
    assert result.exit_code == 0, result.output
    assert 'One-time account setup link' in result.output
    assert 'https://mail.mailu.io/account/setup/' in result.output

    user = models.db.session.get(models.User, 'firstadmin@example.com')
    assert user is not None
    assert not user.global_admin
    assert user.check_password('') is False

    setup_token = result.output.rsplit('/', 1)[1].split()[0]
    assert setup_tokens.lookup(setup_token) is not None

    result = runner.invoke(app.cli, ['mailu', 'user', 'reset', user.email])
    assert result.exit_code == 0, result.output
    reset_token = result.output.rsplit('/', 1)[1].split()[0]
    assert reset_token != setup_token
    assert setup_tokens.lookup(setup_token) is None
    assert setup_tokens.lookup(reset_token) is not None

    result = runner.invoke(app.cli, ['mailu', 'user'])
    assert result.exit_code == 0, result.output
    assert user.email in result.output

    result = runner.invoke(app.cli, ['mailu', 'admin', 'add', user.email])
    assert result.exit_code == 0, result.output
    assert user.global_admin

    result = runner.invoke(app.cli, ['mailu', 'admin'])
    assert result.exit_code == 0, result.output
    assert user.email in result.output

    result = runner.invoke(app.cli, ['mailu', 'admin', 'remove', user.email])
    assert result.exit_code == 0, result.output
    assert not user.global_admin

    result = runner.invoke(app.cli, ['mailu', 'user', 'remove', user.email])
    assert result.exit_code == 0, result.output
    assert not user.enabled


def test_user_add_with_password_does_not_issue_setup_link(app):
    runner = app.test_cli_runner()
    result = runner.invoke(app.cli, [
        'mailu', 'user', 'add', 'passworduser@example.com', 'secret-password',
    ])
    assert result.exit_code == 0, result.output
    assert 'setup link' not in result.output.lower()
    assert models.db.session.get(models.User, 'passworduser@example.com').check_password(
        'secret-password',
    )
    assert models.AccountSetupToken.query.count() == 0
