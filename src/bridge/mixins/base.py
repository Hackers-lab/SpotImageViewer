import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

_tk_lock = threading.Lock()
_tk_root = None

def _get_tk_root():
    global _tk_root
    with _tk_lock:
        if _tk_root is None:
            import tkinter as tk
            _tk_root = tk.Tk()
            _tk_root.withdraw()
        return _tk_root

try:
    from core import config, database, utils, tariff_manager
except ImportError:
    import config, database, utils, tariff_manager

# Shared thread pool for offloading heavy I/O from the PyWebView bridge thread.
_io_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="siv-io")
# Dedicated thread pool for image decoding and resizing to prevent UI thread starvation
_image_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="siv-img")


def _wait_db(timeout=5.0):
    """Wait for init_db to finish (prevents deadlock with schema migration locks)."""
    database.init_db_ready.wait(timeout=timeout)


class BaseBridge:
    """Base mixin managing window reference and lazy-loaded domain services."""

    def __init__(self, window=None):
        self._window = window
        self._billing_service_inst = None
        self._image_service_inst = None
        self._fuzzy_service_inst = None
        self._consumer_service_inst = None
        self._audit_service_inst = None
        self._folder_service_inst = None
        self._update_service_inst = None
        self._osd_service_inst = None
        self._last_dcrc_result = None

    def set_window(self, window):
        self._window = window

    @property
    def _billing_service(self):
        if self._billing_service_inst is None:
            try:
                from core.services.billing_service import BillingService
            except ImportError:
                from services.billing_service import BillingService
            self._billing_service_inst = BillingService()
        return self._billing_service_inst

    @property
    def _image_service(self):
        if self._image_service_inst is None:
            try:
                from core.services.image_service import ImageService
            except ImportError:
                from services.image_service import ImageService
            self._image_service_inst = ImageService()
        return self._image_service_inst

    @property
    def _fuzzy_service(self):
        if self._fuzzy_service_inst is None:
            try:
                from core.services.fuzzy_service import FuzzyService
            except ImportError:
                from services.fuzzy_service import FuzzyService
            self._fuzzy_service_inst = FuzzyService()
        return self._fuzzy_service_inst

    @property
    def _consumer_service(self):
        if self._consumer_service_inst is None:
            try:
                from core.services.consumer_data_service import ConsumerDataService
            except ImportError:
                from services.consumer_data_service import ConsumerDataService
            self._consumer_service_inst = ConsumerDataService()
        return self._consumer_service_inst

    @property
    def _audit_service(self):
        if self._audit_service_inst is None:
            try:
                from core.services.audit_service import AuditService
            except ImportError:
                from services.audit_service import AuditService
            self._audit_service_inst = AuditService()
        return self._audit_service_inst

    @property
    def _folder_service(self):
        if self._folder_service_inst is None:
            try:
                from core.services.folder_service import FolderIndexerService
            except ImportError:
                from services.folder_service import FolderIndexerService
            self._folder_service_inst = FolderIndexerService()
        return self._folder_service_inst

    @property
    def _update_service(self):
        if self._update_service_inst is None:
            try:
                from core.services.update_service import UpdateService
            except ImportError:
                from services.update_service import UpdateService
            self._update_service_inst = UpdateService()
        return self._update_service_inst

    @property
    def _osd_service(self):
        if self._osd_service_inst is None:
            try:
                from core.services.osd_service import OSDService
            except ImportError:
                from services.osd_service import OSDService
            self._osd_service_inst = OSDService()
        return self._osd_service_inst
