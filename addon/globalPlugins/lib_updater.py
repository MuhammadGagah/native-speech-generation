import os
import wx
import gui
import addonHandler
import core
import urllib.request
import zipfile
import threading
import shutil
import glob
from logHandler import log
from typing import Callable

addonHandler.initTranslation()

LIB_URL = "https://github.com/MuhammadGagah/python-library-add-on-Native-Speech-Generation/releases/latest/download/lib.zip"

# Centralized Path Definitions
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(ADDON_DIR, "globalPlugins", "lib")

def cleanup_trash() -> None:
    """
    Garbage Collection: Delete any 'lib_trash_*' folders left over from previous updates.
    Run this at startup when files are likely unlocked.
    """
    try:
        gp_base = os.path.join(ADDON_DIR, "globalPlugins")
        trash_pattern = os.path.join(gp_base, "lib_trash_*")
        for trash_dir in glob.glob(trash_pattern):
            if os.path.isdir(trash_dir):
                try:
                    shutil.rmtree(trash_dir, ignore_errors=True)
                    log.info(f"lib_updater: Cleaned up trash directory: {trash_dir}")
                except Exception as e:
                    log.warning(f"lib_updater: Failed to clean trash {trash_dir}: {e}")
    except Exception as e:
        log.warning(f"lib_updater: Error during trash cleanup: {e}")

def initialize() -> None:
    """
    Entry point for initialization. Performs cleanup.
    """
    cleanup_trash()


def download_and_extract(addon_dir: str, progress_callback: Callable[[int, str], None]) -> bool:
    """
    Downloads and extracts the lib folder.
    """
    lib_dir = os.path.join(addon_dir, "globalPlugins", "lib")
    zip_path = os.path.join(addon_dir, "lib.zip")

    try:
        wx.CallAfter(progress_callback, 10, _("Downloading libraries..."))
        # Download the file
        with urllib.request.urlopen(LIB_URL) as response, open(zip_path, 'wb') as out_file:
            total_length = response.length
            if total_length:
                dl = 0
                while True:
                    data = response.read(8192)
                    if not data:
                        break
                    dl += len(data)
                    out_file.write(data)
                    percent = 10 + int(dl / total_length * 70)
                    wx.CallAfter(progress_callback, percent, _("Downloading..."))
            else: # No content length
                 out_file.write(response.read())

        log.info("Download complete. Extracting...")
        wx.CallAfter(progress_callback, 80, _("Extracting libraries..."))

        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # We enforce extracting into globalPlugins, assuming the zip contains 'lib' folder or similar structure.
            # Based on previous code: zip_ref.extractall(os.path.join(addon_dir, "globalPlugins"))
            # If the zip contains "lib/..." inside, extracting to globalPlugins creates globalPlugins/lib
            zip_ref.extractall(os.path.join(addon_dir, "globalPlugins"))
        
        log.info("Extraction complete.")
        wx.CallAfter(progress_callback, 100, _("Extraction complete."))

        if os.path.exists(zip_path):
            os.remove(zip_path)
        return True

    except Exception as e:
        log.error(f"Failed to download or extract libraries: {e}", exc_info=True)
        wx.CallAfter(gui.messageBox, 
            _("Failed to download or extract required libraries. The add-on might not work correctly.\n\nError: {error}").format(error=e),
            _("Error"), wx.OK | wx.ICON_ERROR)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False

def check_and_install_dependencies(force_reinstall: bool = False) -> None:
    addon_dir = ADDON_DIR
    lib_dir = LIB_DIR
    
    if not force_reinstall and os.path.exists(lib_dir):
        log.info("Dependencies already installed, skipping check.")
        return

    def run_installation() -> None:
        progress_dialog = wx.ProgressDialog(
            _("Installing Dependencies"),
            _("Checking for required libraries..."),
            maximum=100,
            parent=gui.mainFrame
        )

        def update_progress(progress: int, message: str) -> None:
            if progress == 100:
                progress_dialog.Update(100, _("Installation complete!"))
                wx.CallLater(500, progress_dialog.Destroy)
            else:
                progress_dialog.Update(progress, message)

        def do_work() -> None:
            if force_reinstall and os.path.exists(lib_dir):
                try:
                    shutil.rmtree(lib_dir)
                except Exception as e:
                    log.warning(f"Failed to remove existing lib dir during reinstall: {e}")

            success = download_and_extract(addon_dir, update_progress)
            
            def final_message() -> None:
                if success:
                    message = _("The Native Speech Generation libraries have been successfully installed/updated.\n\nPlease restart NVDA for the changes to take effect.")
                    title = _("Installation Complete")
                    res = wx.MessageBox(message, title, wx.OK | wx.ICON_INFORMATION)
                    if res == wx.OK:
                        core.restart()
                else:
                    message = _("Library installation failed. Please check the log.")
                    title = _("Error")
                    wx.CallAfter(wx.MessageBox, message, title, wx.OK | wx.ICON_ERROR)

            wx.CallAfter(final_message)

        threading.Thread(target=do_work).start()

    def confirm_action() -> None:
        if force_reinstall:
             msg = _("Are you sure you want to reinstall the libraries? This will redownload the dependencies and require an NVDA restart.")
             title = _("Confirm Reinstall")
        else:
             msg = _("Required libraries for Native Speech Generation are missing. Click OK to download them.")
             title = _("Missing Dependencies")

        res = wx.MessageBox(msg, title, wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
        
        if res == wx.OK:
            run_installation()
        else:
            log.info("User cancelled dependency installation.")

    wx.CallAfter(confirm_action)

def reinstall_dependencies() -> None:
    """Public wrapper to force reinstallation."""
    check_and_install_dependencies(force_reinstall=True)

# ----------------------------------------------------------------------------
# NVDA Plugin Stub
# ----------------------------------------------------------------------------
# NVDA attempts to load every .py file in globalPlugins as a plugin.
# To avoid "AttributeError: module has no attribute 'GlobalPlugin'", we define a dummy one.
import globalPluginHandler
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    pass
