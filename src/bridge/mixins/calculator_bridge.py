try:
    from core import tariff_manager
except ImportError:
    import tariff_manager


class CalculatorBridge:
    """Billing and theft assessment calculation and tariff CRUD bridge."""

    def calculate_bill(self, p):
        return self._billing_service.calculate_bill(p)

    def calculate_theft(self, p):
        return self._billing_service.calculate_theft(p)

    def calculate_theft_dual(self, p):
        return self._billing_service.calculate_theft_dual(p)

    def calculate_theft_reverse_load(self, p):
        return self._billing_service.calculate_theft_reverse_load(p)

    def get_tariffs(self):
        try:
            return {"success": True, "tariffs": tariff_manager.load_tariff()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_tariff_data(self, tariffs):
        try:
            tariff_manager.save_tariff(tariffs)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset_tariff_data(self, category=None):
        try:
            tariffs = tariff_manager.reset_tariff(category)
            return {"success": True, "tariffs": tariffs}
        except Exception as e:
            return {"success": False, "error": str(e)}
