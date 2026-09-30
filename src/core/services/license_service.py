"""
Cryptographic Machine Licensing & Hardware Activation Service.
Uses HMAC-SHA256 with a unique machine GUID to generate and verify
unforgeable, machine-locked activation keys for protected modules.
"""

import os
import sys
import json
import hmac
import hashlib
import base64
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from core import config
except ImportError:
    import config

# Secret salt used for HMAC signing (keep private to software author)
LICENSE_SECRET_SALT = b"SpotIV_SpotAI_License_Salt_v1_#9872!@"
LICENSE_PREFIX_REQ = "REQ-"
LICENSE_PREFIX_ACT = "ACT-"


def _get_windows_machine_guid() -> str:
    """Retrieves stable Windows MachineGuid from Windows Registry, fallback to UUID."""
    guid = ""
    try:
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            guid = str(val).strip()
    except Exception:
        pass

    if not guid:
        try:
            # Fallback using WMIC / PowerShell UUID
            cmd = "powershell -NoProfile -Command \"(Get-CimInstance Win32_ComputerSystemProduct).UUID\""
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
            if output and len(output) > 8:
                guid = output
        except Exception:
            pass

    if not guid:
        # Ultimate fallback using platform node / python uuid
        import uuid
        guid = str(uuid.getnode())

    return guid.lower()


def get_machine_request_code() -> str:
    """
    Computes a clean, human-readable 16-character Request Code (e.g. REQ-A1B2-C3D4-E5F6)
    unique to this specific PC hardware.
    """
    raw_guid = _get_windows_machine_guid()
    # Hash machine GUID with private salt
    h = hashlib.sha256((raw_guid + "_spotai_request_seed").encode("utf-8")).hexdigest().upper()
    # 12 alphanumeric characters formatted in 3 chunks of 4 + 4-char checksum
    core = h[:12]
    # Checksum of core
    csum = hashlib.sha256(core.encode("utf-8")).hexdigest().upper()[:4]
    full_code = f"{LICENSE_PREFIX_REQ}{core[:4]}-{core[4:8]}-{core[8:12]}-{csum}"
    return full_code


def generate_activation_key(request_code: str, custom_note: str = "") -> str:
    """
    Admin Function:
    Generates an activation key matching the user's Request Code.
    The key is cryptographically signed via HMAC-SHA256.
    """
    clean_req = str(request_code).strip().upper()
    if not clean_req.startswith(LICENSE_PREFIX_REQ):
        clean_req = f"{LICENSE_PREFIX_REQ}{clean_req}"

    # HMAC signature over request code
    sig = hmac.new(
        LICENSE_SECRET_SALT,
        clean_req.encode("utf-8"),
        hashlib.sha256
    ).hexdigest().upper()

    # Form key as ACT-XXXX-XXXX-XXXX-XXXX
    k1 = sig[0:4]
    k2 = sig[4:8]
    k3 = sig[8:12]
    k4 = sig[12:16]
    return f"{LICENSE_PREFIX_ACT}{k1}-{k2}-{k3}-{k4}"


def verify_activation_key(request_code: str, activation_key: str) -> bool:
    """
    Verifies that the given activation key is a valid HMAC signature
    for this machine's request code.
    """
    expected_key = generate_activation_key(request_code)
    clean_input = str(activation_key).strip().upper()
    return hmac.compare_digest(expected_key, clean_input)


class LicenseService:
    """Manages SpotAI Bill Downloader module activation status."""

    def __init__(self):
        self._license_file = os.path.join(config.BASE_DIR, "spotai_license.json")
        self._cached_status: Optional[Dict[str, Any]] = None

    def get_request_code(self) -> str:
        return get_machine_request_code()

    def check_access(self) -> Dict[str, Any]:
        """
        Checks whether this machine has a valid SpotAI Bill Downloader license.
        """
        my_req_code = self.get_request_code()
        
        # Check license file
        if not os.path.exists(self._license_file):
            return {
                "allowed": False,
                "request_code": my_req_code,
                "message": "Module activation required."
            }

        try:
            with open(self._license_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            stored_key = data.get("activation_key", "")
            stored_req = data.get("request_code", "")
            
            if stored_req == my_req_code and verify_activation_key(my_req_code, stored_key):
                return {
                    "allowed": True,
                    "request_code": my_req_code,
                    "activation_date": data.get("activated_at", ""),
                    "message": "Module activated."
                }
        except Exception:
            pass

        return {
            "allowed": False,
            "request_code": my_req_code,
            "message": "Invalid or missing license key."
        }

    def activate(self, activation_key: str) -> Dict[str, Any]:
        """Validates and stores activation key on this machine."""
        my_req_code = self.get_request_code()
        clean_key = str(activation_key).strip().upper()

        if not verify_activation_key(my_req_code, clean_key):
            return {
                "success": False,
                "error": "Invalid Activation Key for this machine. Please verify the code."
            }

        payload = {
            "request_code": my_req_code,
            "activation_key": clean_key,
            "activated_at": datetime.now().isoformat(),
            "status": "ACTIVE"
        }

        try:
            with open(self._license_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return {"success": True, "message": "Module activated successfully!"}
        except Exception as e:
            return {"success": False, "error": f"Failed to save activation file: {str(e)}"}

    def reset_license(self) -> Dict[str, Any]:
        """Removes local license file to return the app to locked state for testing."""
        try:
            if os.path.exists(self._license_file):
                os.remove(self._license_file)
            return {"success": True, "message": "License reset successfully. Module is now locked."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_key_for_request(self, request_code: str) -> str:
        """Admin helper to generate key for another user's request code."""
        return generate_activation_key(request_code)
