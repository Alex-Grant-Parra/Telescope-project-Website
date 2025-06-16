from db import db

class Telescope(db.Model):
    __tablename__ = 'telescopes'

    id = db.Column(db.Integer, primary_key=True)
    telescopeId = db.Column(db.String(100), unique=True, nullable=False)
    ipAddress = db.Column(db.String(45), nullable=False)  # supports IPv6 too
    firmwareVersion = db.Column(db.String(50), nullable=False)
    capabilities = db.Column(db.Text)  # store as JSON string or comma-separated
    lastSeen = db.Column(db.Float, nullable=False)

    def __init__(self, telescopeId, ipAddress, firmwareVersion, capabilities=None, lastSeen=None):
        self.telescopeId = telescopeId
        self.ipAddress = ipAddress
        self.firmwareVersion = firmwareVersion
        self.capabilities = capabilities if capabilities else ''
        self.lastSeen = lastSeen if lastSeen else 0.0

    def toDict(self):
        return {
            "telescopeId": self.telescopeId,
            "ipAddress": self.ipAddress,
            "firmwareVersion": self.firmwareVersion,
            "capabilities": self.capabilities.split(',') if self.capabilities else [],
            "lastSeen": self.lastSeen
        }
