from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json
import mimetypes

from app.db import db
from models.contact import ContactMessage


contact_bp = Blueprint('contact', __name__)


ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.log', '.txt', '.fits'}


def _allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


@contact_bp.route('/contact', methods=['GET'])
def contact_form():
    prefill_email = ''
    try:
        if current_user.is_authenticated:
            prefill_email = current_user.get_email()
    except Exception:
        prefill_email = ''

    # Options for the dropdown
    type_options = [
        '🔧 Technical Issue / Bug Report',
        '🔭 Telescope Tracking Problem',
        '📷 Camera or Imaging Issue',
        '📚 Help / How-To Question',
        '⭐ Database / Star Catalog Issue',
        '💡 Feature Request',
        '🔒 Privacy or Account Issue',
        '🧪 Experimental Feature Feedback',
        '🌐 Website / Interface Feedback',
        '❓Other'
    ]
    return render_template('contact.html', prefill_email=prefill_email, type_options=type_options)


@contact_bp.route('/contact', methods=['POST'])
def submit_contact():
    email = (request.form.get('email') or '').strip()
    title = (request.form.get('title') or '').strip()
    message_type = (request.form.get('message_type') or '').strip()
    message = (request.form.get('message') or '').strip()
    client_meta_raw = request.form.get('client_meta')

    # Basic validation
    if not email or not message_type or not title or not message:
        flash('Please fill out email, type, title, and message.', 'danger')
        return redirect(url_for('contact.contact_form'))

    # Gather server-side metadata
    meta = {
        'server_received_at': datetime.utcnow().isoformat() + 'Z',
        'ip': request.headers.get('X-Forwarded-For', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', ''),
        'accept_language': request.headers.get('Accept-Language', ''),
        'referer': request.headers.get('Referer', ''),
        'url': request.url,
    }
    if title:
        meta['title'] = title

    # Merge client-provided metadata JSON
    try:
        if client_meta_raw:
            client_meta = json.loads(client_meta_raw)
            # Avoid excessive data
            if isinstance(client_meta, dict):
                meta.update(client_meta)
    except Exception:
        pass

    # Handle optional file upload
    saved_path = None
    file = request.files.get('attachment')
    if file and file.filename:
        fname = secure_filename(file.filename)
        if not _allowed_file(fname):
            flash('Invalid file type. Allowed: .png, .jpg, .jpeg, .log, .txt, .fits', 'danger')
            return redirect(url_for('contact.contact_form'))

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        upload_base = ContactMessage.uploads_dir(base_dir)
        try:
            os.makedirs(upload_base, exist_ok=True)
        except Exception:
            pass

        # Use timestamp-based folder to avoid collisions
        ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        target_dir = os.path.join(upload_base, ts)
        os.makedirs(target_dir, exist_ok=True)
        saved_path = os.path.join(target_dir, fname)
        file.save(saved_path)

    # Create DB record
    cm = ContactMessage(
        user_id=(current_user.id if getattr(current_user, 'is_authenticated', False) else None),
        email=email,
        message_type=message_type,
        message=message,
        file_path=saved_path,
        status='new'
    )
    cm.meta = meta
    db.session.add(cm)
    db.session.commit()

    # Send confirmation email (best-effort)
    try:
        from flask_mail import Message
        mail = current_app.extensions.get('mail')
        if mail:
            # Prefer user-provided title in subject when available
            effective_title = (title or message_type or 'Your message')
            subject = f"We received your message (Ticket #{cm.id}) - {effective_title}"
            body = (
                f"Hi,\n\nThanks for contacting us. We've received your message under ticket #{cm.id}.\n"
                f"Type: {message_type}\nSent at: {cm.created_at} UTC\n\n"
                "We'll get back to you as soon as possible.\n\n— Telescope Control"
            )
            msg = Message(subject, recipients=[email])
            msg.body = body
            mail.send(msg)
    except Exception:
        # Do not fail submission if email fails
        pass

    flash('Thanks! Your message has been sent. We will email you shortly.', 'success')
    return redirect(url_for('contact.contact_thank_you', ticket_id=cm.id))


@contact_bp.route('/contact/thank-you')
def contact_thank_you():
    ticket_id = request.args.get('ticket_id')
    title = None
    try:
        if ticket_id:
            from models.contact import ContactMessage
            cm = ContactMessage.query.get(int(ticket_id))
            if cm and cm.meta:
                title = cm.meta.get('title')
    except Exception:
        title = None
    return render_template('contact_thank_you.html', ticket_id=ticket_id, title=title)


@contact_bp.route('/contact/ping')
def contact_ping():
    # Lightweight endpoint for latency checks
    return jsonify({'ok': True, 'ts': datetime.utcnow().isoformat() + 'Z'})


# Admin: list and view/respond to messages
@contact_bp.route('/admin/contact')
@login_required
def admin_contact_list():
    # Basic admin guard: rely on User.is_admin
    if not getattr(current_user, 'is_admin', False):
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    q = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin_contact_list.html', messages=q)


@contact_bp.route('/admin/contact/<int:message_id>', methods=['GET', 'POST'])
@login_required
def admin_contact_detail(message_id):
    if not getattr(current_user, 'is_admin', False):
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    msg = ContactMessage.query.get_or_404(message_id)

    if request.method == 'POST':
        action = request.form.get('action')
        status = request.form.get('status') or msg.status
        # Build a default reply subject from provided title (if any)
        provided_title = None
        try:
            provided_title = (msg.meta or {}).get('title')
        except Exception:
            provided_title = None
        default_subject = f"Re: {(provided_title or 'Your contact request')} (Ticket #{msg.id})"
        reply_subject = request.form.get('reply_subject') or default_subject
        reply_body = request.form.get('reply_body')

        # Update status if changed
        if status and status != msg.status:
            msg.status = status

        # If sending reply
        if action == 'send_reply' and reply_body:
            try:
                from flask_mail import Message
                mail = current_app.extensions.get('mail')
                if mail:
                    m = Message(reply_subject, recipients=[msg.email])
                    m.body = reply_body
                    mail.send(m)
                    msg.admin_response = reply_body
                    msg.responded_at = datetime.utcnow()
                    flash('Reply sent to user.', 'success')
            except Exception as e:
                flash(f'Failed to send email: {e}', 'danger')

        db.session.commit()
        return redirect(url_for('contact.admin_contact_detail', message_id=msg.id))

    return render_template('admin_contact_detail.html', msg=msg)


@contact_bp.route('/admin/contact/<int:message_id>/attachment')
@login_required
def admin_contact_attachment(message_id):
    # Admin-only access to attachments; serve inline for images
    if not getattr(current_user, 'is_admin', False):
        flash('Admin access required.', 'danger')
        return redirect(url_for('home.home'))

    msg = ContactMessage.query.get_or_404(message_id)
    if not msg.file_path or not os.path.exists(msg.file_path):
        return jsonify({'error': 'Attachment not found'}), 404

    mime, _ = mimetypes.guess_type(msg.file_path)
    # Let Flask set the proper headers. For images, browsers will display inline by default.
    try:
        return send_file(msg.file_path, mimetype=mime or 'application/octet-stream')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
