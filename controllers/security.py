from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
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
            'id': token,  # Full token for identification
            'truncated': token[:12] + '...',  # Truncated for display
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
    
    # Check for duplicate names
    tokens = token_utils.load_tokens()
    for token, info in tokens.items():
        if info.get('name') == name:
            flash(f'Token with name "{name}" already exists. Please choose a different name.', 'danger')
            return redirect(url_for('security.tokens'))
    
    token = token_utils.add_token(name, client_type)
    logger.info(f"token_generated: token={token[:12]}..., name={name}, by={current_user.id}")
    flash(f'Generated token for {name}: {token} (store securely)', 'success')
    return redirect(url_for('security.tokens'))


@security_bp.route('/security/tokens/revoke', methods=['POST'])
@login_required
def revoke_token():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    identifier = request.form.get('token')
    if not identifier:
        flash('No token specified.', 'danger')
        return redirect(url_for('security.tokens'))

    tokens = token_utils.load_tokens()
    if identifier in tokens:
        token_utils.revoke_token(identifier)
        logger.info(f"token_revoked: token={identifier[:12]}..., by={current_user.id}")
        flash('Token revoked.', 'success')
    else:
        flash('Token not found.', 'danger')

    return redirect(url_for('security.tokens'))


@security_bp.route('/security/tokens/show', methods=['POST'])
@login_required
def show_token():
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    token_id = request.json.get('token_id') if request.is_json else request.form.get('token_id')
    if not token_id:
        return jsonify({'error': 'Token ID required'}), 400

    tokens = token_utils.load_tokens()
    if token_id in tokens:
        return jsonify({'token': token_id})
    else:
        return jsonify({'error': 'Token not found'}), 404
