from mailu import models, utils
from mailu.ui import ui, forms, access
from flask import current_app as app

import validators
import flask
import flask_login
import wtforms_components

db = models.db


@ui.route('/domain', methods=['GET'])
@access.authenticated
def domain_list():
    return flask.render_template('domain/list.html')


@ui.route('/domain/create', methods=['GET', 'POST'])
@access.global_admin
def domain_create():
    form = forms.DomainForm()
    if form.validate_on_submit():
        if validators.domain(form.name.data):
            conflicting_domain = db.session.get(models.Domain, form.name.data)
            conflicting_alternative = db.session.get(models.Alternative, form.name.data)
            conflicting_relay = db.session.get(models.Relay, form.name.data)
            if conflicting_domain or conflicting_alternative or conflicting_relay:
                flask.flash('Domain %s is already used' % form.name.data, 'error')
            else:
                domain = models.Domain()
                form.populate_obj(domain)
                db.session.add(domain)
                db.session.commit()
                flask.flash('Domain %s created' % domain)
                return flask.redirect(flask.url_for('.domain_list'))
        else:
            flask.flash('Domain %s is invalid' % form.name.data, 'error')
    return flask.render_template('domain/create.html', form=form)


@ui.route('/domain/edit/<domain_name>', methods=['GET', 'POST'])
@access.global_admin
def domain_edit(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    form = forms.DomainForm(obj=domain)
    wtforms_components.read_only(form.name)
    form.name.validators = []
    if form.validate_on_submit():
        form.populate_obj(domain)
        db.session.commit()
        flask.flash('Domain %s saved' % domain)
        return flask.redirect(flask.url_for('.domain_list'))
    return flask.render_template('domain/edit.html', form=form,
        domain=domain)


@ui.route('/domain/delete/<domain_name>', methods=['GET', 'POST'])
@access.global_admin
@access.confirmation_required("delete {domain_name}")
def domain_delete(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    db.session.delete(domain)
    db.session.commit()
    flask.flash('Domain %s deleted' % domain)
    return flask.redirect(flask.url_for('.domain_list'))


@ui.route('/domain/details/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_details(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    return flask.render_template('domain/details.html', domain=domain)


@ui.route('/domain/details/<domain_name>/zonefile', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_download_zonefile(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    res = [domain.dns_mx, domain.dns_spf]
    if domain.dkim_publickey:
        record = domain.dns_dkim.split('"', 1)[0].strip()
        txt = f'v=DKIM1; k=rsa; p={domain.dkim_publickey}'
        txt = ' '.join(f'"{txt[p:p+250]}"' for p in range(0, len(txt), 250))
        res.append(f'{record} {txt}')
        res.append(domain.dns_dmarc)
    if domain.dns_tlsa:
        res.append(domain.dns_tlsa)
    res.extend(domain.dns_autoconfig)
    res.append("")
    return flask.Response(
        "\n".join(res),
        content_type="text/plain",
        headers={"Content-disposition": f"attachment; filename={domain.name}-zonefile.txt"}
    )


@ui.route('/domain/genkeys/<domain_name>', methods=['GET', 'POST'])
@access.domain_admin(models.Domain, 'domain_name')
@access.confirmation_required("regenerate keys for {domain_name}")
def domain_genkeys(domain_name):
    domain = db.get_or_404(models.Domain, domain_name)
    domain.generate_dkim_key()
    db.session.add(domain)
    db.session.commit()
    return flask.redirect(
        flask.url_for(".domain_details", domain_name=domain_name))


@ui.route('/domain/signup', methods=['GET', 'POST'])
def domain_signup(domain_name=None):
    if not app.config['DOMAIN_REGISTRATION']:
        flask.abort(403)
    form = forms.DomainSignupForm()
    if flask_login.current_user.is_authenticated:
        del form.localpart
        del form.pw
        del form.pw2
    if form.validate_on_submit():
        if msg := utils.isBadOrPwned(form):
            flask.flash(msg, "error")
            return flask.render_template('domain/signup.html', form=form)
        conflicting_domain = db.session.get(models.Domain, form.name.data)
        conflicting_alternative = db.session.get(models.Alternative, form.name.data)
        conflicting_relay = db.session.get(models.Relay, form.name.data)
        if conflicting_domain or conflicting_alternative or conflicting_relay:
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            domain = models.Domain()
            form.populate_obj(domain)
            domain.max_quota_bytes = app.config['DEFAULT_QUOTA']
            domain.max_users = 10
            domain.max_aliases = 10
            if domain.check_mx():
                db.session.add(domain)
                if flask_login.current_user.is_authenticated:
                    user = db.session.get(models.User, flask_login.current_user.email)
                else:
                    user = models.User()
                    user.domain = domain
                    form.populate_obj(user)
                    user.set_password(form.pw.data)
                    user.quota_bytes = domain.max_quota_bytes
                db.session.add(user)
                domain.managers.append(user)
                db.session.commit()
                flask.flash('Domain %s created' % domain)
                return flask.redirect(flask.url_for('.domain_list'))
            else:
                flask.flash('The MX record was not properly set', 'error')
    return flask.render_template('domain/signup.html', form=form)
