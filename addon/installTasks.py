# Tasks to perform during installation of the Native Speech Generation NVDA add-on
# Copyright (C) 2025 Muhammad.
# This add-on is free software, licensed under the terms of the GNU General Public License (version 2).
# For more details see: https://www.gnu.org/licenses/gpl-2.0.html

import addonHandler
import config
from logHandler import log

addonHandler.initTranslation()

CONFIG_DOMAIN = "NativeSpeechGeneration"

def onInstall() -> None:
    """
    Called when the add-on is installed.
    Dependency checks are now handled dynamically by the global plugin at runtime.
    """
    log.info("Native Speech Generation add-on installed. Dependencies will be checked periodically by the global plugin.")

def onUninstall() -> None:
    """
    Called when the add-on is uninstalled.
    Cleans up configuration.
    """
    if CONFIG_DOMAIN in config.conf.spec:
        del(config.conf.spec[CONFIG_DOMAIN])
        
    for profile in config.conf.profiles:
        if CONFIG_DOMAIN in profile:
            del(profile[CONFIG_DOMAIN])
            
    log.info(f"Configuration for '{CONFIG_DOMAIN}' has been cleaned up upon uninstallation.")
