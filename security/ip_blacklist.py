"""
IP Blacklist Manager for Telescope Project
Fetches malicious IPs from multiple threat intelligence sources
and provides blocking functionality for Flask applications.
"""

import requests
import ipaddress
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Set, List, Dict
from pathlib import Path
import os

class IPBlacklist:
    def __init__(self, blacklist_file='blacklist.txt', update_interval=3600):
        """
        Initialize IP Blacklist Manager
        
        Args:
            blacklist_file: Local txt file to store blacklisted IPs
            update_interval: How often to update the blacklist (seconds)
        """
        self.blacklist_file = Path(blacklist_file)
        self.update_interval = update_interval
        self.blacklisted_ips = set()
        self.last_update = None
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        
        # Threat intelligence sources (free/public sources)
        self.sources = {
            'spamhaus_drop': {
                'url': 'https://www.spamhaus.org/drop/drop.txt',
                'parser': self._parse_spamhaus_drop
            },
            'spamhaus_edrop': {
                'url': 'https://www.spamhaus.org/drop/edrop.txt',
                'parser': self._parse_spamhaus_drop
            },
            'emergingthreats': {
                'url': 'https://rules.emergingthreats.net/fwrules/emerging-Block-IPs.txt',
                'parser': self._parse_simple_list
            },
            'blocklist_de': {
                'url': 'https://lists.blocklist.de/lists/all.txt',
                'parser': self._parse_simple_list
            },
            'cinsscore': {
                'url': 'http://cinsscore.com/list/ci-badguys.txt',
                'parser': self._parse_simple_list
            },
            'greensnow': {
                'url': 'https://blocklist.greensnow.co/greensnow.txt',
                'parser': self._parse_simple_list
            }
        }
        
        # Load existing blacklist
        self._load_blacklist()
        
        # Start background update thread
        self._start_background_updater()
    
    def _parse_spamhaus_drop(self, content: str) -> Set[str]:
        """Parse Spamhaus DROP/EDROP format"""
        ips = set()
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith(';') and not line.startswith('#'):
                # Extract CIDR block (first part before semicolon)
                if ';' in line:
                    cidr = line.split(';')[0].strip()
                    if self._is_valid_cidr(cidr):
                        ips.add(cidr)
        return ips
    
    def _parse_simple_list(self, content: str) -> Set[str]:
        """Parse simple IP list format"""
        ips = set()
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith(';'):
                if self._is_valid_ip_or_cidr(line):
                    ips.add(line)
        return ips
    
    def _is_valid_ip_or_cidr(self, ip_str: str) -> bool:
        """Check if string is valid IP address or CIDR block"""
        try:
            ipaddress.ip_network(ip_str, strict=False)
            return True
        except ValueError:
            return False
    
    def _is_valid_cidr(self, cidr_str: str) -> bool:
        """Check if string is valid CIDR block"""
        try:
            ipaddress.ip_network(cidr_str, strict=False)
            return '/' in cidr_str
        except ValueError:
            return False
    
    def _fetch_from_source(self, source_name: str, source_config: Dict) -> Set[str]:
        """Fetch IPs from a single source"""
        try:
            self.logger.info(f"Fetching IPs from {source_name}")
            response = requests.get(
                source_config['url'], 
                timeout=30,
                headers={'User-Agent': 'Telescope-Security-Bot/1.0'}
            )
            response.raise_for_status()
            
            ips = source_config['parser'](response.text)
            self.logger.info(f"Fetched {len(ips)} IPs from {source_name}")
            return ips
            
        except Exception as e:
            self.logger.error(f"Failed to fetch from {source_name}: {str(e)}")
            return set()
    
    def update_blacklist(self) -> bool:
        """Update blacklist from all sources"""
        self.logger.info("Starting blacklist update")
        new_ips = set()
        
        for source_name, source_config in self.sources.items():
            source_ips = self._fetch_from_source(source_name, source_config)
            new_ips.update(source_ips)
            time.sleep(1)  # Be nice to the servers
        
        # Add some known bad IPs manually (like the one you encountered)
        manual_bad_ips = {
            '38.211.193.130',  # The IP that attacked you
            '38.211.193.0/24'  # Block the entire subnet
        }
        new_ips.update(manual_bad_ips)
        
        with self._lock:
            self.blacklisted_ips = new_ips
            self.last_update = datetime.now()
        
        self._save_blacklist()
        self.logger.info(f"Updated blacklist with {len(new_ips)} IPs/ranges")
        return True
    
    def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if an IP address is blacklisted"""
        try:
            client_ip = ipaddress.ip_address(ip)
            
            with self._lock:
                for blocked_item in self.blacklisted_ips:
                    try:
                        if '/' in blocked_item:
                            # CIDR range
                            network = ipaddress.ip_network(blocked_item, strict=False)
                            if client_ip in network:
                                return True
                        else:
                            # Single IP
                            if client_ip == ipaddress.ip_address(blocked_item):
                                return True
                    except ValueError:
                        continue
            
            return False
            
        except ValueError:
            # Invalid IP address
            return False
    
    def add_manual_ip(self, ip: str) -> bool:
        """Manually add an IP to the blacklist"""
        if self._is_valid_ip_or_cidr(ip):
            with self._lock:
                self.blacklisted_ips.add(ip)
            self._save_blacklist()
            self.logger.info(f"Manually added {ip} to blacklist")
            return True
        return False
    
    def remove_ip(self, ip: str) -> bool:
        """Remove an IP from the blacklist"""
        with self._lock:
            if ip in self.blacklisted_ips:
                self.blacklisted_ips.remove(ip)
                self._save_blacklist()
                self.logger.info(f"Removed {ip} from blacklist")
                return True
        return False
    
    def get_stats(self) -> Dict:
        """Get blacklist statistics"""
        with self._lock:
            return {
                'total_entries': len(self.blacklisted_ips),
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'sources': list(self.sources.keys()),
                'blacklist_file': str(self.blacklist_file)
            }
    
    def _save_blacklist(self):
        """Save blacklist to text file"""
        try:
            # Ensure directory exists
            self.blacklist_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.blacklist_file, 'w') as f:
                # Write header with update info
                f.write(f"# Telescope Project IP Blacklist\n")
                f.write(f"# Last updated: {datetime.now().isoformat()}\n")
                f.write(f"# Total entries: {len(self.blacklisted_ips)}\n")
                f.write(f"# Sources: {', '.join(self.sources.keys())}\n")
                f.write(f"#\n")
                f.write(f"# Format: One IP address or CIDR range per line\n")
                f.write(f"# Lines starting with # are comments\n")
                f.write(f"#\n\n")
                
                # Write all IPs, sorted for easier reading
                sorted_ips = sorted(self.blacklisted_ips)
                for ip in sorted_ips:
                    f.write(f"{ip}\n")
                
            self.logger.info(f"Saved {len(self.blacklisted_ips)} IPs to {self.blacklist_file}")
                
        except Exception as e:
            self.logger.error(f"Failed to save blacklist: {str(e)}")
    
    def _load_blacklist(self):
        """Load blacklist from text file"""
        try:
            if self.blacklist_file.exists():
                with open(self.blacklist_file, 'r') as f:
                    loaded_ips = set()
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            if self._is_valid_ip_or_cidr(line):
                                loaded_ips.add(line)
                            else:
                                self.logger.warning(f"Invalid IP/CIDR in blacklist file: {line}")
                
                self.blacklisted_ips = loaded_ips
                self.logger.info(f"Loaded {len(self.blacklisted_ips)} IPs from {self.blacklist_file}")
                
                # Try to extract last update time from file header
                with open(self.blacklist_file, 'r') as f:
                    for line in f:
                        if line.startswith('# Last updated:'):
                            try:
                                date_str = line.split('Last updated: ')[1].strip()
                                self.last_update = datetime.fromisoformat(date_str)
                                break
                            except (IndexError, ValueError):
                                pass
            else:
                # No blacklist file, do initial update
                self.logger.info("No blacklist file found, performing initial update")
                self.update_blacklist()
                
        except Exception as e:
            self.logger.error(f"Failed to load blacklist: {str(e)}")
            # Fallback to manual bad IPs
            self.blacklisted_ips = {'38.211.193.130', '38.211.193.0/24'}
            self._save_blacklist()
    
    def _start_background_updater(self):
        """Start background thread for periodic updates"""
        def updater():
            while True:
                try:
                    if (self.last_update is None or 
                        datetime.now() - self.last_update > timedelta(seconds=self.update_interval)):
                        self.update_blacklist()
                    time.sleep(300)  # Check every 5 minutes
                except Exception as e:
                    self.logger.error(f"Background updater error: {str(e)}")
                    time.sleep(300)
        
        updater_thread = threading.Thread(target=updater, daemon=True)
        updater_thread.start()
        self.logger.info("Started background blacklist updater")

# Global instance
_blacklist_instance = None

def get_blacklist():
    """Get global blacklist instance"""
    global _blacklist_instance
    if _blacklist_instance is None:
        # Store blacklist.txt in the security directory
        blacklist_file = Path(__file__).parent / 'blacklist.txt'
        _blacklist_instance = IPBlacklist(blacklist_file=blacklist_file)
    return _blacklist_instance

if __name__ == "__main__":
    # Test the blacklist
    logging.basicConfig(level=logging.INFO)
    blacklist = IPBlacklist(blacklist_file="test_blacklist.txt")
    
    # Test with the malicious IP
    test_ip = "38.211.193.130"
    print(f"Is {test_ip} blacklisted? {blacklist.is_ip_blacklisted(test_ip)}")
    
    # Show stats
    stats = blacklist.get_stats()
    print(f"Blacklist stats: {stats}")
    
    # Show location of blacklist file
    print(f"Blacklist file: {blacklist.blacklist_file}")