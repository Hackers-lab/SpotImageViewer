"""
Live OSD Service (WBSEDCL Portal PDF Fetcher & Parser)
Production-ready implementation with thread-safe caching and resilient network handling.
"""

import re
import io
import time
import base64
from typing import Optional, Dict, Any
from urllib.parse import urljoin
import requests
from pypdf import PdfReader


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BASE_PORTAL_URL = "https://portal.wbsedcl.in/webdynpro/resources/wbsedcl/noduesandoutstandingreport/OutstandingReport"

# In-memory cache to prevent spamming the portal for repeatedly selected consumers
# Format: {consumer_id: (timestamp, result_dict, pdf_bytes)}
_OSD_CACHE = {}
_CACHE_TTL = 900  # 15 minutes TTL


def _decode_sap_url(raw_url: str) -> str:
    """Decodes SAP WebDynpro \\x hex-encoded strings and HTML entities."""
    decoded = re.sub(
        r"\\x([0-9a-fA-F]{2})",
        lambda m: chr(int(m.group(1), 16)),
        raw_url
    )
    decoded = decoded.replace("&amp;", "&")
    return decoded


def fetch_live_osd_pdf(consumer_id: str, timeout: int = 25) -> bytes:
    """
    Handles network negotiation, SAP cookie handshakes, and URL redirection
    to fetch raw PDF binary bytes from WBSEDCL WebDynpro portal.
    """
    clean_id = str(consumer_id).strip()
    if not re.match(r"^\d{9}$", clean_id):
        raise ValueError("Invalid Consumer ID. Must be a 9-digit number.")

    target_url = f"{BASE_PORTAL_URL}?consumerId={clean_id}"

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
    }

    session = requests.Session()
    session.headers.update(headers)

    # Step 1: Initial Request
    res = session.get(target_url, timeout=timeout)
    res.raise_for_status()

    content = res.content

    # Handle empty 0-byte initial handshake (SAP sets cookies and expects immediate retry)
    if len(content) == 0:
        res = session.get(target_url, timeout=timeout)
        res.raise_for_status()
        content = res.content

    # Check if direct PDF was returned
    if content.startswith(b"%PDF-"):
        return content

    # Step 2: Parse HTML / SAP WebDynpro openExternalWindow redirect
    html_text = content.decode("utf-8", errors="ignore")

    match = (
        re.search(r"openExternalWindow\([^,]+,\s*['\"]([^'\"]+?)['\"]", html_text, re.IGNORECASE) or
        re.search(r"openExternalWindow\([^)]*?['\"]([^'\"]*?\.pdf[^'\"]*?)['\"]", html_text, re.IGNORECASE) or
        re.search(r"['\"]([^'\"]*?\.pdf(?:\?[^'\"]*)?)['\"]", html_text, re.IGNORECASE) or
        re.search(r"href=['\"]([^'\"]+\.pdf[^'\"]*)['\"]", html_text, re.IGNORECASE) or
        re.search(r"window\.open\(['\"]([^'\"]+?)['\"]", html_text, re.IGNORECASE) or
        re.search(r"location\.href\s*=\s*['\"]([^'\"]+?)['\"]", html_text, re.IGNORECASE)
    )

    if not match:
        raise RuntimeError("No PDF redirect link or stream found in portal response.")

    raw_rel_url = match.group(1)
    decoded_url = _decode_sap_url(raw_rel_url)
    pdf_url = urljoin(target_url, decoded_url)

    # Step 3: Fetch the actual PDF stream
    pdf_headers = {
        "Accept": "application/pdf,application/octet-stream,*/*",
        "Referer": target_url,
    }
    pdf_res = session.get(pdf_url, headers=pdf_headers, timeout=timeout)
    pdf_res.raise_for_status()

    pdf_bytes = pdf_res.content
    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError("Retrieved payload does not have valid %PDF- magic bytes.")

    return pdf_bytes


def parse_osd_pdf(pdf_bytes: bytes, consumer_id: str) -> Dict[str, Any]:
    """
    Parses PDF bytes, extracts fields via regex, and calculates statuses.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted_text_pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(extracted_text_pages)

    upper_text = text.upper()

    # Document Type
    if "NO DUES CERTIFICATE" in upper_text:
        doc_type = "NO DUES CERTIFICATE"
    elif "OUTSTANDING REPORT" in upper_text:
        doc_type = "OUTSTANDING REPORT"
    else:
        doc_type = "UNKNOWN"

    # Regex Extractions
    name_m = re.search(r"Name\s*:\s*(.+)", text)
    name = name_m.group(1).strip() if name_m else "N/A"

    addr_m = re.search(r"Service Location Address\s*:\s*([\s\S]*?)(?=Office Name\s*:)", text)
    address = re.sub(r"\s+", " ", addr_m.group(1)).strip() if addr_m else "N/A"

    office_m = re.search(r"Office Name\s*:\s*(.+)", text)
    office = office_m.group(1).strip() if office_m else "N/A"

    status_m = re.search(r"Connection Status\s*:\s*(.+)", text)
    connection_status = status_m.group(1).strip() if status_m else "N/A"

    conn_date_m = re.search(r"Date of Service Connection\s*:\s*(.+)", text)
    conn_date = conn_date_m.group(1).strip() if conn_date_m else "N/A"

    # Dues
    osd = 0.0
    osd_m = re.search(r"total unpaid bill amount is Rs\.\s*([\d\.]+)", text, re.IGNORECASE)
    if osd_m:
        osd = float(osd_m.group(1))
    elif doc_type == "NO DUES CERTIFICATE" or "no unpaid bill" in text.lower():
        osd = 0.0

    lpsc = 0.0
    lpsc_m = re.search(r"Late Payment Surcharge \(LPSC\) amount of Rs\.\s*([\d\.]+)", text, re.IGNORECASE)
    if lpsc_m:
        lpsc = float(lpsc_m.group(1))

    total_dues = round(osd + lpsc, 2)

    # Status Flags
    norm_status = connection_status.upper()
    is_deemed = "DEEMED" in norm_status
    is_disconnected = not is_deemed and "DISCONNECT" in norm_status
    is_live = (
        not is_deemed
        and not is_disconnected
        and ("LIVE" in norm_status or bool(re.search(r"\bCONNECTED\b", norm_status)))
    )

    return {
        "consumerId": consumer_id,
        "name": name,
        "address": address,
        "office": office,
        "connectionStatus": connection_status,
        "connDate": conn_date,
        "docType": doc_type,
        "osd": osd,
        "lpsc": lpsc,
        "totalDues": total_dues,
        "isLive": is_live,
        "isDeemed": is_deemed,
        "isDisconnected": is_disconnected,
        "fileSizeKb": round(len(pdf_bytes) / 1024, 1),
    }


def get_live_osd_data(consumer_id: str, include_pdf_base64: bool = False, force_refresh: bool = False) -> Dict[str, Any]:
    """
    High-level entry point function with caching support.
    """
    clean_id = str(consumer_id).strip()
    now = time.time()

    if not force_refresh and clean_id in _OSD_CACHE:
        cached_time, cached_result, cached_pdf = _OSD_CACHE[clean_id]
        if (now - cached_time) < _CACHE_TTL:
            res = dict(cached_result)
            if include_pdf_base64 and cached_pdf:
                res["pdfBase64"] = base64.b64encode(cached_pdf).decode("utf-8")
            res["cached"] = True
            return {"success": True, "data": res}

    try:
        pdf_bytes = fetch_live_osd_pdf(clean_id)
        result = parse_osd_pdf(pdf_bytes, clean_id)
        _OSD_CACHE[clean_id] = (now, result, pdf_bytes)

        res = dict(result)
        if include_pdf_base64:
            res["pdfBase64"] = base64.b64encode(pdf_bytes).decode("utf-8")
        res["cached"] = False
        return {"success": True, "data": res}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
