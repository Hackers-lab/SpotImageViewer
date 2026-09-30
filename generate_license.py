"""
Standalone Admin CLI Tool: Generate Bill Downloader Activation Keys.
Run this script anytime to generate an activation key for any user:
    python generate_license.py REQ-XXXX-XXXX-XXXX
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from core.services.license_service import generate_activation_key, get_machine_request_code

def main():
    print("=" * 60)
    print("  Bill Downloader - Admin License Key Generator")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        req_code = sys.argv[1].strip()
    else:
        print("\nCurrent PC Request Code:", get_machine_request_code())
        req_code = input("\nEnter User's Request Code (e.g. REQ-XXXX-XXXX-XXXX-XXXX): ").strip()
        
    if not req_code:
        print("Error: No request code entered.")
        return

    act_key = generate_activation_key(req_code)
    print("\n------------------------------------------------------------")
    print(f" Request Code  : {req_code.upper()}")
    print(f" Activation Key: {act_key}")
    print("------------------------------------------------------------\n")
    print("Send this Activation Key to the user. It will unlock the module permanently on their machine.")

if __name__ == "__main__":
    main()
