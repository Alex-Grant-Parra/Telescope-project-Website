"""
Flask Security Middleware for IP Blacklisting
Provides request filtering and security logging for the Telescope project
"""

from flask import Flask, request, jsonify, abort
import logging
from datetime import datetime
from typing import Dict, Any
import json
from pathlib import Path
from .ip_blacklist import get_blacklist

class SecurityMiddleware:
    def __init__(self, app: Flask = None, log_file: str = None):
        """
        Initialize Security Middleware
        
        Args:
            app: Flask application instance
            log_file: Path to security log file
        """
        self.app = app
        self.blacklist = get_blacklist()
        
        # Setup security logging
        if log_file is None:
            log_file = Path(__file__).parent / 'logs' / 'security.log'
        
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure security logger
        self.security_logger = logging.getLogger('security')
        self.security_logger.setLevel(logging.INFO)
        
        # Create file handler for security logs
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler if not already added
        if not self.security_logger.handlers:
            self.security_logger.addHandler(file_handler)
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize middleware with Flask app"""
        self.app = app
        
        # Register before_request handler
        app.before_request(self._before_request)
        
        # Register security routes
        self._register_security_routes()
        
        self.security_logger.info("Security middleware initialized")
    
    def _get_client_ip(self) -> str:
        """Get the real client IP address"""
        # Check for various forwarded headers (for reverse proxy scenarios)
        forwarded_headers = [
            'CF-Connecting-IP',  # Cloudflare
            'X-Forwarded-For',   # Standard proxy header
            'X-Real-IP',         # Nginx
            'X-Client-IP',       # Alternative
        ]
        
        for header in forwarded_headers:
            ip = request.headers.get(header)
            if ip:
                # Take the first IP if comma-separated
                return ip.split(',')[0].strip()
        
        # Fallback to remote_addr
        return request.remote_addr or 'unknown'
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events"""
        client_ip = self._get_client_ip()
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'client_ip': client_ip,
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'method': request.method,
            'url': request.url,
            'path': request.path,
            'details': details
        }
        
        # Log to file
        self.security_logger.info(json.dumps(log_entry))
        
        return log_entry
    
    def _is_suspicious_request(self) -> Dict[str, Any]:
        """Check if request is suspicious"""
        suspicious_indicators = {}
        
        # Check for common attack patterns in URL
        suspicious_paths = [
            'cgi-bin', 'phpunit', 'wp-admin', 'wp-content', '.php',
            'eval-stdin', 'shell', '/bin/', 'cmd.exe', 'powershell',
            '../', '..\\', '%2e%2e', 'etc/passwd', 'boot.ini'
        ]
        
        path_lower = request.path.lower()
        query_lower = request.query_string.decode('utf-8', errors='ignore').lower()
        
        for pattern in suspicious_paths:
            if pattern in path_lower or pattern in query_lower:
                suspicious_indicators['suspicious_path'] = pattern
                break
        
        # Check for suspicious headers
        user_agent = request.headers.get('User-Agent', '').lower()
        suspicious_agents = [
            'sqlmap', 'nikto', 'nmap', 'masscan', 'zap', 'burp',
            'crawler', 'bot', 'spider', 'scanner'
        ]
        
        for agent in suspicious_agents:
            if agent in user_agent:
                suspicious_indicators['suspicious_user_agent'] = agent
                break
        
        # Check for unusual methods
        if request.method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
            suspicious_indicators['unusual_method'] = request.method
        
        # Check for suspicious content types
        content_type = request.headers.get('Content-Type', '').lower()
        if 'php' in content_type or 'eval' in content_type:
            suspicious_indicators['suspicious_content_type'] = content_type
        
        return suspicious_indicators
    
    def _before_request(self):
        """Handle request before processing"""
        client_ip = self._get_client_ip()
        
        # Skip security checks for localhost in development
        if client_ip in ['127.0.0.1', '::1', 'localhost'] and self.app.debug:
            return
        
        # Check if IP is blacklisted
        if self.blacklist.is_ip_blacklisted(client_ip):
            self._log_security_event('blocked_request', {
                'reason': 'ip_blacklisted',
                'blocked_ip': client_ip
            })
            
            # Return 403 Forbidden
            abort(403)
        
        # Check for suspicious activity
        suspicious_indicators = self._is_suspicious_request()
        if suspicious_indicators:
            self._log_security_event('suspicious_request', suspicious_indicators)
            
            # For highly suspicious requests, consider blocking
            high_risk_indicators = ['suspicious_path', 'unusual_method']
            if any(indicator in suspicious_indicators for indicator in high_risk_indicators):
                # Optionally auto-blacklist aggressive attackers
                self.blacklist.add_manual_ip(client_ip)
                
                self._log_security_event('auto_blacklisted', {
                    'reason': 'aggressive_attack_pattern',
                    'indicators': suspicious_indicators
                })
                
                abort(403)
    
    def _register_security_routes(self):
        """Register security management routes"""
        
        @self.app.route('/admin/security/status')
        def security_status():
            """Get security system status"""
            # This should be protected by admin authentication
            stats = self.blacklist.get_stats()
            return jsonify({
                'status': 'active',
                'blacklist_stats': stats,
                'blacklist_file': stats.get('blacklist_file'),
                'log_file': str(self.log_file)
            })
        
        @self.app.route('/admin/security/blacklist/add', methods=['POST'])
        def add_to_blacklist():
            """Manually add IP to blacklist"""
            # This should be protected by admin authentication
            data = request.get_json()
            if not data or 'ip' not in data:
                return jsonify({'error': 'IP address required'}), 400
            
            ip = data['ip']
            if self.blacklist.add_manual_ip(ip):
                self._log_security_event('manual_blacklist_add', {'ip': ip})
                return jsonify({'message': f'Added {ip} to blacklist'})
            else:
                return jsonify({'error': 'Invalid IP address'}), 400
        
        @self.app.route('/admin/security/blacklist/remove', methods=['POST'])
        def remove_from_blacklist():
            """Remove IP from blacklist"""
            # This should be protected by admin authentication
            data = request.get_json()
            if not data or 'ip' not in data:
                return jsonify({'error': 'IP address required'}), 400
            
            ip = data['ip']
            if self.blacklist.remove_ip(ip):
                self._log_security_event('manual_blacklist_remove', {'ip': ip})
                return jsonify({'message': f'Removed {ip} from blacklist'})
            else:
                return jsonify({'error': 'IP not found in blacklist'}), 404
        
        @self.app.route('/admin/security/logs')
        def get_security_logs():
            """Get recent security logs"""
            # This should be protected by admin authentication
            try:
                logs = []
                if self.log_file.exists():
                    with open(self.log_file, 'r') as f:
                        # Get last 100 lines
                        lines = f.readlines()[-100:]
                        for line in lines:
                            try:
                                log_entry = json.loads(line.strip())
                                logs.append(log_entry)
                            except json.JSONDecodeError:
                                continue
                
                return jsonify({'logs': logs})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

# Error handlers for security responses
def register_security_error_handlers(app: Flask):
    """Register custom error handlers for security responses"""
    
    @app.errorhandler(403)
    def forbidden(e):
        """Custom 403 response"""
        return jsonify({
            'error': 'Access forbidden',
            'message': 'Your request was blocked for security reasons'
        }), 403
    
    @app.errorhandler(429)
    def too_many_requests(e):
        """Custom 429 response"""
        return jsonify({
            'error': 'Too many requests',
            'message': 'Rate limit exceeded'
        }), 429