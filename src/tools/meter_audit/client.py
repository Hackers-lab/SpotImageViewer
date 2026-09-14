import json
import requests
from .constants import HEADERS, DEFAULT_BASE_URL, hk_encrypt

class SessionExpiredException(Exception):
    pass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def hk_encrypt(password_str):
    secret_key = "@FrTu^^&!#$%^/41"
    key_len = len(secret_key)
    xor_chars = []
    for r in range(len(password_str)):
        c_code = ord(password_str[r])
        k_code = ord(secret_key[r % key_len])
        xor_chars.append(chr(c_code ^ k_code))
    xor_str = "".join(xor_chars)
    # latin1 preserves the exact 0-255 byte values as characters
    return base64.b64encode(xor_str.encode('latin1')).decode('utf-8')

class TomcatAPIClient:
    def __init__(self, base_url=DEFAULT_BASE_URL):
        self.base_url = base_url.strip().rstrip('/')

    def _post(self, path, payload, content_type="application/json", timeout=10):
        url = f"{self.base_url}{path}"
        headers = HEADERS.copy()
        headers["Content-Type"] = content_type
        try:
            if content_type == "text/plain":
                data = json.dumps(payload)
                response = requests.post(url, data=data, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            res_json = response.json()
            # Intercept session expiration codes
            if isinstance(res_json, dict) and res_json.get("code") in ("100", "600"):
                raise SessionExpiredException(res_json.get("message", "Session expired (Code 100/600)"))
            elif isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], dict):
                if res_json[0].get("code") in ("100", "600"):
                    raise SessionExpiredException(res_json[0].get("message", "Session expired (Code 100/600)"))
            return res_json
        except requests.exceptions.HTTPError as he:
            if he.response is not None and he.response.status_code in (401, 403):
                raise SessionExpiredException("Authentication failed or session expired (401/403)")
            try:
                err_data = response.json()
                if isinstance(err_data, dict) and err_data.get("code") in ("100", "600"):
                    raise SessionExpiredException(err_data.get("message", "Session expired"))
                return err_data
            except Exception:
                raise Exception(f"HTTP Error {response.status_code}: {response.text}")
        except SessionExpiredException:
            raise
        except Exception as e:
            raise Exception(f"Network error: {str(e)}")

    def submit_for_otp(self, username, password):
        path = "/spotaiportal/spot_ai_portal_login"
        encrypted_password = hk_encrypt(password)
        payload = [{
            "username": username,
            "password": encrypted_password
        }]
        res = self._post(path, payload, content_type="text/plain")
        if isinstance(res, dict):
            return res
        elif isinstance(res, list) and len(res) > 0:
            return res[0]
        raise Exception("Invalid response format from server")

    def submit_final_otp(self, username, otp):
        path = "/spotaiportal/spot_ai_portal_login"
        payload = [{
            "username": username,
            "otp": otp
        }]
        res = self._post(path, payload, content_type="text/plain")
        if isinstance(res, dict):
            return res
        elif isinstance(res, list) and len(res) > 0:
            return res[0]
        raise Exception("Invalid response format from server")

    def verify_token(self, username, token):
        path = "/spotaiportal/spot_ai_portal_token_check"
        payload = [{"username": username, "token": token}]
        res = self._post(path, payload)
        if isinstance(res, dict):
            return res
        elif isinstance(res, list) and len(res) > 0:
            return res[0]
        raise Exception("Invalid response format from server")

    def fetch_smrd(self, username, token, off_code):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "parameter": "smrd"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return [item["smrd"] for item in res.get("message", []) if item.get("smrd")]
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch SMRD: {msg}")

    def fetch_mru(self, username, token, off_code, acc_month, acc_year):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "acc_month": acc_month,
            "acc_year": acc_year,
            "ccc_code": off_code,
            "parameter": "mru"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return [item["mru"] for item in res.get("message", []) if item.get("mru")]
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch MRU: {msg}")

    def fetch_queue(self, username, token, off_code, acc_month, acc_year, zone, ai_flag):
        path = "/spotaiportal/snapshot"
        
        # Mapping AI Flag to corresponding parameter as per JS bundle
        param_map = {
            "Accepted by Reader": "imagecheckingAIH",
            "Not Accepted by Reader": "imagecheckingAIM",
            "No Reading from AI Engine": "imagecheckingAIN",
            "Not under AI Scope": "imagecheckingAIU"
        }
        parameter = param_map.get(ai_flag, "imagecheckingAIH")

        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "acc_month": acc_month,
            "acc_year": acc_year,
            "zone": zone,
            "parameter": parameter
        }]
        
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return res.get("message", [])
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch batch queue: {msg}")

    def fetch_image_base64(self, username, token, off_code, photo_url):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "parameter": "getimagebase64",
            "connection_string": [{"URL": photo_url}]
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            msg_list = res.get("message", [])
            if msg_list and isinstance(msg_list, list):
                return msg_list[0].get("imagebase64")
        return None

    def fetch_conid_all(self, username, token, off_code, con_id):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "con_id": str(con_id),
            "parameter": "conid_all"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return res.get("message", [])
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch billing history: {msg}")

    def submit_audit_record(self, username, token, off_code, acc_month, acc_year, ccc_code, ccc_name, con_id, smrdn, verification_stat, meter_note=" ", sapdata="MIS", tariff=" "):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "acc_month": acc_month,
            "acc_year": acc_year,
            "ccc_code": ccc_code,
            "ccc_name": ccc_name,
            "con_id": str(con_id),
            "smrdn": smrdn if smrdn else " ",
            "verification_stat": verification_stat,
            "meter_note": meter_note if meter_note else " ",
            "sapdata": sapdata,
            "tariff": tariff if tariff else " ",
            "parameter": "imagecheckinginsert"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict):
            code = res.get("code")
            msg = res.get("message", "")
            if code == "200" or "SUCCESS" in str(msg).upper():
                return True, msg
            else:
                return False, f"Code {code}: {msg}"
        elif isinstance(res, list) and len(res) > 0:
            msg = str(res[0])
            if "SUCCESS" in msg.upper():
                return True, msg
            return False, msg
        return False, str(res)

