from mailu import models, utils
from mailu.ui import ui, forms, access
from flask import current_app as app

import validators
import flask
import flask_login
import wtforms_components


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
            conflicting_domain = models.Domain.query.get(form.name.data)
            conflicting_alternative = models.Alternative.query.get(form.name.data)
            conflicting_relay = models.Relay.query.get(form.name.data)
            if conflicting_domain or conflicting_alternative or conflicting_relay:
                flask.flash('Domain %s is already used' % form.name.data, 'error')
            else:
                domain = models.Domain()
                form.populate_obj(domain)
                models.db.session.add(domain)
                models.db.session.commit()
                flask.flash('Domain %s created' % domain)
                return flask.redirect(flask.url_for('.domain_list'))
        else:
            flask.flash('Domain %s is invalid' % form.name.data, 'error')
    return flask.render_template('domain/create.html', form=form)


@ui.route('/domain/edit/<domain_name>', methods=['GET', 'POST'])
@access.global_admin
def domain_edit(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    form = forms.DomainForm(obj=domain)
    wtforms_components.read_only(form.name)
    form.name.validators = []
    if form.validate_on_submit():
        form.populate_obj(domain)
        models.db.session.commit()
        flask.flash('Domain %s saved' % domain)
        return flask.redirect(flask.url_for('.domain_list'))
    return flask.render_template('domain/edit.html', form=form,
        domain=domain)


@ui.route('/domain/delete/<domain_name>', methods=['GET', 'POST'])
@access.global_admin
@access.confirmation_required("delete {domain_name}")
def domain_delete(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    models.db.session.delete(domain)
    models.db.session.commit()
    flask.flash('Domain %s deleted' % domain)
    return flask.redirect(flask.url_for('.domain_list'))


@ui.route('/domain/details/<domain_name>', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_details(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    return flask.render_template('domain/details.html', domain=domain)

@ui.route('/domain/details/<domain_name>/zonefile', methods=['GET'])
@access.domain_admin(models.Domain, 'domain_name')
def domain_download_zonefile(domain_name):
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    res = [domain.dns_mx, domain.dns_spf]
    if domain.dkim_publickey:
        record = domain.dns_dkim.split('"', 1)[0].strip()
        txt = f'v=DKIM1; k=rsa; p={domain.dkim_publickey}'
        txt = ' '.join(f'"{txt[p:p+250]}"' for p in range(0, len(txt), 250))
        res.append(f'{record} {txt}')
        res.append(domain.dns_dmarc)
        if domain.dns_dmarc_report_needed:
            res.append(domain.dns_dmarc_report)
    res.extend(domain.dns_tlsa)
    res.extend(domain.dns_autoconfig)
    for alternative in domain.alternatives:
        res.extend([alternative.dns_mx, alternative.dns_spf])
        if alternative.domain.dkim_publickey:
            record = alternative.dns_dkim.split('"', 1)[0].strip()
            txt = f'v=DKIM1; k=rsa; p={alternative.domain.dkim_publickey}'
            txt = ' '.join(f'"{txt[p:p+250]}"' for p in range(0, len(txt), 250))
            res.append(f'{record} {txt}')
            res.append(alternative.dns_dmarc)
            if alternative.dns_dmarc_report_needed:
                res.append(alternative.dns_dmarc_report)
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
    domain = models.Domain.query.get(domain_name) or flask.abort(404)
    domain.generate_dkim_key()
    models.db.session.add(domain)
    models.db.session.commit()
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
        conflicting_domain = models.Domain.query.get(form.name.data)
        conflicting_alternative = models.Alternative.query.get(form.name.data)
        conflicting_relay = models.Relay.query.get(form.name.data)
        if conflicting_domain or conflicting_alternative or conflicting_relay:
            flask.flash('Domain %s is already used' % form.name.data, 'error')
        else:
            domain = models.Domain()
            form.populate_obj(domain)
            domain.max_quota_bytes = app.config['DEFAULT_QUOTA']
            domain.max_users = 10
            domain.max_aliases = 10
            if domain.check_mx():
                models.db.session.add(domain)
                if flask_login.current_user.is_authenticated:
                    user = models.User.query.get(flask_login.current_user.email)
                else:
                    user = models.User()
                    user.domain = domain
                    form.populate_obj(user)
                    user.set_password(form.pw.data)
                    user.quota_bytes = domain.max_quota_bytes
                models.db.session.add(user)
                domain.managers.append(user)
                models.db.session.commit()
                flask.flash('Domain %s created' % domain)
                return flask.redirect(flask.url_for('.domain_list'))
            else:
                flask.flash('The MX record was not properly set', 'error')
    return flask.render_template('domain/signup.html', form=form)
