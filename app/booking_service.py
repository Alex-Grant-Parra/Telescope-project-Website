import json
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.db import db
from models.booking import TelescopeAvailabilityBlock, TelescopeBooking, TelescopeBookingLock, BookingAuditEvent


def _get_telescope_model():
    from models.tables import Telescope
    return Telescope


def _get_user_model():
    from models.user import User
    return User


ACTIVE_BOOKING_STATES = {'pending', 'reserved'}


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(day_str):
    return datetime.strptime(day_str, '%Y-%m-%d').date()


def _parse_hhmm(value):
    return datetime.strptime(value, '%H:%M').time()


def _as_utc_naive(dt_with_tz):
    return dt_with_tz.astimezone(timezone.utc).replace(tzinfo=None)


def _serialize_booking(row):
    return {
        'id': row.id,
        'telescope_id': row.telescope_id,
        'requester_user_id': row.requester_user_id,
        'owner_user_id': row.owner_user_id,
        'start_utc': row.start_utc.isoformat() if row.start_utc else None,
        'end_utc': row.end_utc.isoformat() if row.end_utc else None,
        'status': row.status,
        'note': row.note,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def cleanup_expired_locks():
    now = _utc_now()
    TelescopeBookingLock.query.filter(TelescopeBookingLock.expires_at <= now).delete(synchronize_session=False)
    db.session.flush()


def to_utc_windows(date_list, start_time_hhmm, end_time_hhmm, user_timezone):
    tz = ZoneInfo(user_timezone or 'UTC')
    start_t = _parse_hhmm(start_time_hhmm)
    end_t = _parse_hhmm(end_time_hhmm)

    windows = []
    for day_str in date_list:
        local_day = _parse_date(day_str)
        local_start = datetime.combine(local_day, start_t).replace(tzinfo=tz)
        local_end_day = local_day if end_t > start_t else (local_day + timedelta(days=1))
        local_end = datetime.combine(local_end_day, end_t).replace(tzinfo=tz)
        windows.append((_as_utc_naive(local_start), _as_utc_naive(local_end)))

    return windows


def _overlap_exists(model, telescope_id, start_utc, end_utc, extra_filter=None):
    q = model.query.filter(
        model.telescope_id == telescope_id,
        model.start_utc < end_utc,
        model.end_utc > start_utc,
    )
    if extra_filter is not None:
        q = q.filter(extra_filter)
    return db.session.query(q.exists()).scalar()


def _allowed_window_check(telescope, window_start_utc, window_end_utc):
    # Optional owner-defined local booking windows (JSON array of {'start':'HH:MM','end':'HH:MM'})
    raw = telescope.allowed_windows_json
    if not raw:
        return True

    try:
        windows = json.loads(raw)
        if not isinstance(windows, list) or not windows:
            return True
    except Exception:
        return True

    tz = ZoneInfo(telescope.timezone or 'UTC')
    local_start = window_start_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    local_end = window_end_utc.replace(tzinfo=timezone.utc).astimezone(tz)

    # Compare by local clock minutes, handling overnight request windows
    request_start_min = local_start.hour * 60 + local_start.minute
    request_end_min = local_end.hour * 60 + local_end.minute
    if local_end.date() > local_start.date() or request_end_min <= request_start_min:
        request_end_min += 24 * 60

    for w in windows:
        try:
            ws = _parse_hhmm(w.get('start', '00:00'))
            we = _parse_hhmm(w.get('end', '23:59'))
            ws_min = ws.hour * 60 + ws.minute
            we_min = we.hour * 60 + we.minute
            if we_min <= ws_min:
                we_min += 24 * 60
            if request_start_min >= ws_min and request_end_min <= we_min:
                return True
        except Exception:
            continue

    return False


def evaluate_telescope_slot(telescope, start_utc, end_utc):
    if telescope.is_disabled or not telescope.is_approved:
        return 'unavailable'

    # Owner blackout rules
    unavailable_overlap = _overlap_exists(
        TelescopeAvailabilityBlock,
        telescope.id,
        start_utc,
        end_utc,
        TelescopeAvailabilityBlock.block_type == 'unavailable',
    )
    if unavailable_overlap:
        return 'unavailable'

    # If owner has explicit available blocks, require coverage by at least one block
    has_available_blocks = TelescopeAvailabilityBlock.query.filter_by(
        telescope_id=telescope.id,
        block_type='available',
    ).count() > 0
    if has_available_blocks:
        covered = TelescopeAvailabilityBlock.query.filter(
            TelescopeAvailabilityBlock.telescope_id == telescope.id,
            TelescopeAvailabilityBlock.block_type == 'available',
            TelescopeAvailabilityBlock.start_utc <= start_utc,
            TelescopeAvailabilityBlock.end_utc >= end_utc,
        ).first()
        if not covered:
            return 'unavailable'

    # Active bookings lock the slot
    booking_overlap = TelescopeBooking.query.filter(
        TelescopeBooking.telescope_id == telescope.id,
        TelescopeBooking.status.in_(list(ACTIVE_BOOKING_STATES)),
        TelescopeBooking.start_utc < end_utc,
        TelescopeBooking.end_utc > start_utc,
    ).first()
    if booking_overlap:
        return 'booking_in_process' if booking_overlap.status == 'pending' else 'reserved'

    # Short-lived lock protection
    lock_overlap = TelescopeBookingLock.query.filter(
        TelescopeBookingLock.telescope_id == telescope.id,
        TelescopeBookingLock.expires_at > _utc_now(),
        TelescopeBookingLock.start_utc < end_utc,
        TelescopeBookingLock.end_utc > start_utc,
    ).first()
    if lock_overlap:
        return 'booking_in_process'

    return 'available'


def search_telescopes(location_query, date_list, start_time_hhmm, end_time_hhmm, user_timezone):
    Telescope = _get_telescope_model()
    cleanup_expired_locks()
    windows = to_utc_windows(date_list, start_time_hhmm, end_time_hhmm, user_timezone)

    q = Telescope.query.filter(Telescope.token_hash.isnot(None))
    if location_query:
        like = f"%{location_query.strip()}%"
        q = q.filter(
            (Telescope.location_text.ilike(like)) |
            (Telescope.telescope_id.ilike(like))
        )

    telescopes = q.order_by(Telescope.telescope_id.asc()).all()
    results = []

    for t in telescopes:
        # Telescope is available only if all selected windows are available
        statuses = [evaluate_telescope_slot(t, w_start, w_end) for w_start, w_end in windows]
        aggregate_status = 'available' if all(s == 'available' for s in statuses) else 'unavailable'

        specs = {}
        try:
            specs = json.loads(t.specs_json) if t.specs_json else {}
            if not isinstance(specs, dict):
                specs = {}
        except Exception:
            specs = {}

        results.append({
            'id': t.id,
            'name': t.telescope_id,
            'location': t.location_text,
            'description': t.description,
            'status': aggregate_status,
            'specifications': {
                'aperture': specs.get('aperture'),
                'telescope_type': specs.get('telescope_type') or t.type,
                'mount_type': specs.get('mount_type'),
                'camera_model': specs.get('camera_model'),
            },
        })

    return results


def _ensure_duration_constraints(telescope, start_utc, end_utc):
    duration_min = int((end_utc - start_utc).total_seconds() / 60)
    min_min = telescope.min_booking_minutes or 30
    max_min = telescope.max_booking_minutes or 720
    if duration_min < min_min:
        return False, f'Minimum booking duration is {min_min} minutes.'
    if duration_min > max_min:
        return False, f'Maximum booking duration is {max_min} minutes.'
    return True, None


def request_booking(requester_user_id, telescope_id, date_list, start_time_hhmm, end_time_hhmm, user_timezone, note=None):
    Telescope = _get_telescope_model()
    telescope = db.session.get(Telescope, telescope_id)
    if not telescope:
        return None, 'Telescope not found.'

    if not telescope.user_id:
        return None, 'Telescope has no owner configured for booking approval.'

    if telescope.is_disabled or not telescope.is_approved:
        return None, 'Telescope is not available for booking.'

    windows = to_utc_windows(date_list, start_time_hhmm, end_time_hhmm, user_timezone)

    # SQLite-safe coarse lock to reduce race conditions while validating and inserting
    db.session.execute(text('BEGIN IMMEDIATE'))
    cleanup_expired_locks()

    created_ids = []
    for start_utc, end_utc in windows:
        ok, err = _ensure_duration_constraints(telescope, start_utc, end_utc)
        if not ok:
            db.session.rollback()
            return None, err

        if not _allowed_window_check(telescope, start_utc, end_utc):
            db.session.rollback()
            return None, 'Requested time is outside owner allowed booking windows.'

        status = evaluate_telescope_slot(telescope, start_utc, end_utc)
        if status != 'available':
            db.session.rollback()
            return None, 'Requested slot is no longer available.'

        lock = TelescopeBookingLock(
            telescope_id=telescope.id,
            requester_user_id=requester_user_id,
            start_utc=start_utc,
            end_utc=end_utc,
            expires_at=TelescopeBookingLock.default_expiry(minutes=15),
        )
        db.session.add(lock)

        booking = TelescopeBooking(
            telescope_id=telescope.id,
            requester_user_id=requester_user_id,
            owner_user_id=telescope.user_id,
            start_utc=start_utc,
            end_utc=end_utc,
            requester_timezone=user_timezone or 'UTC',
            status='pending',
            note=(note or '').strip() or None,
        )
        db.session.add(booking)
        db.session.flush()

        BookingAuditEvent.log(
            actor_user_id=requester_user_id,
            action_type='booking_request_submitted',
            entity_type='booking',
            entity_id=booking.id,
            before_state=None,
            after_state=_serialize_booking(booking),
            metadata={'telescope_id': telescope.id},
        )
        created_ids.append(booking.id)

    db.session.commit()
    return created_ids, None


def set_booking_decision(actor_user_id, booking_id, decision, is_admin=False):
    booking = db.session.get(TelescopeBooking, booking_id)
    if not booking:
        return None, 'Booking not found.'

    before = _serialize_booking(booking)

    if booking.status != 'pending':
        return None, 'Booking is not pending.'

    if decision == 'approve':
        booking.status = 'reserved'
    elif decision == 'reject':
        booking.status = 'rejected'
    else:
        return None, 'Invalid decision.'

    booking.approved_by_user_id = actor_user_id
    booking.decided_at = _utc_now()

    # Release lock(s) for this booking window after decision
    TelescopeBookingLock.query.filter(
        TelescopeBookingLock.telescope_id == booking.telescope_id,
        TelescopeBookingLock.start_utc == booking.start_utc,
        TelescopeBookingLock.end_utc == booking.end_utc,
    ).delete(synchronize_session=False)

    BookingAuditEvent.log(
        actor_user_id=actor_user_id,
        action_type='booking_approved' if decision == 'approve' else 'booking_rejected',
        entity_type='booking',
        entity_id=booking.id,
        before_state=before,
        after_state=_serialize_booking(booking),
        metadata={'is_admin_override': bool(is_admin)},
    )

    db.session.commit()
    return booking, None


def admin_override_booking(admin_user_id, booking_id, new_status):
    booking = db.session.get(TelescopeBooking, booking_id)
    if not booking:
        return None, 'Booking not found.'

    valid_states = {'pending', 'reserved', 'rejected', 'cancelled', 'expired'}
    if new_status not in valid_states:
        return None, 'Invalid booking state.'

    before = _serialize_booking(booking)
    booking.status = new_status
    booking.approved_by_user_id = admin_user_id
    booking.decided_at = _utc_now()

    BookingAuditEvent.log(
        actor_user_id=admin_user_id,
        action_type='admin_booking_override',
        entity_type='booking',
        entity_id=booking.id,
        before_state=before,
        after_state=_serialize_booking(booking),
        metadata={'new_status': new_status},
    )

    db.session.commit()
    return booking, None


def save_telescope_metadata(actor_user_id, telescope, payload, is_admin=False):
    before = {
        'description': telescope.description,
        'location_text': telescope.location_text,
        'latitude': telescope.latitude,
        'longitude': telescope.longitude,
        'timezone': telescope.timezone,
        'specs_json': telescope.specs_json,
        'extra_fields_json': telescope.extra_fields_json,
        'min_booking_minutes': telescope.min_booking_minutes,
        'max_booking_minutes': telescope.max_booking_minutes,
        'allowed_windows_json': telescope.allowed_windows_json,
    }

    telescope.description = (payload.get('description') or '').strip() or None
    telescope.location_text = (payload.get('location_text') or '').strip() or None
    telescope.timezone = (payload.get('timezone') or 'UTC').strip() or 'UTC'

    lat = payload.get('latitude')
    lon = payload.get('longitude')
    telescope.latitude = float(lat) if str(lat).strip() else None
    telescope.longitude = float(lon) if str(lon).strip() else None

    specs = payload.get('specifications') or {}
    if not isinstance(specs, dict):
        specs = {}
    if not is_admin:
        # Only admin may change telescope type in specifications
        specs.pop('telescope_type', None)

    telescope.specs_json = json.dumps(specs) if specs else None

    extra = payload.get('extra_fields') or {}
    if not isinstance(extra, dict):
        extra = {}
    telescope.extra_fields_json = json.dumps(extra) if extra else None

    min_minutes = payload.get('min_booking_minutes')
    max_minutes = payload.get('max_booking_minutes')
    telescope.min_booking_minutes = int(min_minutes) if str(min_minutes).strip() else 30
    telescope.max_booking_minutes = int(max_minutes) if str(max_minutes).strip() else 720

    allowed_windows = payload.get('allowed_windows')
    if isinstance(allowed_windows, str) and allowed_windows.strip():
        try:
            allowed_windows = json.loads(allowed_windows)
        except Exception:
            allowed_windows = None

    if isinstance(allowed_windows, list):
        telescope.allowed_windows_json = json.dumps(allowed_windows)

    BookingAuditEvent.log(
        actor_user_id=actor_user_id,
        action_type='telescope_metadata_updated',
        entity_type='telescope',
        entity_id=telescope.id,
        before_state=before,
        after_state={
            'description': telescope.description,
            'location_text': telescope.location_text,
            'latitude': telescope.latitude,
            'longitude': telescope.longitude,
            'timezone': telescope.timezone,
            'specs_json': telescope.specs_json,
            'extra_fields_json': telescope.extra_fields_json,
            'min_booking_minutes': telescope.min_booking_minutes,
            'max_booking_minutes': telescope.max_booking_minutes,
            'allowed_windows_json': telescope.allowed_windows_json,
        },
        metadata={'is_admin_override': bool(is_admin)},
    )

    db.session.commit()


def add_availability_block(actor_user_id, telescope, block_type, start_utc, end_utc):
    row = TelescopeAvailabilityBlock(
        telescope_id=telescope.id,
        owner_user_id=telescope.user_id,
        block_type=block_type,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    db.session.add(row)
    db.session.flush()

    BookingAuditEvent.log(
        actor_user_id=actor_user_id,
        action_type='availability_rule_changed',
        entity_type='availability',
        entity_id=row.id,
        before_state=None,
        after_state={
            'id': row.id,
            'telescope_id': row.telescope_id,
            'block_type': row.block_type,
            'start_utc': row.start_utc.isoformat(),
            'end_utc': row.end_utc.isoformat(),
        },
    )
    db.session.commit()
    return row


def get_owner_bookings(owner_user_id, include_past=False):
    q = TelescopeBooking.query.filter_by(owner_user_id=owner_user_id)
    if not include_past:
        q = q.filter(TelescopeBooking.end_utc >= _utc_now())
    return q.order_by(TelescopeBooking.start_utc.asc()).all()


def get_user_bookings(user_id, include_past=False):
    q = TelescopeBooking.query.filter_by(requester_user_id=user_id)
    if not include_past:
        q = q.filter(TelescopeBooking.end_utc >= _utc_now())
    return q.order_by(TelescopeBooking.start_utc.asc()).all()


def get_owner_for_telescope(telescope_id):
    Telescope = _get_telescope_model()
    User = _get_user_model()
    telescope = db.session.get(Telescope, telescope_id)
    if not telescope or not telescope.user_id:
        return None
    return db.session.get(User, telescope.user_id)


def get_user(user_id):
    User = _get_user_model()
    return db.session.get(User, user_id)
