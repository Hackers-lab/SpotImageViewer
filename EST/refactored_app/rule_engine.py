"""
This module contains the DynamicRuleEngine for processing canvas items
against a set of rules to generate a bill of materials.
"""
import math
from typing import TYPE_CHECKING

from canvas_objects import SmartPole, SmartSpan, SmartHome

if TYPE_CHECKING:
    pass

class DynamicRuleEngine:
    def evaluate_rule(self, item_context, condition_str):
        """
        Safely evaluates a rule's condition string against an item's context.
        """
        try:
            # Safe eval: provide a limited context and no access to globals
            return eval(condition_str, {"__builtins__": {}}, item_context)
        except Exception as e:
            print(f"Error evaluating rule condition '{condition_str}': {e}")
            return False

    def calculate_qty(self, item_context, formula_str):
        """
        Safely evaluates a formula string in the context of a canvas item.
        """
        try:
            # Safe eval: provide a limited context with only math functions
            safe_builtins = {
                'math': math,
                'int': int,
            }
            return eval(formula_str, {"__builtins__": safe_builtins}, item_context)
        except Exception as e:
            print(f"Error calculating formula '{formula_str}': {e}")
            return 0

    def process(self, canvas_items, rules, use_uh=False):
        """
        Processes all items on the canvas against the loaded ruleset to
        generate a raw Bill of Materials (BOM) and a list of labor tasks.
        """
        raw_bom = {}
        total_lab_tasks = {}

        for item in canvas_items:
            item_context = {'use_uh': use_uh}
            if isinstance(item, SmartPole):
                item_context['object_type'] = 'SmartPole'
                item_context['pole_type'] = item.pole_type
                item_context['is_existing'] = item.is_existing
                item_context['height'] = int(item.height.replace("MTR",""))
                item_context['dtr_size'] = item.dtr_size
                item_context['earth_count'] = item.earth_count
                item_context['stay_count'] = item.stay_count
                item_context['has_extension'] = item.has_extension
                item_context['stay_type'] = getattr(item, 'stay_type', item.pole_type)
                
                # Calculate ht_spans_count
                ht_spans = [s for s in item.connected_spans if s.conductor == "ACSR" and getattr(s.p1, 'pole_type', '') != "LT" and getattr(s.p2, 'pole_type', '') != "LT"]
                item_context['ht_spans_count'] = len(ht_spans)
                
                item_context['has_cg'] = any(getattr(s, 'has_cg', False) for s in item.connected_spans)
                
                item_context.update(item.dynamic_props)

            elif isinstance(item, SmartSpan):
                item_context['object_type'] = 'SmartSpan'
                item_context['conductor'] = item.conductor
                item_context['length'] = item.length
                item_context['is_service_drop'] = item.is_service_drop
                item_context['wire_count'] = int(item.wire_count) if hasattr(item, 'wire_count') else 0
                item_context['wire_size'] = item.wire_size if hasattr(item, 'wire_size') else ""
                item_context['cable_size'] = item.cable_size if hasattr(item, 'cable_size') else ""
                item_context['phase'] = item.phase if hasattr(item, 'phase') else ""
                item_context['has_cg'] = item.has_cg
                item_context['aug_type'] = item.aug_type
                item_context['is_existing_span'] = item.is_existing_span
                item_context['consider_cable'] = getattr(item, 'consider_cable', False)
                
                # Calculate is_lt_span
                item_context['is_lt_span'] = (getattr(item.p1, 'pole_type', '') == "LT") or (getattr(item.p2, 'pole_type', '') == "LT")

                item_context.update(item.dynamic_props)
            
            elif isinstance(item, SmartHome):
                item_context['object_type'] = 'SmartHome'
                item_context.update(item.dynamic_props)
            
            else:
                continue

            for rule in rules:
                target_object = rule.get("object")
                if item_context.get('object_type') != target_object:
                    continue
                
                condition = rule.get("condition", "True")

                if self.evaluate_rule(item_context, condition):
                    formula = rule.get("formula", "1")
                    qty = self.calculate_qty(item_context, formula)

                    if qty > 0:
                        item_name = rule["item_name"]
                        item_type = rule["type"]

                        if item_type == "Material":
                            raw_bom[item_name] = raw_bom.get(item_name, 0) + qty
                        elif item_type == "Labor":
                            total_lab_tasks[item_name] = total_lab_tasks.get(item_name, 0) + qty
        
        return raw_bom, total_lab_tasks
