# Tasks to perform during installation of the Native Speech Generation NVDA add-on
# Copyright (C) 2025 Muhammad.
# This add-on is free software, licensed under the terms of the GNU General Public License (version 2).
# For more details see: https://www.gnu.org/licenses/gpl-2.0.html

import os
import wx
import gui
import addonHandler
import core
import config
from logHandler import log
import urllib.request
import zipfile
import threading

addonHandler.initTranslation()

CONFIG_DOMAIN = "NativeSpeechGeneration"
LIB_URL = "https://github.com/MuhammadGagah/python-library-add-on-Native-Speech-Generation/releases/download/1.0.0/lib.zip"

def download_and_extract(addon_dir, progress_callback):
    """
    Downloads and extracts the lib folder.
    """
    lib_dir = os.path.join(addon_dir, "globalPlugins", "lib")
    if os.path.exists(lib_dir):
        log.info("lib directory already exists. Skipping download.")
        wx.CallAfter(progress_callback, 100, _("Dependencies already satisfied."))
        return True

    log.info(f"lib directory not found. Downloading from {LIB_URL}")
    zip_path = os.path.join(addon_dir, "lib.zip")

    try:
        wx.CallAfter(progress_callback, 10, _("Downloading libraries..."))
        # Download the file
        with urllib.request.urlopen(LIB_URL) as response, open(zip_path, 'wb') as out_file:
            total_length = response.length
            if total_length:
                total_length = total_length
                dl = 0
                while True:
                    data = response.read(8192)
                    if not data:
                        break
                    dl += len(data)
                    out_file.write(data)
                    # Update progress, scaling download to 80% of the task
                    wx.CallAfter(progress_callback, 10 + int(dl / total_length * 70), _("Downloading..."))
            else: # No content length
                 out_file.write(response.read())

        log.info("Download complete. Extracting...")
        wx.CallAfter(progress_callback, 80, _("Extracting libraries..."))

        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(addon_dir, "globalPlugins"))
        
        log.info("Extraction complete.")
        wx.CallAfter(progress_callback, 100, _("Extraction complete."))

        # Clean up the zip file
        os.remove(zip_path)
        return True

    except Exception as e:
        log.error(f"Failed to download or extract libraries: {e}", exc_info=True)
        wx.CallAfter(gui.messageBox, 
            _("Failed to download or extract required libraries. The add-on might not work correctly.\n\nError: {error}").format(error=e),
            _("Error"), wx.OK | wx.ICON_ERROR)
        # Clean up partial download if it exists
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False

def onInstall():
    log.info("Native Speech Generation add-on installed. Dependencies will be checked after restart.")

def check_and_install_dependencies():
    addon = addonHandler.getCodeAddon()
    addon_dir = addon.path
    lib_dir = os.path.join(addon_dir, "globalPlugins", "lib")
    if os.path.exists(lib_dir):
        log.info("Dependencies already installed, skipping check.")
        return

    def run_installation():
        progress_dialog = wx.ProgressDialog(
            _("Installing Dependencies"),
            _("Checking for required libraries..."),
            maximum=100,
            parent=gui.mainFrame
        )

        def update_progress(progress, message):
            if progress == 100:
                progress_dialog.Update(100, _("Installation complete!"))
                # Short delay before closing
                wx.CallLater(500, progress_dialog.Destroy)
            else:
                progress_dialog.Update(progress, message)

        def do_work():
            success = download_and_extract(addon_dir, update_progress)
            
            # This needs to run after the dialog is closed
            def final_message():
                if success:
                    # Translators: Shown after successful dependency installation, with instructions for the user.
                    message = _("""The Native Speech Generation add-on has been installed successfully.

To use this add-on, you must obtain a Gemini API key from Google AI Studio and enter it in the add-on's settings (NVDA Menu -> Preferences -> Settings -> Native Speech Generation).

To open the generation dialog, you can press the shortcut NVDA+Control+Shift+G (this can be changed via NVDA Menu -> Preferences -> Input Gestures).
""")
                    title = _("Native Speech Generation Installation Complete")
                    res = wx.MessageBox(message, title, wx.OK | wx.ICON_INFORMATION)
                    if res == wx.OK:
                        core.restart()
                else:
                    # Translators: Shown if dependency installation fails.
                    message = _("Dependency installation failed. The Native Speech Generation add-on might not work correctly. Please review the log for errors.")
                    title = _("Installation Warning")
                    wx.CallAfter(wx.MessageBox, message, title, wx.OK | wx.ICON_WARNING)

            wx.CallAfter(final_message)

        # Start the download/extract in a separate thread to keep UI responsive
        threading.Thread(target=do_work).start()

    def confirm_install():
        # Translators: Shown after NVDA restart when dependencies are missing,
        # asking user to confirm downloading required libraries.
        res = wx.MessageBox(
            _("Required libraries for Native Speech Generation are missing. "
              "They will be downloaded and installed now.\n\n"
              "Click OK to continue."),
            _("Installing Dependencies"),
            wx.OK | wx.CANCEL | wx.ICON_INFORMATION
        )
        if res == wx.OK:
            run_installation()
        else:
            log.info("User cancelled dependency installation.")

    wx.CallAfter(confirm_install)

def onUninstall():
    if CONFIG_DOMAIN in config.conf.spec:
        del(config.conf.spec[CONFIG_DOMAIN])
        
    for profile in config.conf.profiles:
        if CONFIG_DOMAIN in profile:
            del(profile[CONFIG_DOMAIN])
            
    log.info(f"Configuration for '{CONFIG_DOMAIN}' has been cleaned up upon uninstallation.")