# Tasks to perform during installation of the Native Speech Generation NVDA add-on
# Copyright (C) 2025 Muhammad.
# This add-on is free software, licensed under the terms of the GNU General Public License (version 2).
# For more details see: https://www.gnu.org/licenses/gpl-2.0.html

import wx
import gui
import addonHandler
import config
from logHandler import log

addonHandler.initTranslation()

CONFIG_DOMAIN = "NativeSpeechGeneration"

def onInstall():
    def show_info_dialog():
        message = _("""The Native Speech Generation add-on has been installed successfully.

To use this add-on, you must obtain a Gemini API key from Google AI Studio and enter it in the add-on's settings (NVDA Menu -> Tools -> Native Speech Generation).

To run the Native Speech Generation add-on, you can press the shortcut NVDA+Control+Shift+G (this can be changed via NVDA Menu -> Preferences -> Input Gestures, under the Native Speech Generation category).

Please note that this add-on bundles external libraries. If you encounter any issues, please ensure your NVDA version is compatible.""")
        
        title = _("Native Speech Generation Installation Complete")
        
        gui.messageBox(message, title, wx.OK | wx.ICON_INFORMATION)

    wx.CallAfter(show_info_dialog)

def onUninstall():
    if CONFIG_DOMAIN in config.conf.spec:
        del(config.conf.spec[CONFIG_DOMAIN])
        
    for profile in config.conf.profiles:
        if CONFIG_DOMAIN in profile:
            del(profile[CONFIG_DOMAIN])
            
    log.info(f"Configuration for '{CONFIG_DOMAIN}' has been cleaned up upon uninstallation.")