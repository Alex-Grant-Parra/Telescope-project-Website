import hashlib
import os
from datetime import datetime, timedelta
from db import db
from flask import request


class TrustedDevice(db.Model):
    __tablename__ = "trusted_device"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    device_fingerprint = db.Column(db.String(64), nullable=False)  # SHA256 hash
    device_name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to User
    user = db.relationship('User', backref='trusted_devices')
    
    @staticmethod
    def generate_device_fingerprint():
        """Generate a device fingerprint based on request headers and IP"""
        # Get identifying information from the request
        user_agent = request.headers.get('User-Agent', '')
        accept_language = request.headers.get('Accept-Language', '')
        accept_encoding = request.headers.get('Accept-Encoding', '')
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        
        # Create a fingerprint string
        fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}|{client_ip}"
        
        # Hash the fingerprint for storage
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    @staticmethod
    def get_device_name():
        """Extract a friendly device name from User-Agent"""
        user_agent = request.headers.get('User-Agent', '')
        
        # Simple device name extraction
        if 'Windows' in user_agent:
            if 'Chrome' in user_agent:
                return 'Windows - Chrome'
            elif 'Firefox' in user_agent:
                return 'Windows - Firefox'
            elif 'Edge' in user_agent:
                return 'Windows - Edge'
            else:
                return 'Windows - Unknown Browser'
        elif 'Macintosh' in user_agent:
            if 'Chrome' in user_agent:
                return 'Mac - Chrome'
            elif 'Firefox' in user_agent:
                return 'Mac - Firefox'
            elif 'Safari' in user_agent:
                return 'Mac - Safari'
            else:
                return 'Mac - Unknown Browser'
        elif 'Linux' in user_agent:
            if 'Chrome' in user_agent:
                return 'Linux - Chrome'
            elif 'Firefox' in user_agent:
                return 'Linux - Firefox'
            else:
                return 'Linux - Unknown Browser'
        elif 'Mobile' in user_agent or 'iPhone' in user_agent or 'Android' in user_agent:
            return 'Mobile Device'
        else:
            return 'Unknown Device'
    
    @staticmethod
    def is_device_trusted(user_id):
        """Check if the current device is trusted for the given user"""
        fingerprint = TrustedDevice.generate_device_fingerprint()
        
        trusted_device = TrustedDevice.query.filter_by(
            user_id=user_id,
            device_fingerprint=fingerprint
        ).filter(
            TrustedDevice.expires_at > datetime.utcnow()
        ).first()
        
        if trusted_device:
            # Update last used timestamp
            trusted_device.last_used = datetime.utcnow()
            db.session.commit()
            return True, trusted_device.device_name
        
        return False, None
    
    @staticmethod
    def trust_device(user_id, trust_for_days=30):
        """Mark the current device as trusted for the specified number of days"""
        fingerprint = TrustedDevice.generate_device_fingerprint()
        device_name = TrustedDevice.get_device_name()
        
        # Check if device is already trusted
        existing = TrustedDevice.query.filter_by(
            user_id=user_id,
            device_fingerprint=fingerprint
        ).first()
        
        if existing:
            # Update existing trusted device
            existing.expires_at = datetime.utcnow() + timedelta(days=trust_for_days)
            existing.last_used = datetime.utcnow()
            existing.device_name = device_name  # Update device name in case it changed
        else:
            # Create new trusted device
            trusted_device = TrustedDevice(
                user_id=user_id,
                device_fingerprint=fingerprint,
                device_name=device_name,
                expires_at=datetime.utcnow() + timedelta(days=trust_for_days)
            )
            db.session.add(trusted_device)
        
        db.session.commit()
        return device_name
    
    @staticmethod
    def cleanup_expired_devices():
        """Remove expired trusted devices"""
        expired_devices = TrustedDevice.query.filter(
            TrustedDevice.expires_at < datetime.utcnow()
        ).all()
        
        for device in expired_devices:
            db.session.delete(device)
        
        db.session.commit()
        return len(expired_devices)
    
    @staticmethod
    def get_user_trusted_devices(user_id):
        """Get all trusted devices for a user"""
        return TrustedDevice.query.filter_by(user_id=user_id).filter(
            TrustedDevice.expires_at > datetime.utcnow()
        ).order_by(TrustedDevice.last_used.desc()).all()
    
    @staticmethod
    def revoke_device(user_id, device_id):
        """Revoke trust for a specific device"""
        device = TrustedDevice.query.filter_by(
            id=device_id,
            user_id=user_id
        ).first()
        
        if device:
            db.session.delete(device)
            db.session.commit()
            return True
        return False
