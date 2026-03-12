import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


def _bool(x, default=False):
    if x is None:
        return default
    if isinstance(x, bool):
        return x
    return str(x).lower() in ("1", "true", "yes", "on")


def _as_sender(sender_name, sender_email):
    if sender_name:
        return f"{sender_name} <{sender_email}>"
    return sender_email


def send_smtp_email(server, port, use_tls, username, password,
                    sender_email, sender_name,
                    recipients, subject, body,
                    reply_to=None, timeout=15):
    """Send a plain-text email directly via SMTP.
    Args:
        server, port, use_tls, username, password: SMTP connection params
        sender_email, sender_name: From header
        recipients (list[str]): To recipients
        subject (str): Subject
        body (str): Plain text body
        reply_to (str|None): Optional Reply-To header
    Returns: True on success, raises on failure
    """
    if not recipients:
        raise ValueError("No recipients provided")

    msg = EmailMessage()
    msg['From'] = _as_sender(sender_name, sender_email)
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    if reply_to:
        msg['Reply-To'] = reply_to
    msg['Message-ID'] = make_msgid()
    msg.set_content(body or "")

    with smtplib.SMTP(server, port, timeout=timeout) as smtp:
        if _bool(use_tls, True):
            smtp.starttls()
        if username:
            smtp.login(username, password or '')
        smtp.send_message(msg)
    return True


def send_email(app, role, recipients, subject, body, reply_to=None):
    """Role-aware email sender.
    Uses per-role SMTP settings if present, otherwise falls back to Flask-Mail.
    role: 'support' or 'auth'
    """
    role = (role or '').strip().lower()
    if role not in ('support', 'auth'):
        raise ValueError("role must be 'support' or 'auth'")

    prefix = 'MAIL_SUPPORT_' if role == 'support' else 'MAIL_AUTH_'

    # Determine sender headers
    sender_email = app.config.get(prefix + 'SENDER') or app.config.get('MAIL_DEFAULT_SENDER')
    sender_name = app.config.get(prefix + 'NAME') or (role.capitalize())

    server = app.config.get(prefix + 'SMTP_SERVER')
    port = app.config.get(prefix + 'SMTP_PORT')
    use_tls = app.config.get(prefix + 'SMTP_USE_TLS', True)
    username = app.config.get(prefix + 'SMTP_USERNAME')
    password = app.config.get(prefix + 'SMTP_PASSWORD')

    if server and port:
        return send_smtp_email(
            server=server,
            port=port,
            use_tls=use_tls,
            username=username,
            password=password,
            sender_email=sender_email,
            sender_name=sender_name,
            recipients=recipients,
            subject=subject,
            body=body,
            reply_to=reply_to or sender_email,
        )

    # Fallback: use Flask-Mail (single configured SMTP)
    mail_ext = app.extensions.get('mail')
    if mail_ext is None:
        raise RuntimeError('Flask-Mail is not configured and no role SMTP provided')

    try:
        from flask_mail import Message
        msg = Message(subject, recipients=recipients, sender=(sender_name, sender_email), reply_to=reply_to or sender_email)
        msg.body = body or ""
        mail_ext.send(msg)
        return True
    except Exception:
        raise
