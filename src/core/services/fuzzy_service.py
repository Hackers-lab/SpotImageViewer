import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz as rapidfuzz_fuzz
except ImportError:
    rapidfuzz_fuzz = None

try:
    from core import utils, live_osd_service
except ImportError:
    import utils, live_osd_service


_cache_timestamp = 0
_CACHE_TTL = 300

class FuzzyService:
    """
    High-performance fuzzy matching service for consumer identity resolution
    (Name, C/O, Address, Mobile) with token indexing and batch Excel processing.
    """

    _cached_prepped_fuzzy_db = None
    _cached_fuzzy_lock = threading.Lock()

    def __init__(self):
        self._fuzzy_state = {
            "running": False,
            "processed": 0,
            "total": 0,
            "elapsed": 0,
            "status": "idle",
            "output_path": "",
            "error": ""
        }

    def get_status(self):
        return {"success": True, **self._fuzzy_state}

    @classmethod
    def invalidate_cache(cls):
        """Clears the in-memory fuzzy lookup prepped database index."""
        with cls._cached_fuzzy_lock:
            cls._cached_prepped_fuzzy_db = None

    @staticmethod
    def generate_fuzzy_template(save_path):
        """Generates an empty Excel template for fuzzy lookup queries."""
        try:
            if not save_path:
                return {"success": False, "cancelled": True}

            openpyxl = utils.get_openpyxl()
            wb = openpyxl.Workbook()
            sheet = wb.active
            sheet.title = "FuzzyLookupInput"
            sheet.append(["NAME", "C/O", "ADDRESS", "MOBILE NUMBER"])
            sheet.append(["", "", "", ""])
            sheet.freeze_panes = "A2"

            widths = [28, 28, 42, 18]
            for idx, width in enumerate(widths, start=1):
                col = openpyxl.utils.get_column_letter(idx)
                sheet.column_dimensions[col].width = width

            wb.save(save_path)
            return {"success": True, "path": save_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def normalize_fuzzy_text(value):
        text = str(value or "").upper()
        text = re.sub(r"[^A-Z0-9 ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def clean_address_text(cls, value):
        """
        Strips common administrative boilerplate keywords (VILL, PO, PS, DIST, etc.)
        from address strings so that fuzzy comparison compares substantive location names.
        """
        text = cls.normalize_fuzzy_text(value)
        if not text:
            return ""
        # Remove common administrative label words but retain the actual location names
        pattern = r"\b(?:VILL|VILLAGE|VIL|PO|P\s*O|POST|PS|P\s*S|POLICE\s*STATION|DIST|DISTRICT|DT|PIN|PINCODE|GP|GRAM\s*PANCHAYAT|PANCHAYAT|BLOCK|BLK|HOLDING|HOUSE|DAG|KHATIAN|PLOT|FLAT|APT|APARTMENT|NEAR|OPP|OPPOSITE|BEHIND|BESIDE)\b"
        cleaned = re.sub(pattern, " ", text)
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def strip_fuzzy_prefixes(cls, value):
        text = cls.normalize_fuzzy_text(value)
        pattern = r"^(?:C\s*O|S\s*O|D\s*O|W\s*O|F\s*O|H\s*O|M\s*O|B\s*O|CARE\s*OF|SON\s*OF|DAUGHTER\s*OF|WIFE\s*OF|FATHER\s*OF|HUSBAND\s*OF|MOTHER\s*OF|LATE|LT|SRI|SMT|MD|MR|MRS|DR)\s+"
        while True:
            subbed = re.sub(pattern, "", text)
            if subbed == text:
                break
            text = subbed.strip()
        return text

    @staticmethod
    def phonetic_key(word):
        """
        Generates a phonetic consonant key to handle pronunciation and spelling variations
        (e.g., KANUA vs KONUA, ANWAR vs ANOWAR, SIDDIK vs SEDDIK, JAHIR vs ZAHIR).
        """
        if not word or len(word) < 2:
            return ""
        w = word.upper()
        w = re.sub(r"PH", "F", w)
        w = re.sub(r"BH", "B", w)
        w = re.sub(r"DH", "D", w)
        w = re.sub(r"TH", "T", w)
        w = re.sub(r"KH", "K", w)
        w = re.sub(r"GH", "G", w)
        w = re.sub(r"CH", "C", w)
        w = re.sub(r"SH", "S", w)
        w = re.sub(r"Z", "J", w)
        w = re.sub(r"V", "B", w)
        w = re.sub(r"W", "O", w)
        w = re.sub(r"Y", "I", w)
        w = re.sub(r"EE", "I", w)
        w = re.sub(r"OO", "U", w)
        w = re.sub(r"OU", "U", w)
        w = re.sub(r"(.)\1+", r"\1", w)
        first_char = w[0]
        rest = re.sub(r"[AEIOU]", "", w[1:])
        return (first_char + rest)[:4]

    @classmethod
    def extract_co_and_name(cls, text, is_address=False):
        if not text:
            return "", ""

        addr_keywords = {
            "VILL", "VILLAGE", "VIL", "PO", "POST", "PS", "DIST", "DISTRICT",
            "PIN", "PINCODE", "ROAD", "STREET", "LANE", "SARANI", "PARA",
            "WARD", "HOLDING", "HOUSE", "NEAR", "BEHIND", "OPP", "OPPOSITE",
            "GP", "PANCHAYAT", "MUNICIPALITY", "BLOCK", "SECTOR", "PLOT", "FLAT", "APARTMENT"
        }
        raw_str = str(text)
        pattern_rel = r"\b(?:S\s*O|D\s*O|W\s*O|C\s*O|F\s*O|H\s*O|M\s*O|CARE\s*OF|SON\s*OF|DAUGHTER\s*OF|WIFE\s*OF|FATHER\s*OF|HUSBAND\s*OF)\b"

        if is_address:
            # 1. First check explicit relation prefix in address (e.g. C/O SIDDIK ... or S/O ...)
            m_rel = re.search(pattern_rel, cls.normalize_fuzzy_text(raw_str))
            if m_rel:
                norm_full = cls.normalize_fuzzy_text(raw_str)
                after_co = norm_full[m_rel.end():].strip()
                words = after_co.split()
                co_words = []
                addr_words = []
                found_addr_start = False
                for w in words:
                    if not found_addr_start and (w in addr_keywords or w.isdigit()):
                        found_addr_start = True
                    if found_addr_start:
                        addr_words.append(w)
                    else:
                        co_words.append(w)
                co_part = cls.strip_fuzzy_prefixes(" ".join(co_words))
                remaining_addr = " ".join(addr_words)
                if not remaining_addr:
                    parts = [p.strip() for p in re.split(r"[,;]+", raw_str) if p.strip()]
                    if len(parts) > 1:
                        remaining_addr = " ".join(parts[1:])
                return cls.strip_fuzzy_prefixes(remaining_addr), co_part

            # 2. Check comma-separated leading name token if no explicit relation prefix
            # (e.g. 'MAFIJUDDIN ,PALASHI SWARUPGUNJ' or 'ABDUL MAJID, NONATOR')
            parts = [p.strip() for p in re.split(r"[,;]+", raw_str) if p.strip()]
            if parts:
                first_seg = cls.normalize_fuzzy_text(parts[0])
                first_words = first_seg.split()
                has_addr_kw = any(w in addr_keywords for w in first_words)
                has_digit = any(w.isdigit() for w in first_words)
                if 1 <= len(first_words) <= 4 and not has_addr_kw and not has_digit and len(parts) > 1:
                    co_part = cls.strip_fuzzy_prefixes(first_seg)
                    remaining_addr = ", ".join(parts[1:]).strip()
                    return cls.strip_fuzzy_prefixes(remaining_addr), co_part

            # 3. Generic check: leading personal name tokens before standard administrative address keywords
            # (e.g. 'ABDUL MAJID VILL NONATOR' -> guardian 'ABDUL MAJID', address 'VILL NONATOR')
            words = cls.normalize_fuzzy_text(raw_str).split()
            for idx, w in enumerate(words):
                if w in addr_keywords:
                    leading = words[:idx]
                    if 1 <= len(leading) <= 3 and not any(lw.isdigit() for lw in leading):
                        return cls.strip_fuzzy_prefixes(" ".join(words[idx:])), cls.strip_fuzzy_prefixes(" ".join(leading))
                    break

        cleaned = cls.normalize_fuzzy_text(text)
        m = re.search(pattern_rel, cleaned)
        if m:
            main_part = cls.strip_fuzzy_prefixes(cleaned[:m.start()])
            co_part = cls.strip_fuzzy_prefixes(cleaned[m.end():])
            return main_part, co_part

        return cls.strip_fuzzy_prefixes(cleaned), ""

    @staticmethod
    def normalize_mobile_10(value):
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        return digits if len(digits) == 10 else ""

    @classmethod
    def tokenize_for_lookup(cls, text):
        return [t for t in cls.normalize_fuzzy_text(text).split(" ") if len(t) >= 2]

    @staticmethod
    def token_level_sim(s1, s2):
        t1 = [w for w in s1.split() if len(w) >= 2]
        t2 = [w for w in s2.split() if len(w) >= 2]
        if not t1 or not t2:
            return 0.0
        matches1 = sum(1 for w1 in t1 if any(SequenceMatcher(None, w1, w2).ratio() >= 0.80 for w2 in t2))
        matches2 = sum(1 for w2 in t2 if any(SequenceMatcher(None, w2, w1).ratio() >= 0.80 for w1 in t1))
        return ((matches1 / len(t1)) + (matches2 / len(t2))) / 2.0

    @classmethod
    def match_single_field(cls, a, b, is_address=False):
        if is_address:
            a_clean = cls.clean_address_text(a) or cls.normalize_fuzzy_text(a)
            b_clean = cls.clean_address_text(b) or cls.normalize_fuzzy_text(b)
        else:
            a_clean = cls.strip_fuzzy_prefixes(a)
            b_clean = cls.strip_fuzzy_prefixes(b)

        if not a_clean or not b_clean:
            return 0.0
        if a_clean == b_clean:
            return 100.0

        if not is_address:
            # Compound religious suffix normalization to avoid false similarity
            # (e.g. TAHIRUDDIN vs HAFIJUDDIN should not get 71% purely from -UDDIN)
            suffixes = ["UDDIN", "ODDIN"]
            a_root, b_root = a_clean, b_clean
            for sfx in suffixes:
                if a_clean.endswith(sfx) and len(a_clean) > len(sfx) + 2:
                    a_root = a_clean[:-len(sfx)]
                if b_clean.endswith(sfx) and len(b_clean) > len(sfx) + 2:
                    b_root = b_clean[:-len(sfx)]

            if rapidfuzz_fuzz is not None:
                ratio = float(rapidfuzz_fuzz.ratio(a_clean, b_clean))
                token_sort = float(rapidfuzz_fuzz.token_sort_ratio(a_clean, b_clean))
                token_set = float(rapidfuzz_fuzz.token_set_ratio(a_clean, b_clean))
                partial = float(rapidfuzz_fuzz.partial_ratio(a_clean, b_clean))
                score = (0.25 * ratio) + (0.35 * token_set) + (0.25 * token_sort) + (0.15 * partial)

                if a_root != a_clean and b_root != b_clean:
                    root_ratio = float(rapidfuzz_fuzz.ratio(a_root, b_root))
                    score = min(score, root_ratio + 15.0)
            else:
                ratio = SequenceMatcher(None, a_clean, b_clean).ratio() * 100.0
                score = ratio
                if a_root != a_clean and b_root != b_clean:
                    root_ratio = SequenceMatcher(None, a_root, b_root).ratio() * 100.0
                    score = min(score, root_ratio + 15.0)

            # Check phonetic skeletal consonant key for spelling & pronunciation variants
            # (e.g. KANUA vs KONUA, ANWAR vs ANOWAR, SIDDIK vs SEDDIK, DILIP vs DELIP)
            key_a = cls.phonetic_key(a_clean)
            key_b = cls.phonetic_key(b_clean)
            if key_a and key_b and key_a == key_b:
                score = max(score, 88.0)

            return min(100.0, max(0.0, score))

        if rapidfuzz_fuzz is not None:
            ratio = float(rapidfuzz_fuzz.ratio(a_clean, b_clean))
            token_sort = float(rapidfuzz_fuzz.token_sort_ratio(a_clean, b_clean))
            token_set = float(rapidfuzz_fuzz.token_set_ratio(a_clean, b_clean))
            partial = float(rapidfuzz_fuzz.partial_ratio(a_clean, b_clean))
            score = (0.25 * ratio) + (0.35 * token_set) + (0.25 * token_sort) + (0.15 * partial)
        else:
            seq = SequenceMatcher(None, a_clean, b_clean).ratio() * 100.0
            tok = cls.token_level_sim(a_clean, b_clean) * 100.0
            sub = 0.0
            if a_clean in b_clean and len(a_clean.split()) >= 2:
                sub = 90.0
            elif b_clean in a_clean and len(b_clean.split()) >= 2:
                sub = 90.0
            score = max(seq, tok, sub)
        return min(100.0, score)

    @classmethod
    def get_prepped_fuzzy_db(cls):
        global _cache_timestamp
        with cls._cached_fuzzy_lock:
            if cls._cached_prepped_fuzzy_db is not None:
                if time.time() - _cache_timestamp > _CACHE_TTL:
                    cls._cached_prepped_fuzzy_db = None
                else:
                    return cls._cached_prepped_fuzzy_db

            db_profiles = utils.get_all_consumer_profiles()
            if not db_profiles:
                return None

            prepped_db = []
            mobile_index = defaultdict(set)
            prefix_index = defaultdict(set)
            token_index = defaultdict(set)
            phonetic_index = defaultdict(set)

            addr_noise_tokens = {
                "VILL", "VILLAGE", "VIL", "PO", "POST", "PS", "DIST", "DISTRICT",
                "PIN", "PINCODE", "CARE", "SON", "DAUGHTER", "WIFE", "LATE", "SRI", "SMT"
            }

            for idx, row in enumerate(db_profiles):
                db_name = str(row.get("name", "") or "").strip()
                db_address = str(row.get("address", "") or "").strip()
                db_name_main, db_name_co = cls.extract_co_and_name(db_name, is_address=False)
                db_addr_main, db_addr_co = cls.extract_co_and_name(db_address, is_address=True)

                db_combined_raw = f"{db_name} {db_address}".strip()
                combined_norm = cls.normalize_fuzzy_text(db_combined_raw)
                combined_tokens = set(cls.tokenize_for_lookup(combined_norm))
                mobile_norm = cls.normalize_mobile_10(row.get("mobile_number", ""))

                prepped_db.append({
                    "consumer_id": str(row.get("consumer_id", "") or ""),
                    "name": db_name,
                    "address": db_address,
                    "name_main": db_name_main,
                    "name_co": db_name_co,
                    "addr_main": db_addr_main,
                    "addr_co": db_addr_co,
                    "mobile_number": str(row.get("mobile_number", "") or ""),
                    "mobile_norm": mobile_norm,
                    "combined_norm": combined_norm,
                    "tokens": combined_tokens,
                })

                if mobile_norm:
                    mobile_index[mobile_norm].add(idx)

                for tok in combined_tokens:
                    # Do not index purely administrative noise tokens in prefix/token index
                    if tok in addr_noise_tokens:
                        continue
                    if len(tok) >= 3:
                        prefix_index[tok[:3]].add(idx)
                    if len(tok) >= 4:
                        token_index[tok].add(idx)
                    # Index phonetic consonant skeletal key (e.g. KANUA & KONUA -> KN)
                    pkey = cls.phonetic_key(tok)
                    if pkey and len(pkey) >= 2:
                        phonetic_index[pkey].add(idx)

            cache_data = (prepped_db, mobile_index, prefix_index, token_index, phonetic_index)
            cls._cached_prepped_fuzzy_db = cache_data
            _cache_timestamp = time.time()
            return cache_data

    @classmethod
    def score_single_fuzzy_query(cls, input_name, input_co, input_address, input_mobile, threshold=0.85, top_n=5):
        prepped = cls.get_prepped_fuzzy_db()
        if not prepped:
            return []

        prepped_db, mobile_index, prefix_index, token_index, phonetic_index = prepped

        input_name = str(input_name or "").strip()
        input_co = str(input_co or "").strip()
        input_address = str(input_address or "").strip()
        input_mobile = str(input_mobile or "").strip()

        if not (input_name or input_co or input_address or input_mobile):
            return []

        input_combined = cls.normalize_fuzzy_text(f"{input_name} {input_co} {input_address}")
        input_mobile_norm = cls.normalize_mobile_10(input_mobile)
        input_tokens = [t for t in cls.tokenize_for_lookup(input_combined) if len(t) >= 3]

        addr_noise_tokens = {
            "VILL", "VILLAGE", "VIL", "PO", "POST", "PS", "DIST", "DISTRICT",
            "PIN", "PINCODE", "CARE", "SON", "DAUGHTER", "WIFE", "LATE", "SRI", "SMT"
        }
        substantive_tokens = [t for t in input_tokens if t not in addr_noise_tokens]
        if not substantive_tokens:
            substantive_tokens = input_tokens

        candidate_ids = set()
        if input_mobile_norm:
            candidate_ids.update(mobile_index.get(input_mobile_norm, set()))

        for tok in substantive_tokens[:6]:
            candidate_ids.update(prefix_index.get(tok[:3], set()))
            # Retrieve phonetic candidates for spelling & pronunciation variants (e.g. Konua for Kanua)
            pkey = cls.phonetic_key(tok)
            if pkey and len(pkey) >= 2:
                candidate_ids.update(phonetic_index.get(pkey, set()))

        longest_tokens = sorted({t for t in substantive_tokens if len(t) >= 4}, key=len, reverse=True)[:4]
        for tok in longest_tokens:
            candidate_ids.update(token_index.get(tok, set()))

        if not candidate_ids and substantive_tokens:
            for tok in substantive_tokens:
                candidate_ids.update(prefix_index.get(tok[:3], set()))

        # Fallback: if no candidates found via substantive tokens, check all input tokens
        if not candidate_ids and input_tokens:
            for tok in input_tokens:
                candidate_ids.update(prefix_index.get(tok[:3], set()))

        if not candidate_ids:
            return []

        # Cap maximum candidates evaluated to top 150 to keep processing responsive
        if len(candidate_ids) > 150 and substantive_tokens:
            input_token_set = set(substantive_tokens)
            ranked_cands = []
            for cid in candidate_ids:
                row_tokens = prepped_db[cid].get("tokens", set())
                overlap = len(input_token_set.intersection(row_tokens)) if row_tokens else 0
                ranked_cands.append((overlap, cid))
            ranked_cands.sort(key=lambda x: x[0], reverse=True)
            candidate_ids = [c[1] for c in ranked_cands[:150]]

        candidates = []
        for cand_idx in candidate_ids:
            db_row = prepped_db[cand_idx]
            mobile_score = 100.0 if (input_mobile_norm and db_row["mobile_norm"] == input_mobile_norm) else 0.0

            # 1. Evaluate Primary Name Match (Input Name vs DB Registered Consumer Name)
            primary_name_targets = [t for t in [db_row["name"], db_row["name_main"]] if t]
            primary_name_score = max((cls.match_single_field(input_name, t, is_address=False) for t in primary_name_targets), default=0.0) if input_name else 0.0

            # Check if Input Name matches Guardian in DB (e.g. W/O GOLAM RABBANI) -> this indicates a RELATIVE connection
            guardian_as_name_score = 0.0
            if input_name and (db_row["addr_co"] or db_row["name_co"]):
                g_targets = [t for t in [db_row["name_co"], db_row["addr_co"]] if t]
                guardian_as_name_score = max((cls.match_single_field(input_name, t, is_address=False) for t in g_targets), default=0.0)

            # Effective name score for identity comparison
            name_score = max(primary_name_score, guardian_as_name_score)

            # 2. Evaluate C/O match
            # CRITICAL FIX: If DB has an explicit guardian (addr_co or name_co), Input C/O MUST match THAT guardian!
            # It must NOT leak into db_row["name"], otherwise Input C/O matching consumer's own name creates false 100% scores!
            has_db_co = bool(db_row["name_co"] or db_row["addr_co"])
            if has_db_co:
                co_targets = [t for t in [db_row["name_co"], db_row["addr_co"]] if t]
            else:
                # If DB has no guardian recorded, check if Input C/O matches registered name (father as consumer)
                co_targets = [t for t in [db_row["name"], db_row["name_main"]] if t]

            co_score = max((cls.match_single_field(input_co, t, is_address=False) for t in co_targets), default=0.0) if input_co else 0.0

            # 3. Calculate Identity Score & Detect Relation
            is_relative_match = False
            co_bonus = 0.0

            # Determine whether this is a Relative match:
            # (a) Input Name matched the Guardian field (e.g. W/O GOLAM RABBANI, registered is NURBANU BEWA)
            # (b) Input C/O matched the Registered Name (e.g. father SIDDIK registered, son ANWAR applying)
            if guardian_as_name_score >= 70.0 and primary_name_score < 60.0:
                is_relative_match = True
            elif co_score >= 75.0 and primary_name_score < 60.0:
                is_relative_match = True

            if input_name and input_co:
                if is_relative_match:
                    # Connection belongs to spouse / relative:
                    # (a) Wife/relative connection: Input Name matched the Guardian (e.g. W/O GOLAM RABBANI, consumer NURBANU BEWA)
                    # (b) Son/daughter connection: Input C/O matched the Registered Name (e.g. father SIDDIK registered, son ANWAR applying)
                    # Since this is a relative, both fields will never match the same person.
                    # Base the relative identity on the matched relation link rather than diluting it with unrelated name.
                    rel_ident = max(guardian_as_name_score, co_score)
                    identity_score = rel_ident
                elif has_db_co:
                    if primary_name_score >= 70.0 and co_score >= 75.0:
                        # Both registered name and C/O match well: strong verified identity!
                        identity_score = (primary_name_score * 0.55) + (co_score * 0.45)
                        co_bonus = 4.0 if (primary_name_score >= 80.0 and co_score >= 85.0) else 0.0
                    elif primary_name_score >= 60.0 and co_score < 65.0:
                        # CONFLICTING FATHER: Name matches, but DB has an explicit DIFFERENT father!
                        # (e.g. Input: GOLAM RABBANI C/O KUTUBUDDIN, DB: S/O ASIRUDDIN or ABDUL MAJID)
                        # (e.g. Input: ABDUL ROF C/O TAHIRUDDIN, DB: S/O HAFIJUDDIN)
                        identity_score = min(50.0, (primary_name_score * 0.35) + (co_score * 0.65))
                    else:
                        identity_score = (primary_name_score * 0.50) + (co_score * 0.50)
                else:
                    # Database has NO C/O recorded:
                    # Name matches, but father is unverified in DB. Cap identity at 78% so unverified
                    # records do not outrank or masquerade as verified father matches.
                    identity_score = min(78.0, primary_name_score * 0.78)
            elif input_name:
                if is_relative_match:
                    identity_score = guardian_as_name_score
                else:
                    identity_score = primary_name_score
            elif input_co:
                identity_score = co_score
            else:
                identity_score = 0.0

            # 4. Evaluate Address match (with boilerplate stripping)
            addr_targets = [t for t in [db_row["address"], db_row["addr_main"]] if t]
            address_score = max((cls.match_single_field(input_address, t, is_address=True) for t in addr_targets), default=0.0) if input_address else 0.0

            # 5. Composite Scoring & Identity Gating
            # User requirement: When 10-digit mobile is matched, it MUST score 100% even if name or C/O don't match!
            if mobile_score == 100.0:
                final_score = 100.0
            else:
                # Disqualify if identity is too low
                if (input_name or input_co) and identity_score < 45.0:
                    final_score = identity_score * 0.40
                else:
                    if input_address:
                        final_score = (identity_score * 0.60) + (address_score * 0.40) + co_bonus
                    else:
                        final_score = identity_score + co_bonus

            final_score = round(min(100.0, max(0.0, final_score)), 2)

            if final_score >= (threshold * 100.0) or mobile_score == 100.0:
                if is_relative_match:
                    relation = "RELATIVE"
                elif primary_name_score >= 60.0:
                    relation = "SELF"
                elif co_score >= 70.0 and primary_name_score < co_score - 10.0:
                    relation = "RELATIVE"
                else:
                    relation = "SELF" if primary_name_score >= co_score else "RELATIVE"

                if mobile_score == 100.0 and identity_score >= 60.0:
                    match_type = "Both"
                elif mobile_score == 100.0:
                    match_type = "Mobile Exact"
                else:
                    match_type = "Fuzzy Identity"

                candidates.append({
                    "consumer_id": db_row["consumer_id"],
                    "name": db_row["name"],
                    "address": db_row["address"],
                    "mobile_number": db_row["mobile_number"],
                    "identity_score": round(identity_score, 2),
                    "name_score": round(name_score, 2),
                    "co_score": round(co_score, 2),
                    "address_score": round(address_score, 2),
                    "mobile_score": round(mobile_score, 2),
                    "final_score": final_score,
                    "match_type": match_type,
                    "relation": relation
                })

        candidates.sort(key=lambda x: (x["final_score"], x["identity_score"], x["mobile_score"]), reverse=True)
        return candidates[:top_n]

    @classmethod
    def lookup_fuzzy_rows(cls, rows, threshold=0.85, top_n=5):
        """Interactive synchronous API for typed or pasted rows."""
        try:
            try:
                thresh_val = float(threshold)
            except Exception:
                thresh_val = 0.85
            thresh_val = max(0.0, min(1.0, thresh_val))

            try:
                limit_n = int(top_n)
            except Exception:
                limit_n = 5
            limit_n = max(1, min(50, limit_n))

            if not isinstance(rows, list) or not rows:
                return {"success": False, "error": "No input rows provided."}

            prepped = cls.get_prepped_fuzzy_db()
            if not prepped:
                return {"success": False, "error": "Consumer database is empty. Please import consumer data first."}

            output_results = []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                in_name = str(item.get("name", "") or "").strip()
                in_co = str(item.get("co", "") or "").strip()
                in_address = str(item.get("address", "") or "").strip()
                in_mobile = str(item.get("mobile", "") or item.get("mobile_number", "") or "").strip()

                candidates = cls.score_single_fuzzy_query(
                    input_name=in_name,
                    input_co=in_co,
                    input_address=in_address,
                    input_mobile=in_mobile,
                    threshold=thresh_val,
                    top_n=limit_n
                )

                output_results.append({
                    "input": {
                        "name": in_name,
                        "co": in_co,
                        "address": in_address,
                        "mobile": in_mobile
                    },
                    "candidates": candidates
                })

            return {"success": True, "total_rows": len(output_results), "results": output_results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_fuzzy_lookup_worker(self, input_path, output_path, threshold=0.85, top_n=5, include_live_osd=False):
        """Background worker for batch Excel fuzzy lookup."""
        start_time = time.time()
        try:
            prepped = self.get_prepped_fuzzy_db()
            if not prepped:
                self._fuzzy_state["error"] = "No consumer data found. Please update consumer database first."
                return

            openpyxl = utils.get_openpyxl()
            wb_in = openpyxl.load_workbook(input_path)
            sh_in = wb_in.active
            rows = list(sh_in.iter_rows(values_only=True))
            if not rows:
                raise ValueError("Input Excel sheet is empty.")

            header_map = {
                "name": "name",
                "co": "co",
                "c/o": "co",
                "careof": "co",
                "care of": "co",
                "address": "address",
                "mobile": "mobile",
                "mobilenumber": "mobile",
                "mobile number": "mobile",
            }

            first_row = rows[0]
            idx_map = {}
            for i, v in enumerate(first_row):
                if v is None:
                    continue
                key = str(v).strip().lower().replace("_", " ")
                key = " ".join(key.split())
                compact = key.replace(" ", "")
                mapped = header_map.get(key) or header_map.get(compact)
                if mapped:
                    idx_map[mapped] = i

            has_headers = "name" in idx_map and "address" in idx_map
            data_rows = rows[1:] if has_headers else rows
            self._fuzzy_state["total"] = len(data_rows)
            self._fuzzy_state["status"] = "Performing fuzzy matching..."

            def _get_input_value(row_vals, field, fallback_idx):
                idx = idx_map.get(field, fallback_idx)
                if idx is None or idx >= len(row_vals):
                    return ""
                val = row_vals[idx]
                return "" if val is None else str(val).strip()

            out_wb = openpyxl.Workbook()
            out_sh = out_wb.active
            out_sh.title = "FuzzyLookupResults"
            out_headers = [
                "Input Name",
                "Input C/O",
                "Input Address",
                "Input Mobile",
                "Matched Consumer ID",
                "Matched Name",
                "Matched Address",
                "Matched Mobile",
                "Relation",
                "Identity Match %",
                "Name Match %",
                "C/O Match %",
                "Address Match %",
                "Mobile Exact Match %",
                "Final Score %",
                "Match Type",
                "Rank",
            ]
            if include_live_osd:
                out_headers.extend([
                    "Live Connection Status",
                    "Live OSD (Rs)",
                    "Live LPSC (Rs)",
                    "Total Payable Dues (Rs)",
                    "Service Conn Date",
                    "Office Name",
                ])
            out_sh.append(out_headers)

            # Phase 1: Pure in-memory fuzzy matching across all rows (runs in seconds)
            all_row_matches = []
            unique_cids_to_fetch = set()

            for in_row in data_rows:
                self._fuzzy_state["processed"] += 1
                self._fuzzy_state["elapsed"] = int(time.time() - start_time)

                if not in_row:
                    continue

                input_name = _get_input_value(in_row, "name", 0)
                input_co = _get_input_value(in_row, "co", 1)
                input_address = _get_input_value(in_row, "address", 2)
                input_mobile = _get_input_value(in_row, "mobile", 3)

                if not (input_name or input_co or input_address or input_mobile):
                    continue

                candidates = self.score_single_fuzzy_query(
                    input_name=input_name,
                    input_co=input_co,
                    input_address=input_address,
                    input_mobile=input_mobile,
                    threshold=threshold,
                    top_n=top_n
                )

                all_row_matches.append({
                    "input_name": input_name,
                    "input_co": input_co,
                    "input_address": input_address,
                    "input_mobile": input_mobile,
                    "candidates": candidates
                })

                if include_live_osd:
                    for c in candidates:
                        cid = str(c.get("consumer_id", "")).strip()
                        if len(cid) == 9 and cid.isdigit():
                            unique_cids_to_fetch.add(cid)

            # Phase 2: Concurrent Multi-Threaded Live OSD Fetch for all candidates
            osd_results_cache = {}
            if include_live_osd and unique_cids_to_fetch:
                total_cids = len(unique_cids_to_fetch)
                fetched_count = 0
                self._fuzzy_state["status"] = f"Fetching live OSD concurrently (0/{total_cids})..."

                def _fetch_single_osd(target_cid):
                    try:
                        res = live_osd_service.get_live_osd_data(target_cid)
                        if res and res.get("success") and res.get("data"):
                            ld = res["data"]
                            return target_cid, {
                                "status": ld.get("connectionStatus", "-"),
                                "osd": float(ld.get("osd", 0.0)),
                                "lpsc": float(ld.get("lpsc", 0.0)),
                                "total": float(ld.get("totalDues", 0.0)),
                                "date": ld.get("connDate", "-"),
                                "office": ld.get("office", "-"),
                            }
                    except Exception:
                        pass
                    return target_cid, {
                        "status": "-", "osd": 0.0, "lpsc": 0.0, "total": 0.0, "date": "-", "office": "-"
                    }

                # Use 10 concurrent worker threads for maximum throughput without overwhelming portal
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(_fetch_single_osd, cid) for cid in unique_cids_to_fetch]
                    for f in as_completed(futures):
                        cid, osd_data = f.result()
                        osd_results_cache[cid] = osd_data
                        fetched_count += 1
                        self._fuzzy_state["elapsed"] = int(time.time() - start_time)
                        self._fuzzy_state["status"] = f"Fetching live OSD concurrently ({fetched_count}/{total_cids})..."

            # Phase 3: Assemble Excel Worksheet
            self._fuzzy_state["status"] = "Writing results to Excel..."
            for item in all_row_matches:
                in_name = item["input_name"]
                in_co = item["input_co"]
                in_addr = item["input_address"]
                in_mob = item["input_mobile"]
                candidates = item["candidates"]

                if not candidates:
                    empty_row = [
                        in_name, in_co, in_addr, in_mob,
                        "", "", "", "",
                        "-", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
                        "No Match", ""
                    ]
                    if include_live_osd:
                        empty_row.extend(["-", "0.00", "0.00", "0.00", "-", "-"])
                    out_sh.append(empty_row)
                    continue

                rank = 1
                for c in candidates:
                    c_cid = str(c["consumer_id"]).strip()
                    row_data = [
                        in_name, in_co, in_addr, in_mob,
                        c["consumer_id"], c["name"], c["address"], c["mobile_number"],
                        c.get("relation", "SELF"),
                        f"{c['identity_score']:.2f}", f"{c['name_score']:.2f}", f"{c['co_score']:.2f}",
                        f"{c['address_score']:.2f}", f"{c['mobile_score']:.2f}", f"{c['final_score']:.2f}",
                        c["match_type"], rank
                    ]

                    if include_live_osd:
                        osd_info = osd_results_cache.get(c_cid, {
                            "status": "-", "osd": 0.0, "lpsc": 0.0, "total": 0.0, "date": "-", "office": "-"
                        })
                        row_data.extend([
                            osd_info["status"],
                            f"{osd_info['osd']:.2f}",
                            f"{osd_info['lpsc']:.2f}",
                            f"{osd_info['total']:.2f}",
                            osd_info["date"],
                            osd_info["office"],
                        ])

                    out_sh.append(row_data)
                    rank += 1

            widths = [24, 24, 36, 16, 18, 26, 36, 16, 14, 16, 14, 14, 16, 18, 14, 16, 10]
            if include_live_osd:
                widths.extend([22, 16, 16, 22, 18, 26])
            for idx, width in enumerate(widths, start=1):
                col = openpyxl.utils.get_column_letter(idx)
                out_sh.column_dimensions[col].width = width
            out_sh.freeze_panes = "A2"

            out_wb.save(output_path)
            self._fuzzy_state["status"] = "Complete"
        except Exception as ex:
            self._fuzzy_state["error"] = str(ex)
            self._fuzzy_state["status"] = "Error"
        finally:
            self._fuzzy_state["running"] = False

    def start_batch_lookup(self, input_path, output_path, threshold=0.85, top_n=5, include_live_osd=False):
        if self._fuzzy_state["running"]:
            return {"success": False, "error": "Fuzzy lookup is already currently running."}

        self._fuzzy_state["running"] = True
        self._fuzzy_state["processed"] = 0
        self._fuzzy_state["total"] = 0
        self._fuzzy_state["elapsed"] = 0
        self._fuzzy_state["status"] = "Preparing consumer database..."
        self._fuzzy_state["output_path"] = output_path
        self._fuzzy_state["error"] = ""

        thread = threading.Thread(
            target=self.run_fuzzy_lookup_worker,
            args=(input_path, output_path, threshold, top_n, include_live_osd),
            daemon=True
        )
        thread.start()
        return {"success": True, "output_path": output_path}
