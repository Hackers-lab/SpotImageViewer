from .base import _io_pool


class AuditBridge:
    """Low consumption audit studio bridge."""

    def get_low_consumption_session(self):
        return self._audit_service.get_session()

    def save_low_consumption_session(self, data):
        return self._audit_service.save_session(data)

    def parse_low_consumption_file(self, file_path=""):
        return _io_pool.submit(lambda: self._audit_service.parse_file(file_path)).result()

    def export_low_consumption_report(self, items):
        def _do_export():
            res = self._audit_service.export_report(items)
            if res.get("success") and res.get("file_path"):
                self.open_file_external(res["file_path"])
            return res

        return _io_pool.submit(_do_export).result()
