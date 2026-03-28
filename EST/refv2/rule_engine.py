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
                 "math": math},
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
        ctx: dict = {
            "object_type":      "SmartPole",
            "pole_type":        item.pole_type,
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
        }

        # has_cg — True if any connected span has cattle guard
        ctx["has_cg"] = any(
            getattr(s, "has_cg", False)
            for s in item.connected_spans
        )

        # ht_spans_count — number of ACSR spans between HT poles
        # (used by insulator / hardware fitting rules)
        ctx["ht_spans_count"] = sum(
            1 for s in item.connected_spans
            if s.conductor == "ACSR"
            and getattr(s.p1, "pole_type", "LT") != "LT"
            and getattr(s.p2, "pole_type", "LT") != "LT"
        )

        # Merge any dynamic props attached to the item
        ctx.update(getattr(item, "dynamic_props", {}))
        return ctx

    def _build_structure_context(
        self, item: SmartStructure,
        use_uh: bool, project_type: str
    ) -> dict:
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
        ctx: dict = {
            "object_type":   "SmartConsumer",
            # Keep SmartHome alias so any legacy rules survive
            "object_type_alias": "SmartHome",
            "phase":         item.phase,
            "cable_size":    item.cable_size,
            "agency_supply": item.agency_supply,
            "use_uh":        use_uh,
            "project_type":  project_type,
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
