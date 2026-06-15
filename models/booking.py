import json
from datetime import datetime, timedelta

from sqlalchemy import inspect, text

from app.db import db


class TelescopeAvailabilityBlock(db.Model):
    __tablename__ = 'telescope_availability_blocks'

    id = db.Column(db.Integer, primary_key=True)
    telescope_id = db.Column(db.Integer, db.ForeignKey('telescopes.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    block_type = db.Column(db.String(16), nullable=False, default='available')  # available|unavailable
    start_utc = db.Column(db.DateTime, nullable=False, index=True)
    end_utc = db.Column(db.DateTime, nullable=False, index=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    recurrence_rule = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class TelescopeBooking(db.Model):
    __tablename__ = 'telescope_bookings'

    id = db.Column(db.Integer, primary_key=True)
    telescope_id = db.Column(db.Integer, db.ForeignKey('telescopes.id', ondelete='CASCADE'), nullable=False, index=True)
    requester_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)

    start_utc = db.Column(db.DateTime, nullable=False, index=True)
    end_utc = db.Column(db.DateTime, nullable=False, index=True)
    requester_timezone = db.Column(db.String(64), nullable=False, default='UTC')

    # pending|reserved|rejected|cancelled|expired
    status = db.Column(db.String(16), nullable=False, default='pending', index=True)
    note = db.Column(db.Text, nullable=True)

    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class TelescopeBookingLock(db.Model):
    __tablename__ = 'telescope_booking_locks'

    id = db.Column(db.Integer, primary_key=True)
    telescope_id = db.Column(db.Integer, db.ForeignKey('telescopes.id', ondelete='CASCADE'), nullable=False, index=True)
    requester_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    start_utc = db.Column(db.DateTime, nullable=False, index=True)
    end_utc = db.Column(db.DateTime, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @staticmethod
    def default_expiry(minutes=5):
        return datetime.utcnow() + timedelta(minutes=minutes)


class BookingAuditEvent(db.Model):
    __tablename__ = 'booking_audit_events'

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True)
    action_type = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(32), nullable=False, index=True)  # booking|telescope|availability
    entity_id = db.Column(db.Integer, nullable=True, index=True)

    before_state_json = db.Column(db.Text, nullable=True)
    after_state_json = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    @classmethod
    def log(cls, actor_user_id, action_type, entity_type, entity_id=None, before_state=None, after_state=None, metadata=None):
        row = cls(
            actor_user_id=actor_user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state_json=json.dumps(before_state) if before_state is not None else None,
            after_state_json=json.dumps(after_state) if after_state is not None else None,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        db.session.add(row)



def ensure_telescope_booking_columns():
    """Ensure booking-related telescope metadata/constraint columns exist."""
    engine = db.engine
    inspector = inspect(engine)

    if 'telescopes' not in inspector.get_table_names():
        return

    existing_cols = {c['name'] for c in inspector.get_columns('telescopes')}
    required = {
        'description': 'TEXT',
        'latitude': 'REAL',
        'longitude': 'REAL',
        'specs_json': 'TEXT',
        'aperture': 'VARCHAR(128)',
        'camera': 'VARCHAR(255)',
        'min_booking_minutes': 'INTEGER',
        'max_booking_minutes': 'INTEGER',
        'allowed_windows_json': 'TEXT',
    }
    remove_if_present = {'location_text', 'extra_fields_json', 'timezone'}

    with engine.begin() as conn:
        for col_name, col_type in required.items():
            if col_name not in existing_cols:
                conn.execute(text(f"ALTER TABLE telescopes ADD COLUMN {col_name} {col_type}"))

        for col_name in remove_if_present:
            if col_name in existing_cols:
                conn.execute(text(f"ALTER TABLE telescopes DROP COLUMN {col_name}"))

        # sensible defaults for legacy rows
        conn.execute(text("UPDATE telescopes SET min_booking_minutes = COALESCE(min_booking_minutes, 30)"))
        conn.execute(text("UPDATE telescopes SET max_booking_minutes = COALESCE(max_booking_minutes, 720)"))
