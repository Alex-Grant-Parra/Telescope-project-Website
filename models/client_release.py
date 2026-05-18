import os
from datetime import datetime

from app.db import db


class ClientReleaseSubmission(db.Model):
    __tablename__ = "client_release_submission"

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_APPROVED = "approved"
    STATUS_DELETED = "deleted"
    VALID_STATUSES = {
        STATUS_PENDING,
        STATUS_IN_PROGRESS,
        STATUS_APPROVED,
        STATUS_DELETED,
    }

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(128), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    uploaded_by_telescope_id = db.Column(db.Integer, nullable=True)
    uploaded_by_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_PENDING, index=True)
    claimed_by_user_id = db.Column(db.Integer, nullable=True)
    reviewed_by_user_id = db.Column(db.Integer, nullable=True)
    review_note = db.Column(db.String(512), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    @staticmethod
    def candidate_dir():
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_dir, "instance", "uploads", "client_release_candidates")

    @staticmethod
    def downloads_dir():
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_dir, "downloads")

    @classmethod
    def create_submission(cls, *, version, original_filename, stored_filename, telescope_id=None, telescope_name=None):
        rec = cls(
            version=version,
            original_filename=original_filename,
            stored_filename=stored_filename,
            uploaded_by_telescope_id=telescope_id,
            uploaded_by_name=telescope_name,
            status=cls.STATUS_PENDING,
        )
        db.session.add(rec)
        db.session.commit()
        return rec

    @classmethod
    def list_for_review(cls):
        return cls.query.order_by(cls.uploaded_at.desc()).all()

    @classmethod
    def get_by_id(cls, submission_id):
        return db.session.get(cls, int(submission_id))

    def mark_in_progress(self, *, admin_user_id):
        self.status = self.STATUS_IN_PROGRESS
        self.claimed_by_user_id = admin_user_id
        self.reviewed_by_user_id = admin_user_id
        self.reviewed_at = datetime.utcnow()
        db.session.commit()
        return self

    def mark_approved(self, *, admin_user_id):
        self.status = self.STATUS_APPROVED
        self.reviewed_by_user_id = admin_user_id
        self.reviewed_at = datetime.utcnow()
        db.session.commit()
        return self

    def mark_deleted(self, *, admin_user_id):
        self.status = self.STATUS_DELETED
        self.reviewed_by_user_id = admin_user_id
        self.reviewed_at = datetime.utcnow()
        db.session.commit()
        return self

    def candidate_file_path(self):
        return os.path.join(self.candidate_dir(), self.stored_filename)

    def published_file_path(self):
        return os.path.join(self.downloads_dir(), f"{self.version}.zip")
