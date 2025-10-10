from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import security.manage_tokens as token_utils
import hashlib
import logging

security_bp = Blueprint('security', __name__)
logger = logging.getLogger('security')


def _token_identifier(token: str) -> str:
    # Create a short identifier for display/removal (not reversible)
    h = hashlib.sha256(token.encode()).hexdigest()
    return h[:12]


@security_bp.route('/security/tokens')
@login_required
def tokens():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    tokens = token_utils.load_tokens()
    # Build mapping of identifier -> (token, info)
    view_tokens = []
    for token, info in tokens.items():
        view_tokens.append({
            'id': _token_identifier(token),
            'name': info.get('name'),
            'client_type': info.get('client_type'),
            'created': info.get('created')
        })

    return render_template('security_tokens.html', tokens=view_tokens)


@security_bp.route('/security/tokens/generate', methods=['POST'])
@login_required
def generate_token():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    name = request.form.get('name') or 'unnamed'
    client_type = request.form.get('client_type') or 'observer'
    token = token_utils.add_token(name, client_type)
    identifier = _token_identifier(token)
    logger.info(f"token_generated: id={identifier}, name={name}, by={current_user.id}")
    flash(f'Generated token for {name}. Identifier: {identifier} (store the secret securely)', 'success')
    return redirect(url_for('security.tokens'))


@security_bp.route('/security/tokens/revoke', methods=['POST'])
@login_required
def revoke_token():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    identifier = request.form.get('token')
    if not identifier:
        flash('No token identifier specified.', 'danger')
        return redirect(url_for('security.tokens'))

    tokens = token_utils.load_tokens()
    found = None
    for token, info in list(tokens.items()):
        if _token_identifier(token) == identifier:
            found = token
            break

    if found:
        token_utils.revoke_token(found)
        logger.info(f"token_revoked: id={identifier}, by={current_user.id}")
        flash('Token revoked.', 'success')
    else:
        flash('Token identifier not found.', 'danger')

    return redirect(url_for('security.tokens'))
