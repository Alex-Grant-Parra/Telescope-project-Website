"""
Test script for the IP blacklist security system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from security.ip_blacklist import IPBlacklist
import logging

def test_blacklist():
    """Test the IP blacklist functionality"""
    print("Testing IP Blacklist System")
    print("=" * 40)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create blacklist instance
    print("1. Creating blacklist instance...")
    blacklist = IPBlacklist(blacklist_file='test_blacklist.txt', update_interval=3600)
    
    # Test with known malicious IP
    malicious_ip = "38.211.193.130"
    print(f"2. Testing malicious IP: {malicious_ip}")
    is_blocked = blacklist.is_ip_blacklisted(malicious_ip)
    print(f"   Is {malicious_ip} blocked? {is_blocked}")
    
    # Test with localhost (should not be blocked)
    localhost = "127.0.0.1"
    print(f"3. Testing localhost: {localhost}")
    is_blocked = blacklist.is_ip_blacklisted(localhost)
    print(f"   Is {localhost} blocked? {is_blocked}")
    
    # Add a test IP manually
    test_ip = "192.168.1.100"
    print(f"4. Manually adding test IP: {test_ip}")
    success = blacklist.add_manual_ip(test_ip)
    print(f"   Added successfully? {success}")
    
    # Test the manually added IP
    print(f"5. Testing manually added IP: {test_ip}")
    is_blocked = blacklist.is_ip_blacklisted(test_ip)
    print(f"   Is {test_ip} blocked? {is_blocked}")
    
    # Test CIDR range
    print(f"6. Testing CIDR range blocking...")
    cidr_test_ip = "38.211.193.150"  # Should be in the blocked range
    is_blocked = blacklist.is_ip_blacklisted(cidr_test_ip)
    print(f"   Is {cidr_test_ip} blocked (should be in 38.211.193.0/24)? {is_blocked}")
    
    # Get stats
    print(f"7. Blacklist statistics:")
    stats = blacklist.get_stats()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Last update: {stats['last_update']}")
    print(f"   Sources: {', '.join(stats['sources'])}")
    
    # Clean up test file
    try:
        os.remove('test_blacklist.txt')
        print("8. Cleaned up test blacklist file")
    except FileNotFoundError:
        pass
    
    print("\n✓ All tests completed!")

if __name__ == "__main__":
    test_blacklist()