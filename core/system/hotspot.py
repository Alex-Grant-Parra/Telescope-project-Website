import subprocess
import os
import re
import tempfile

class HotspotController:
    def __init__(self, interface='wlan0', dhcp_range="192.168.50.10,192.168.50.50,12h"):
        self.interface = interface
        self.hostapd_process = None
        self.dhcp_process = None
        self.dhcp_range = dhcp_range
        self.temp_dir = tempfile.gettempdir()
        self.hostapd_conf_path = os.path.join(self.temp_dir, "hostapd.conf")
        self.dnsmasq_conf_path = os.path.join(self.temp_dir, "dnsmasq.conf")
        self.original_ip = None

    # -----------------------------
    # Start hotspot
    # -----------------------------
    def startHotspot(self, ssid: str, password: str):
        # Bring interface up
        subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"], check=True)

        # Save current IP (if any) to restore later
        try:
            output = subprocess.check_output(["ip", "-4", "addr", "show", "dev", self.interface]).decode()
            lines = [line.strip() for line in output.splitlines()]
            for line in lines:
                if line.startswith("inet "):
                    self.original_ip = line.split()[1]  # e.g., 192.168.0.165/24
                    break
        except subprocess.CalledProcessError:
            self.original_ip = None

        # Flush existing IP addresses
        subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.interface], check=True)

        # Assign hotspot IP
        subprocess.run(["sudo", "ip", "addr", "add", "192.168.50.1/24", "dev", self.interface], check=True)

        # Kill any existing hostapd/dnsmasq
        subprocess.run(["sudo", "killall", "hostapd", "dnsmasq"], check=False)

        # Write hostapd config
        hostapd_conf = "\n".join([
            f"interface={self.interface}",
            "driver=nl80211",
            f"ssid={ssid}",
            "hw_mode=g",
            "channel=6",
            "wmm_enabled=0",
            "macaddr_acl=0",
            "auth_algs=1",
            "ignore_broadcast_ssid=0",
            "wpa=2",
            f"wpa_passphrase={password}",
            "wpa_key_mgmt=WPA-PSK",
            "rsn_pairwise=CCMP"
        ])


        with open(self.hostapd_conf_path, "w") as f:
            f.write(hostapd_conf)

        # Write dnsmasq config
        dnsmasq_conf = f"""
        interface={self.interface}
        dhcp-range={self.dhcp_range}
        no-resolv
        port=0
        log-queries
        log-dhcp
        """

        with open(self.dnsmasq_conf_path, "w") as f:
            f.write(dnsmasq_conf)

        # Start dnsmasq
        self.dhcp_process = subprocess.Popen(["sudo", "/usr/sbin/dnsmasq", "-C", self.dnsmasq_conf_path])

        # Start hostapd
        self.hostapd_process = subprocess.Popen(["sudo", "/usr/sbin/hostapd", self.hostapd_conf_path])

        print(f"[✓] Hotspot started: SSID='{ssid}', PASSWORD='{password}'")

    # -----------------------------
    # Stop hotspot
    # -----------------------------
    def stopHotspot(self):
        # Stop hostapd
        if self.hostapd_process:
            self.hostapd_process.terminate()
            self.hostapd_process.wait()
            self.hostapd_process = None

        # Stop dnsmasq
        if self.dhcp_process:
            self.dhcp_process.terminate()
            self.dhcp_process.wait()
            self.dhcp_process = None

        # Flush hotspot IP
        subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.interface], check=False)

        # Restore original IP (if any)
        if self.original_ip:
            subprocess.run(["sudo", "ip", "addr", "add", self.original_ip, "dev", self.interface], check=False)

        print("[✓] Hotspot stopped.")

    # -----------------------------
    # Check if hotspot is active
    # -----------------------------
    def isHotspotActive(self):
        return self.hostapd_process is not None and self.hostapd_process.poll() is None

    # -----------------------------
    # Get connected devices
    # -----------------------------
    def getConnectedDevices(self):
        devices = []
        try:
            output = subprocess.check_output(["arp", "-n"]).decode()
            pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+\S+\s+(\S+)\s+\S+\s+(\S+)")
            for match in pattern.findall(output):
                ip, hwtype, mac = match
                if mac != "(incomplete)":
                    devices.append({"ip": ip, "mac": mac})
        except subprocess.CalledProcessError:
            pass
        return devices
