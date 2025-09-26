"""
Security Configuration for Telescope Project
"""

# IP Blacklist Configuration
BLACKLIST_CONFIG = {
    'update_interval': 3600,  # Update every hour (3600 seconds)
    'blacklist_file': 'security/blacklist.txt',  # Simple text file with one IP per line
    'log_file': 'security/logs/security.log',
    'enable_auto_blacklist': True,  # Automatically blacklist aggressive attackers
    'aggressive_threshold': 3,  # Number of suspicious requests before auto-blacklist
}

# Threat Intelligence Sources
# You can enable/disable sources by setting 'enabled': False
THREAT_SOURCES = {
    'spamhaus_drop': {
        'enabled': True,
        'description': 'Spamhaus DROP list - known bad networks'
    },
    'spamhaus_edrop': {
        'enabled': False,
        'description': 'Spamhaus EDROP list - extended bad networks'
    },
    'emergingthreats': {
        'enabled': True,
        'description': 'Emerging Threats IP list'
    },
    'blocklist_de': {
        'enabled': True,
        'description': 'Blocklist.de - failed login attempts and compromised hosts'
    },
    'cinsscore': {
        'enabled': False,  # Sometimes unreliable
        'description': 'CINS Score bad guys list'
    },
    'greensnow': {
        'enabled': True,
        'description': 'GreenSnow blacklist'
    }
}

# Manual IP blocks (IPs that are always blocked)
MANUAL_BLOCKS = [
    '38.211.193.130',  # The IP that attacked your server
    '38.211.193.0/24'  # Block the entire subnet for safety
]

# Suspicious request patterns
SUSPICIOUS_PATTERNS = {
    'paths': [
        'cgi-bin', 'phpunit', 'wp-admin', 'wp-content', '.php',
        'eval-stdin', 'shell', '/bin/', 'cmd.exe', 'powershell',
        '../', '..\\', '%2e%2e', 'etc/passwd', 'boot.ini',
        'proc/self', 'windows/system32'
    ],
    'user_agents': [
        'sqlmap', 'nikto', 'nmap', 'masscan', 'zap', 'burp',
        'crawler', 'bot', 'spider', 'scanner', 'exploit'
    ]
}

# Rate limiting (requests per IP per minute)
RATE_LIMITS = {
    'default': 60,      # 60 requests per minute for normal users
    'suspicious': 10,   # 10 requests per minute for suspicious IPs
    'blocked': 0        # 0 requests for blocked IPs
}

# Security logging
LOGGING_CONFIG = {
    'log_blocked_requests': True,
    'log_suspicious_requests': True,
    'log_successful_requests': False,  # Only log security events
    'max_log_size_mb': 10,  # Rotate logs when they exceed 10MB
    'backup_count': 5       # Keep 5 backup log files
}