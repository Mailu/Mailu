from mailu.admin import app, db, models, forms, access

import flask
import flask_login


@app.route('/fetch/list', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/fetch/list/<user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def fetch_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.render_template('fetch/list.html', user=user)


@app.route('/fetch/create', methods=['GET', 'POST'], defaults={'user_email': None})
@app.route('/fetch/create/<user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def fetch_create(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    form = forms.FetchForm()
    if form.validate_on_submit():
        fetch = models.Fetch(user=user)
        form.populate_obj(fetch)
        db.session.add(fetch)
        db.session.commit()
        flask.flash('Fetch configuration created')
        return flask.redirect(
            flask.url_for('.fetch_list', user_email=user.email))
    return flask.render_template('fetch/create.html', form=form)


@app.route('/fetch/edit/<fetch_id>', methods=['GET', 'POST'])
@access.owner(models.Fetch, 'fetch_id')
def fetch_edit(fetch_id):
    fetch = models.Fetch.query.get(fetch_id) or flask.abort(404)
    form = forms.FetchForm(obj=fetch)
    if form.validate_on_submit():
        form.populate_obj(fetch)
        db.session.commit()
        flask.flash('Fetch configuration updated')
        return flask.redirect(
            flask.url_for('.fetch_list', user_email=fetch.user.email))
    return flask.render_template('fetch/edit.html',
        form=form, fetch=fetch)


@app.route('/fetch/delete/<fetch_id>', methods=['GET', 'POST'])
@access.confirmation_required("delete a fetched account")
@access.owner(models.Fetch, 'fetch_id')
def fetch_delete(fetch_id):
    fetch = models.Fetch.query.get(fetch_id) or flask.abort(404)
    user = fetch.user
    db.session.delete(fetch)
    db.session.commit()
    flask.flash('Fetch configuration delete')
    return flask.redirect(
        flask.url_for('.fetch_list', user_email=user.email))
