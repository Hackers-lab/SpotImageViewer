"""
rule_engine.py
==============
Dynamic rule engine for ERP Estimate Generator v5.0.

How it works
------------
1.  For each canvas item, build an ``item_context`` dict of all its
    properties (including global project properties like ``use_uh`` and
    ``project_type``).
2.  Each rule in rules.json specifies:
        object    — which object type it applies to
        condition — a Python expression evaluated against item_context
        formula   — a Python expression that returns the quantity
        type      — "Material" or "Labor"
        item_name — matches the database item_name / task_name column
3.  Safe eval is used: no builtins except ``math`` and ``int``.

Context keys available per object type
---------------------------------------

SmartPole
    object_type, pole_type, pole_type2, is_existing, height (int metres),
    has_extension, extension_height (float), earth_count, stay_count,
    has_cg, ht_spans_count, use_uh, project_type

SmartStructure
    object_type, structure_type, pole_type2, height (int metres),
    has_extension, extension_height (float), earth_count, stay_count,
    dtr_size, use_uh, project_type

SmartSpan
    object_type, conductor, conductor_size, is_service_drop,
    is_existing_span, is_lt_span, wire_count (int), length (int/float),
    aug_type, has_cg, phase, consider_cable, use_uh, project_type

SmartConsumer
    object_type, phase, cable_size, agency_supply, use_uh, project_type

Backward-compatibility notes
-----------------------------
•   Rules written for the old SmartPole / SmartHome / SmartSpan contexts
    will continue to work because the old key names are preserved where
    possible (``wire_count``, ``conductor``, etc.).
•   ``wire_size`` and ``cable_size`` from old rules still resolve because
    we provide them as aliases of ``conductor_size`` for SmartSpan.
•   ``SmartHome`` rules are silently skipped (no SmartHome objects exist
    in v5 drawings). They will not error; they simply produce zero output.
•   ``dtr_size`` is now a SmartStructure property — old rules that checked
    ``object == 'SmartPole' and dtr_size != 'None'`` will no longer fire
    because there are no SmartPole items with dtr_size. Those rules should
    be migrated to ``object == 'SmartStructure'`` in the Ruleset Manager.
"""

import math
from canvas_objects import SmartPole, SmartStructure, SmartSpan, SmartConsumer


class DynamicRuleEngine:
    """
    Evaluates a JSON ruleset against all canvas items and accumulates
    material quantities and labour task counts.
    """

    # ── Safe evaluation helpers ───────────────────────────────────────────────

    def evaluate_rule(self, item_context: dict, condition_str: str) -> bool:
        """
        Safely evaluate a condition string.
        Returns False on any exception (rule silently skipped).
        """
        if not condition_str or condition_str.strip() == "":
            return True           # empty condition = always fire
        try:
            return bool(
                eval(
                    condition_str,
                    {"__builtins__": {}},
                    item_context,
                )
            )
        except Exception as exc:
            print(f"[RuleEngine] Condition error '{condition_str}': {exc}")
            return False

    def calculate_qty(self, item_context: dict, formula_str: str) -> float:
        """
        Safely evaluate a quantity formula.
        Returns 0 on any exception.
        """
        if not formula_str or formula_str.strip() == "":
            return 0
        try:
            result = eval(
                formula_str,
                {"__builtins__": {"int": int, "round": round, "abs": abs},
                 "math": math,
                 # Named iron weight constants (kg/m)
                 "CH_75X40":    6.8,
                 "CH_100X50":   9.8,
                 "ANG_65X65X6": 5.8,
                 "ANG_50X50X6": 4.5,
                 "FLAT_65X6":   3.1,
                 "FLAT_50X6":   2.5,
                 "GIWIRE_5MM":  0.123,
                 "GIWIRE_4MM":  0.100},
                item_context,
            )
            return float(result)
        except Exception as exc:
            print(f"[RuleEngine] Formula error '{formula_str}': {exc}")
            return 0

    # ── Context builders ──────────────────────────────────────────────────────

    @staticmethod
    def _height_int(height_str: str) -> int:
        """
        Convert height string to integer metres.
        "8MTR" → 8,  "9.5MTR" → 9,  "11MTR" → 11, "13MTR" → 13
        Uses int() truncation so 9.5MTR → 9 for backward compat with
        old rules that check ``height == 9``.
        """
        try:
            return int(float(height_str.replace("MTR", "").strip()))
        except ValueError:
            return 8

    def _build_pole_context(
        self, item: SmartPole,
        use_uh: bool, project_type: str
    ) -> dict:
        # For existing poles use existing_subtype (e.g. "HT") as the
        # effective pole_type so stay/insulator rules fire correctly.
        eff_pole_type = (
            getattr(item, "existing_subtype", item.pole_type)
            if item.is_existing else item.pole_type
        )
        ctx: dict = {
            "object_type":      "SmartPole",
            "pole_type":        eff_pole_type,
            "pole_type2":       item.pole_type2,
            "is_existing":      item.is_existing,
            "existing_subtype": getattr(item, "existing_subtype", item.pole_type),
            "existing_dtr_size": getattr(item, "existing_dtr_size", "None"),
            "height":           self._height_int(item.height),
            "has_extension":    item.has_extension,
            "extension_height": item.extension_height,
            "earth_count":      item.earth_count,
            "stay_count":       item.stay_count,
            "use_uh":           use_uh,
            "project_type":     project_type,
            "work_mode":        getattr(item, "work_mode", "new"),
            "reuse_material":   getattr(item, "reuse_material", False)        }

        # has_cg — True if any connected span has cattle guard
        ctx["has_cg"] = any(
            getattr(s, "has_cg", False)
            for s in item.connected_spans
        )

        # ht_spans_count — number of NEW (non-existing) ACSR spans connected.
        # Used to classify end pole (==1 → disc) vs through pole (>=2 → pin).
        # Includes spans to/from existing poles so a DTR or new pole adjacent
        # to an existing HT pole is still treated as an end point.
        ctx["ht_spans_count"] = sum(
            1 for s in item.connected_spans
            if s.conductor == "ACSR"
            and not getattr(s, "is_existing_span", False)
        )

        # lt_acsr_count — number of LT ACSR spans connected to this pole
        # (used by LT bracket iron rules on SmartPole)
        lt_acsr_spans = [
            s for s in item.connected_spans
            if s.conductor == "ACSR" and getattr(s, "is_lt_span", False)
        ]
        ctx["lt_acsr_count"] = len(lt_acsr_spans)

        # lt_wire_count — max wire count across LT ACSR spans (for UH D-Iron rule)
        ctx["lt_wire_count"] = max(
            (int(getattr(s, "wire_count", 0)) for s in lt_acsr_spans),
            default=0
        )

        # AB cable context — distribution box / clamp / IPC rules
        ab_spans = [
            s for s in item.connected_spans
            if s.conductor == "AB Cable"
            and not getattr(s, "is_service_drop", False)
        ]
        ab_cable_count = len(ab_spans)
        if ab_cable_count == 0:
            ab_needs_dead_end   = False
            ab_needs_suspension = False
        elif ab_cable_count == 1:
            ab_needs_dead_end   = True
            ab_needs_suspension = False
        else:
            my_x, my_y = item.x(), item.y()
            span_angles = []
            for s in ab_spans:
                other = s.p1 if s.p2 is item else s.p2
                dx = other.x() - my_x
                dy = other.y() - my_y
                mag = math.hypot(dx, dy)
                if mag > 0:
                    span_angles.append(math.atan2(dy, dx))
            max_dev = 0.0
            for i in range(len(span_angles)):
                for j in range(i + 1, len(span_angles)):
                    diff = abs(span_angles[i] - span_angles[j])
                    if diff > math.pi:
                        diff = 2 * math.pi - diff
                    deviation = abs(math.pi - diff)
                    max_dev = max(max_dev, math.degrees(deviation))
            ab_needs_dead_end   = max_dev > 65
            ab_needs_suspension = not ab_needs_dead_end
        ctx["ab_cable_count"]     = ab_cable_count
        ctx["ab_needs_dead_end"]  = ab_needs_dead_end
        ctx["ab_needs_suspension"] = ab_needs_suspension

        # Merge any dynamic props attached to the item
        ctx.update(getattr(item, "dynamic_props", {}))
        return ctx

    def _build_structure_context(
        self, item: SmartStructure,
        use_uh: bool, project_type: str
    ) -> dict:
        ht_spans_count = sum(
            1 for s in getattr(item, "connected_spans", [])
            if s.conductor == "ACSR"
            and not getattr(s, "is_existing_span", False)
        )
        ctx: dict = {
            "object_type":      "SmartStructure",
            "structure_type":   item.structure_type,
            "pole_type2":       item.pole_type2,
            "height":           self._height_int(item.height),
            "has_extension":    item.has_extension,
            "extension_height": item.extension_height,
            "earth_count":      item.earth_count,
            "stay_count":       item.stay_count,
            "dtr_size":         item.dtr_size,
            "ht_spans_count":   ht_spans_count,
            "use_uh":           use_uh,
            "project_type":     project_type,
        }
        ctx.update(getattr(item, "dynamic_props", {}))
        return ctx

    def _build_span_context(
        self, item: SmartSpan,
        use_uh: bool, project_type: str
    ) -> dict:
        # wire_count as int — old rules used int(wire_count)
        try:
            wire_count_int = int(item.wire_count)
        except (ValueError, TypeError):
            wire_count_int = 3

        ctx: dict = {
            "object_type":      "SmartSpan",
            "conductor":        item.conductor,
            "conductor_size":   item.conductor_size,
            # Backward-compat aliases so old rules still work
            "wire_size":        item.conductor_size,
            "cable_size":       item.conductor_size,
            "is_service_drop":  item.is_service_drop,
            "is_existing_span": item.is_existing_span,
            "is_lt_span":       item.is_lt_span,
            "wire_count":       wire_count_int,
            "length":           item.length,
            "aug_type":         item.aug_type,
            "has_cg":           item.has_cg,
            "phase":            item.phase,
            "consider_cable":   item.consider_cable,
            "use_uh":           use_uh,
            "project_type":     project_type,
        }
        ctx.update(getattr(item, "dynamic_props", {}))
        return ctx

    def _build_consumer_context(
        self, item: SmartConsumer,
        use_uh: bool, project_type: str
    ) -> dict:
        service_span = next(
            (s for s in getattr(item, "connected_spans", [])
             if getattr(s, "is_service_drop", False)),
            None,
        )
        service_length = service_span.length if service_span else 20
        ctx: dict = {
            "object_type":       "SmartConsumer",
            # Keep SmartHome alias so any legacy rules survive
            "object_type_alias": "SmartHome",
            "phase":             item.phase,
            "cable_size":        item.cable_size,
            "agency_supply":     item.agency_supply,
            "consider_cable":    getattr(item, "consider_cable", False),
            "service_length":    service_length,
            "use_uh":            use_uh,
            "project_type":      project_type,
        }
        ctx.update(getattr(item, "dynamic_props", {}))
        return ctx

    # ── Main processing entry point ───────────────────────────────────────────

    def process(
        self,
        canvas_items: list,
        rules: list,
        use_uh: bool = False,
        project_type: str = "NSC",
    ) -> tuple[dict, dict]:
        """
        Walk all canvas items, build their context, evaluate every rule,
        and accumulate quantities.

        Parameters
        ----------
        canvas_items  : list of SmartPole / SmartStructure / SmartSpan /
                        SmartConsumer instances from the scene
        rules         : parsed contents of rules.json
        use_uh        : project-level UH material toggle
        project_type  : project type string e.g. "NSC", "SHIFTING" etc.

        Returns
        -------
        (raw_bom, raw_lab)
            raw_bom  : dict  item_name → total_quantity  (Materials)
            raw_lab  : dict  task_name → total_quantity  (Labor)
        """
        raw_bom: dict[str, float] = {}
        raw_lab: dict[str, float] = {}

        for item in canvas_items:

            # ── Build context ─────────────────────────────────────────────
            if isinstance(item, SmartPole):
                ctx = self._build_pole_context(item, use_uh, project_type)

            elif isinstance(item, SmartStructure):
                ctx = self._build_structure_context(item, use_uh, project_type)

            elif isinstance(item, SmartSpan):
                ctx = self._build_span_context(item, use_uh, project_type)

            elif isinstance(item, SmartConsumer):
                ctx = self._build_consumer_context(item, use_uh, project_type)

            else:
                # Unknown item type — skip silently
                continue

            # ── Evaluate rules ────────────────────────────────────────────
            for rule in rules:
                target = rule.get("object", "")

                # Match object type
                # Also allow "SmartHome" rules to match SmartConsumer
                # so legacy rulesets keep working without any edits.
                obj_type = ctx.get("object_type", "")
                if target == "SmartHome" and obj_type == "SmartConsumer":
                    pass   # allow legacy match
                elif target != obj_type:
                    continue

                condition = rule.get("condition", "")
                if not self.evaluate_rule(ctx, condition):
                    continue

                formula = rule.get("formula", "1")
                qty     = self.calculate_qty(ctx, formula)

                if qty <= 0:
                    continue

                item_name = rule.get("item_name", "")
                item_type = rule.get("type", "Material")

                if not item_name:
                    continue

                if item_type == "Material":
                    raw_bom[item_name] = raw_bom.get(item_name, 0) + qty
                elif item_type == "Labor":
                    raw_lab[item_name] = raw_lab.get(item_name, 0) + qty

        return raw_bom, raw_lab
