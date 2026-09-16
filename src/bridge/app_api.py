"""
Python-to-JavaScript RPC Bridge exposed to the PyWebView window.
Composes modular domain bridge mixins into a single unified Facade.
All 112 RPC endpoints remain 100% backward compatible with frontend callers.
"""

from .mixins import (
    BaseBridge,
    SystemBridge,
    DialogBridge,
    ViewerBridge,
    CalculatorBridge,
    FolderBridge,
    FuzzyBridge,
    AuditBridge,
    OSDBridge,
    DCRCBridge,
)


class AppAPI(
    BaseBridge,
    SystemBridge,
    DialogBridge,
    ViewerBridge,
    CalculatorBridge,
    FolderBridge,
    FuzzyBridge,
    AuditBridge,
    OSDBridge,
    DCRCBridge,
):
    """
    Unified RPC Bridge for PyWebView.
    Dispatches calls to dedicated domain mixins for modularity and maintainability.
    """

    def __init__(self, window=None):
        super().__init__(window=window)


AppBridge = AppAPI

