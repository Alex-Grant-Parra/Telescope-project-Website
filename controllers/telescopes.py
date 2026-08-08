import secrets
import logging
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user

from app.db import db
from security.token_store import token_hash

sec_logger = logging.getLogger('security')

telescopes_bp = Blueprint('telescopes', __name__)


@telescopes_bp.route('/telescopes')
@login_required
def my_telescopes():
    from models.tables import Telescope
    # Show the current user's registered telescopes
    telescopes = Telescope.query.filter_by(user_id=current_user.id).order_by(Telescope.token_created_at.desc()).all()
    generated_token = session.pop('new_user_telescope_token', None)
    generated_name = session.pop('new_user_telescope_name', None)
    return render_template(
        'my_telescopes.html',
        telescopes=telescopes,
        generated_token=generated_token,
        generated_name=generated_name,
    )


@telescopes_bp.route('/telescopes/register', methods=['POST'])
@login_required
def register_telescope():
    from models.tables import Telescope
    # Register a new telescope under the current user's account
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Telescope name is required.', 'danger')
        return redirect(url_for('telescopes.my_telescopes'))

    if len(name) > 100:
        flash('Telescope name must be 100 characters or fewer.', 'danger')
        return redirect(url_for('telescopes.my_telescopes'))

    # Prevent duplicate names across the whole table
    existing = Telescope.query.filter_by(telescope_id=name).first()
    if existing:
        flash(f'A telescope named "{name}" already exists. Please choose a different name.', 'danger')
        return redirect(url_for('telescopes.my_telescopes'))

    raw_token = secrets.token_urlsafe(32)
    digest = token_hash(raw_token)

    rec = Telescope(
        telescope_id=name,
        type='telescope',
        token_hash=digest,
        token_prefix=raw_token[:12],
        token_created_at=datetime.utcnow(),
        user_id=current_user.id,
        is_approved=False,  # requires admin approval
        is_disabled=False,
    )
    db.session.add(rec)
    db.session.commit()

    sec_logger.info(
        f"user_telescope_registered: name={name}, user_id={current_user.id}, "
        f"token_prefix={raw_token[:12]}..., pending_approval=True"
    )

    # One-time token reveal via session
    session['new_user_telescope_token'] = raw_token
    session['new_user_telescope_name'] = name
    flash(
        f'Telescope "{name}" registered. Copy your token now — it will not be shown again. '
        'It will become active once an admin approves it.',
        'success',
    )
    return redirect(url_for('telescopes.my_telescopes'))


@telescopes_bp.route('/telescopes/<int:telescope_id>/revoke', methods=['POST'])
@login_required
def revoke_my_telescope(telescope_id):
    from models.tables import Telescope
    # Allow a user to revoke (delete) one of their own telescopes
    rec = Telescope.query.filter_by(id=telescope_id, user_id=current_user.id).first()
    if not rec:
        flash('Telescope not found.', 'danger')
        return redirect(url_for('telescopes.my_telescopes'))

    name = rec.telescope_id
    db.session.delete(rec)
    db.session.commit()
    sec_logger.info(f"user_telescope_revoked: name={name}, user_id={current_user.id}")
    flash(f'Telescope "{name}" has been removed.', 'success')
    return redirect(url_for('telescopes.my_telescopes'))
