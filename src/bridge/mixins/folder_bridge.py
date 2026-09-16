class FolderBridge:
    """Network folder management, monitoring, and background indexing bridge."""

    def get_folder_status(self):
        return self._folder_service.get_folder_status()

    def add_network_folder(self, path=""):
        if not path:
            path = self.pick_folder(title="Select Folder to Add")
        if not path:
            return {"success": False, "cancelled": True}
        return self._folder_service.add_network_folder(path)

    def remove_network_folder(self, path):
        return self._folder_service.remove_network_folder(path)

    def start_indexing(self, target_folders=None, full_reindex=False, **kwargs):
        if isinstance(target_folders, dict):
            full_reindex = target_folders.get("full_reindex", target_folders.get("full", False))
            target_folders = target_folders.get("target_folders", None)
        return self._folder_service.start_indexing(target_folders=target_folders, full_reindex=full_reindex)

    def get_indexing_status(self):
        return self._folder_service.get_indexing_status()

    def check_folder_changes(self):
        return self._folder_service.check_folder_changes()

    def get_auto_index_settings(self):
        return {"success": True, "mode": self._folder_service.get_auto_index_mode()}

    def set_auto_index_settings(self, mode):
        saved = self._folder_service.set_auto_index_mode(mode)
        return {"success": True, "mode": saved}
