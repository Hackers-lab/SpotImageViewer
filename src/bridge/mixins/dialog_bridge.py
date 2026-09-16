import os
import re

from .base import _get_tk_root


class DialogBridge:
    """Native Windows and cross-platform File/Folder dialog bridge."""

    def _ensure_window_enabled(self):
        """Ensures the PyWebView main window is enabled and brought to foreground."""
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst and hasattr(inst, 'Handle'):
                    import ctypes
                    hwnd = inst.Handle.ToInt64()
                    ctypes.windll.user32.EnableWindow(hwnd, True)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    @staticmethod
    def _format_file_filters(file_types):
        """
        Normalizes arbitrary file_types specifications into valid formats for:
        1. WinForms OpenFileDialog/SaveFileDialog: 'Desc1 (*.ext)|*.ext|All Files (*.*)|*.*'
        2. pywebview Window.create_file_dialog: ('Desc1 (*.ext)', 'All Files (*.*)')
        3. tkinter.filedialog: [('Desc1', '*.ext'), ('All Files', '*.*')]
        """
        pairs = []
        if not file_types:
            pairs = [("All Files", "*.*")]
        elif isinstance(file_types, str):
            if "|" in file_types:
                parts = [p.strip() for p in file_types.split("|") if p.strip()]
                for i in range(0, len(parts) - 1, 2):
                    pairs.append((parts[i], parts[i + 1]))
            else:
                pairs.append((file_types, file_types))
        elif isinstance(file_types, (list, tuple)):
            for item in file_types:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    pairs.append((str(item[0]), str(item[1])))
                elif isinstance(item, str):
                    m = re.match(r'^(.*?)\s*\((.*?)\)$', item.strip())
                    if m:
                        pairs.append((m.group(1).strip(), m.group(2).strip()))
                    else:
                        pairs.append((item.strip(), item.strip()))

        normalized_pairs = []
        has_all = False
        for desc, patt in pairs:
            clean_desc = re.sub(r'\s*\(.*?\)\s*$', '', desc).strip()
            clean_patt = patt.strip('() ').strip()
            if clean_patt == '*.*' or clean_desc.lower() == 'all files':
                has_all = True
                normalized_pairs.append(('All Files', '*.*'))
            else:
                normalized_pairs.append((clean_desc or 'Supported Files', clean_patt))

        if not has_all:
            normalized_pairs.append(('All Files', '*.*'))

        # 1. WinForms filter string: "Description (pattern)|pattern|All Files (*.*)|*.*"
        wf_parts = []
        for desc, patt in normalized_pairs:
            if patt == '*.*':
                wf_parts.append('All Files (*.*)')
                wf_parts.append('*.*')
            else:
                wf_parts.append(f'{desc} ({patt})')
                wf_parts.append(patt)
        winforms_str = '|'.join(wf_parts)

        # 2. PyWebView filter tuple: ('Safe Description (*.ext)', ...)
        pwv_list = []
        for desc, patt in normalized_pairs:
            safe_desc = re.sub(r'[^\w ]', ' ', desc)
            safe_desc = ' '.join(safe_desc.split()) or 'Files'
            clean_pw_patt = patt.replace(' ', '')
            pwv_str = f'{safe_desc} ({clean_pw_patt})'
            pwv_list.append(pwv_str)

        # 3. Tkinter filetypes list: [('Description', '*.ext1 *.ext2'), ...]
        tk_list = []
        for desc, patt in normalized_pairs:
            tk_patt = patt.replace(';', ' ')
            tk_list.append((desc, tk_patt))

        return winforms_str, tuple(pwv_list), tk_list

    def pick_file(self, title="Select File", file_types=None):
        wf_filter, pwv_filter, tk_filter = self._format_file_filters(file_types)
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System')
                    from System.Windows.Forms import OpenFileDialog, DialogResult
                    from System import Func, Object

                    def _show_ofd():
                        try:
                            ofd = OpenFileDialog()
                            ofd.Title = title
                            ofd.RestoreDirectory = True
                            ofd.Filter = wf_filter
                            ofd.FilterIndex = 1
                            res = ofd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return ofd.FileName
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_ofd))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_file WinForms Invoke error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=pwv_filter)
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0]
                return ""
        except Exception as e:
            print(f"[pick_file webview error]: {e}")

        try:
            from tkinter import filedialog
            root = _get_tk_root()
            root.attributes('-topmost', True)
            chosen = filedialog.askopenfilename(title=title, filetypes=tk_filter)
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_file]: {e}")
            self._ensure_window_enabled()
            return ""

    def pick_save_file(self, title="Save File", default_filename="export.xlsx", file_types=None):
        wf_filter, pwv_filter, tk_filter = self._format_file_filters(file_types)
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System')
                    from System.Windows.Forms import SaveFileDialog, DialogResult
                    from System import Func, Object

                    def _show_sfd():
                        try:
                            sfd = SaveFileDialog()
                            sfd.Title = title
                            sfd.FileName = default_filename
                            sfd.RestoreDirectory = True
                            sfd.Filter = wf_filter
                            sfd.FilterIndex = 1
                            res = sfd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return sfd.FileName
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_sfd))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_save_file WinForms Invoke error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                res = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_filename, file_types=pwv_filter)
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0] if isinstance(res, (list, tuple)) else str(res)
                return ""
        except Exception as e:
            print(f"[pick_save_file webview error]: {e}")

        try:
            from tkinter import filedialog
            root = _get_tk_root()
            root.attributes('-topmost', True)
            chosen = filedialog.asksaveasfilename(
                title=title,
                initialfile=default_filename,
                filetypes=tk_filter
            )
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_save_file]: {e}")
            self._ensure_window_enabled()
            return ""

    def pick_folder(self, title="Select Folder to Add", initial_dir=""):
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView, OpenFolderDialog
                inst = BrowserView.instances.get(uid)
                if inst:
                    from System import Func, Object

                    def _show_native_folder():
                        try:
                            res = OpenFolderDialog.show(inst, initial_dir or None, False, title)
                            if res and len(res) > 0:
                                return res[0]
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_native_folder))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_folder WinForms OpenFolderDialog error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                res = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial_dir or "")
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0]
                return ""
        except Exception as e:
            print(f"[pick_folder webview error]: {e}")

        try:
            from tkinter import filedialog
            root = _get_tk_root()
            root.attributes('-topmost', True)
            chosen = filedialog.askdirectory(title=title)
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_folder]: {e}")
            self._ensure_window_enabled()
            return ""

    def pick_files_multiple(self, title="Select Files", file_types=None):
        """Allows selecting multiple files via WinForms, webview, or tkinter fallback."""
        wf_filter, pwv_filter, tk_filter = self._format_file_filters(file_types)
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System')
                    from System.Windows.Forms import OpenFileDialog, DialogResult
                    from System import Func, Object

                    def _show_ofd_multi():
                        try:
                            ofd = OpenFileDialog()
                            ofd.Title = title
                            ofd.Multiselect = True
                            ofd.RestoreDirectory = True
                            ofd.Filter = wf_filter
                            ofd.FilterIndex = 1
                            res = ofd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return list(ofd.FileNames)
                            return []
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_ofd_multi))
                    return list(chosen) if chosen else []
        except Exception as e:
            print(f"[pick_files_multiple WinForms Invoke error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=pwv_filter)
                self._ensure_window_enabled()
                if res:
                    return list(res)
                return []
        except Exception as e:
            print(f"[pick_files_multiple webview error]: {e}")

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            chosen = filedialog.askopenfilenames(title=title, filetypes=tk_filter)
            root.destroy()
            self._ensure_window_enabled()
            return list(chosen) if chosen else []
        except Exception as e:
            print(f"[Error in pick_files_multiple]: {e}")
            self._ensure_window_enabled()
            return []
