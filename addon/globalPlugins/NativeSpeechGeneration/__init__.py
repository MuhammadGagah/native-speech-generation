# -*- coding: utf-8 -*-
import os
import sys
import mimetypes
import struct
import tempfile
import threading
import time
import wave
import webbrowser
import shutil
import platform
from typing import Any, TYPE_CHECKING
import contextlib

# NVDA & Local Imports
import addonHandler
import globalPluginHandler
import gui
import wx
import core
import config
import ui
from gui.settingsDialogs import SettingsPanel
from logHandler import log
from scriptHandler import script

# Windows-only
import winsound

# Third-party
import requests

# Initialize translation
addonHandler.initTranslation()

if TYPE_CHECKING:
    def _(msg: str) -> str:
        return msg

# Initialization & Dependency Management
pkg_dir = os.path.dirname(os.path.abspath(__file__))
addon_dir = os.path.dirname(os.path.dirname(pkg_dir))

# Ensure globalPlugins is in path (it usually is, but just in case)
gp_dir = os.path.dirname(pkg_dir)
if gp_dir not in sys.path:
    sys.path.insert(0, gp_dir)

try:
    from . import lib_updater

    # Run trash cleanup
    lib_updater.initialize()
    # Use centralized lib_dir definition
    lib_dir = lib_updater.LIB_DIR
except Exception as e:
    log.error(f"Failed to initialize lib_updater: {e}", exc_info=True)
    # Fallback if import fails
    lib_dir = os.path.join(pkg_dir, "lib")

LIBS_AVAILABLE = False

if not os.path.isdir(lib_dir):
    def run_check() -> None:
        try:
            from . import lib_updater
            lib_updater.check_and_install_dependencies(force_reinstall=False)
        except Exception as e:
            log.error(f"Failed to run lib_updater check: {e}", exc_info=True)

    wx.CallAfter(run_check)
else:
    # If we've reached this point, the lib directory exists.
    # Add it to the path and set the flag.
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    LIBS_AVAILABLE = True


# Global Plugin Definition
if not LIBS_AVAILABLE:
    # Dummy Plugin (Dependencies Missing)
    class GlobalPlugin(globalPluginHandler.GlobalPlugin):
        """
        A dummy plugin that informs the user that the addon is not ready
        and that a restart is required.
        """

        # Translators: A script to open the main dialog.
        @script(
            description=_("Open the Native Speech Generation dialog"),
            category=_("Native Speech Generation"),
            gesture="kb:NVDA+Control+Shift+G",
        )
        def script_openDialog(self, gesture: Any) -> None:
            # Translators: Shown when the add-on is not ready yet and requires NVDA restart.
            wx.CallAfter(
                wx.MessageBox,
                _(
                    "Native Speech Generation is installing dependencies. "
                    "Please restart NVDA for the changes to take effect."
                ),
                _("Restart Required"),
                wx.OK | wx.ICON_INFORMATION,
            )

else:
    # Full Functionality
    IMPORT_ERROR_MSG = None
    try:
        # Dependency Conflict Resolution (Scoped / Safe Mode)
        # We handle typing_extensions conflict that can happen in some NVDA environments
        original_typing_ext = sys.modules.get("typing_extensions")
        if "typing_extensions" in sys.modules:
            del sys.modules["typing_extensions"]
        try:
            from google import genai
            from google.genai import types

            GENAI_AVAILABLE = True
            log.info("google-genai loaded successfully.")
        finally:
            if original_typing_ext:
                sys.modules["typing_extensions"] = original_typing_ext
    except Exception as e:
        genai = None
        types = None
        GENAI_AVAILABLE = False
        
        err_msg = (
            f"Google GenAI Import Error:\n{e}\n\n"
            f"Python: {sys.version}\n"
            f"Arch: {platform.architecture()}\n"
            f"Path: {sys.path[:3]}..."
        )
        log.warning("google-genai not available", exc_info=True)
        log.error(err_msg)
        IMPORT_ERROR_MSG = err_msg

    # Constants & Defaults
    CONFIG_DOMAIN = "NativeSpeechGeneration"
    DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
    SECOND_MODEL = "gemini-2.5-pro-preview-tts"
    VOICE_SAMPLE_BASE = "https://www.gstatic.com/aistudio/voices/samples"

    FALLBACK_VOICES = [
        "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
        "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
        "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
        "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
        "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
    ]
    CACHE_FILE = os.path.join(addon_dir, "voices_cache.json")
    CACHE_TTL = 24 * 60 * 60  # 24 hours

    # Audio Helpers
    # Audio Helpers
    try:
        from . import talkWithAI
    except ImportError:
        talkWithAI = None
        log.warning("talkWithAI module not found.")

    def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
        """Parses the MIME type string to extract sample rate and bit depth."""
        bits_per_sample = 16
        rate = 24000
        if not mime_type:
            return {"bits_per_sample": bits_per_sample, "rate": rate}

        parts = [p.strip() for p in mime_type.split(";")]
        for p in parts:
            if p.lower().startswith("rate="):
                with contextlib.suppress(Exception):
                    rate = int(p.split("=", 1)[1])
            if "L" in p and p.lower().startswith("audio/l"):
                with contextlib.suppress(Exception):
                    bits_per_sample = int(p.split("L", 1)[1])
        return {"bits_per_sample": bits_per_sample, "rate": rate}

    def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
        """Wraps raw PCM audio data in a WAV header based on MIME type parameters."""
        if mime_type and "wav" in mime_type.lower():
            return audio_data

        params = parse_audio_mime_type(mime_type)
        bits_per_sample = params.get("bits_per_sample", 16) or 16
        sample_rate = params.get("rate", 24000) or 24000
        num_channels = 1
        data_size = len(audio_data)
        bytes_per_sample = bits_per_sample // 8
        block_align = num_channels * bytes_per_sample
        byte_rate = sample_rate * block_align
        chunk_size = 36 + data_size

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", chunk_size, b"WAVE", b"fmt ", 16,
            1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample,
            b"data", data_size
        )
        return header + audio_data

    def merge_wav_files(input_paths: list[str], output_path: str) -> None:
        """Combines multiple WAV files into a single continuous audio file."""
        if not input_paths:
            raise ValueError("No input WAV files to merge.")

        with wave.open(input_paths[0], 'rb') as w0:
            params = w0.getparams()
            frames = [w0.readframes(w0.getnframes())]

        for p in input_paths[1:]:
            with wave.open(p, 'rb') as wi:
                if wi.getparams() != params:
                    raise ValueError("WAV files have different parameters; cannot merge safely.")
                frames.append(wi.readframes(wi.getnframes()))

        with wave.open(output_path, 'wb') as wo:
            wo.setparams(params)
            for fr in frames:
                wo.writeframes(fr)
        log.info(f"Merged {len(input_paths)} WAV files -> {output_path}")

    def save_binary_file(file_name: str, data: bytes) -> None:
        """Writes binary data to a file, creating parent directories if necessary."""
        os.makedirs(os.path.dirname(file_name) or ".", exist_ok=True)
        with open(file_name, "wb") as f:
            f.write(data)
        log.info(f"Saved audio file: {file_name}")

    def safe_startfile(path: str) -> None:
        """Opens a file with the default OS application, handling errors safely."""
        try:
            os.startfile(path)
        except Exception as e:
            log.error(f"Failed to open file: {e}", exc_info=True)
            wx.CallAfter(
                wx.MessageBox,
                _("Audio generated, but failed to play automatically: {error}").format(error=e),
                _("Info"),
                wx.OK | wx.ICON_INFORMATION
            )

    # Settings Panel
    class NativeSpeechSettingsPanel(SettingsPanel):
        title = _("Native Speech Generation")

        def makeSettings(self, settingsSizer: wx.Sizer) -> None:
            sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
            
            # API Key Configuration Group
            # Match VisionAssistant layout: Label -> Input -> Checkbox in a horizontal row
            apiSizer = wx.BoxSizer(wx.HORIZONTAL)
            
            apiLabel = wx.StaticText(self, label=_("&Gemini API Key:"))
            apiSizer.Add(apiLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            
            api_value = config.conf.get(CONFIG_DOMAIN, {}).get("apiKey", "")
            
            self.apiKeyCtrl_hidden = wx.TextCtrl(
                self,
                value=api_value,
                style=wx.TE_PASSWORD
            )
            self.apiKeyCtrl_visible = wx.TextCtrl(
                self,
                value=api_value
            )
            self.apiKeyCtrl_visible.Hide()
            
            # Add inputs with EXPAND to fill available space
            apiSizer.Add(self.apiKeyCtrl_hidden, 1, wx.EXPAND | wx.RIGHT, 5)
            apiSizer.Add(self.apiKeyCtrl_visible, 1, wx.EXPAND | wx.RIGHT, 5)
            
            self.showApiCheck = wx.CheckBox(self, label=_("Show API Key"))
            self.showApiCheck.Bind(wx.EVT_CHECKBOX, self.onToggleApiVisibility)
            apiSizer.Add(self.showApiCheck, 0, wx.ALIGN_CENTER_VERTICAL)
            
            # Add the row to the main settings sizer
            sHelper.addItem(apiSizer)
            
            self.getKeyBtn = wx.Button(self, label=_("&How to get API Key..."))
            sHelper.addItem(self.getKeyBtn)
            self.getKeyBtn.Bind(wx.EVT_BUTTON, self.onGetKey)

            # Reinstall libraries button
            self.reinstallBtn = wx.Button(self, label=_("&Reinstall Libraries"))
            sHelper.addItem(self.reinstallBtn)
            self.reinstallBtn.Bind(wx.EVT_BUTTON, self.onReinstall)

        def onToggleApiVisibility(self, event: wx.Event) -> None:
            if self.showApiCheck.IsChecked():
                self.apiKeyCtrl_visible.SetValue(self.apiKeyCtrl_hidden.GetValue())
                self.apiKeyCtrl_hidden.Hide()
                self.apiKeyCtrl_visible.Show()
            else:
                self.apiKeyCtrl_hidden.SetValue(self.apiKeyCtrl_visible.GetValue())
                self.apiKeyCtrl_visible.Hide()
                self.apiKeyCtrl_hidden.Show()
            self.Layout()

        def onGetKey(self, evt: wx.Event) -> None:
            webbrowser.open("https://aistudio.google.com/apikey")

        def onReinstall(self, evt: wx.Event) -> None:
            """Handles the reinstall libraries action."""
            res = wx.MessageBox(
                _("This will delete the existing library and restart NVDA to redownload it.\nAre you sure?"),
                _("Confirm Reinstall"),
                wx.OK | wx.CANCEL | wx.ICON_WARNING,
            )
            if res != wx.OK:
                return

            try:
                target_lib = lib_dir
                if os.path.exists(target_lib):
                    # Rename first to avoid lock issues, let cleanup_trash handle deletion on next run
                    temp_trash = target_lib + "_trash_" + str(time.time())
                    os.rename(target_lib, temp_trash)
                    # Try to delete immediately, but ignore errors if locked
                    shutil.rmtree(temp_trash, ignore_errors=True)

                wx.MessageBox(
                    _("Library removed successfully. NVDA will now restart to download the latest version."),
                    _("Restart Required"),
                    wx.OK | wx.ICON_INFORMATION,
                )
                core.restart()

            except Exception as e:
                log.error(f"Failed to delete lib folder: {e}", exc_info=True)
                wx.MessageBox(
                    f"Failed to remove library: {e}\nPlease check log.",
                    _("Error"),
                    wx.OK | wx.ICON_ERROR,
                )

        def onSave(self) -> None:
            if CONFIG_DOMAIN not in config.conf:
                config.conf[CONFIG_DOMAIN] = {}
            value = (
                self.apiKeyCtrl_visible.GetValue()
                if self.showApiCheck.IsChecked()
                else self.apiKeyCtrl_hidden.GetValue()
            )
            config.conf[CONFIG_DOMAIN]["apiKey"] = value

    # Main Dialog
    class NativeSpeechDialog(wx.Dialog):
        def __init__(self, parent: wx.Window) -> None:
            super().__init__(parent, title=_("Native Speech Generation (Gemini TTS)"))
            try:
                self.api_key = config.conf[CONFIG_DOMAIN]["apiKey"]
            except Exception:
                self.api_key = ""
                
            self.last_audio_path: str | None = None
            self.model = DEFAULT_MODEL
            self.mode_multi = False
            self.voices: list[dict[str, Any]] = []
            self.selected_voice_idx = 0
            self.selected_voice_idx_2 = 0
            self.is_generating = False
            self.client = None
            self.is_closed = False
            
            self._build_ui()
            threading.Thread(target=self.load_voices, daemon=True).start()
            self.text_ctrl.SetFocus()

        def _build_ui(self) -> None:
            main_sizer = wx.BoxSizer(wx.VERTICAL)
            
            # Text Input
            text_label = wx.StaticText(self, label=_("&Type text to convert here:"))
            self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(520, 160))
            main_sizer.Add(text_label, flag=wx.ALL, border=6)
            main_sizer.Add(self.text_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
            
            # Style Input
            style_label = wx.StaticText(self, label=_("&Style instructions (optional):"))
            self.style_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(520, 60))
            main_sizer.Add(style_label, flag=wx.ALL, border=6)
            main_sizer.Add(self.style_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
            
            # Model & Mode Selection
            model_sizer = wx.BoxSizer(wx.HORIZONTAL)
            model_label = wx.StaticText(self, label=_("Select &Model:"))
            self.model_choice = wx.Choice(self, choices=[_("Flash (Standard Quality)"), _("Pro (High Quality)")])
            self.model_choice.SetSelection(0)
            self.model_choice.Bind(wx.EVT_CHOICE, self.on_model_change)
            model_sizer.Add(model_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=6)
            model_sizer.Add(self.model_choice, flag=wx.ALL, border=6)
            
            self.mode_single_rb = wx.RadioButton(self, label=_("Single-speaker"), style=wx.RB_GROUP)
            self.mode_multi_rb = wx.RadioButton(self, label=_("Multi-speaker (2)"))
            self.mode_single_rb.SetValue(True)
            self.mode_single_rb.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change)
            self.mode_multi_rb.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change)
            model_sizer.Add(self.mode_single_rb, flag=wx.ALL, border=6)
            model_sizer.Add(self.mode_multi_rb, flag=wx.ALL, border=6)
            main_sizer.Add(model_sizer, flag=wx.EXPAND)
            
            # Settings Toggle
            self.settings_checkbox = wx.CheckBox(self, label=_("Advanced Settings (&Temperature)"))
            self.settings_checkbox.SetValue(False)
            main_sizer.Add(self.settings_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)
            
            # Settings Panel (Hidden)
            self.settings_panel = wx.Panel(self)
            main_sizer.Add(self.settings_panel, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
            
            pane_sizer = wx.BoxSizer(wx.VERTICAL)
            temp_sizer = wx.BoxSizer(wx.HORIZONTAL)
            temp_label = wx.StaticText(self.settings_panel, label=_("Temperature:"))
            self.temp_slider = wx.Slider(self.settings_panel, value=10, minValue=0, maxValue=20, style=wx.SL_HORIZONTAL)
            self.temp_value_label = wx.StaticText(self.settings_panel, label=self._temp_to_label(10))
            self.temp_slider.Bind(wx.EVT_SLIDER, self.on_temp_change)
            temp_sizer.Add(temp_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5)
            temp_sizer.Add(self.temp_slider, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
            temp_sizer.Add(self.temp_value_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5)
            pane_sizer.Add(temp_sizer, flag=wx.EXPAND | wx.ALL, border=5)
            self.settings_panel.SetSizer(pane_sizer)
            self.settings_panel.Hide()
            self.Bind(wx.EVT_CHECKBOX, self.on_toggle_settings, self.settings_checkbox)
            
            # Voice Panels
            self.voice_panel_single = self._build_voice_panel_single()
            self.voice_panel_multi = self._build_voice_panel_multi()
            main_sizer.Add(self.voice_panel_single, flag=wx.EXPAND | wx.ALL, border=5)
            main_sizer.Add(self.voice_panel_multi, flag=wx.EXPAND | wx.ALL, border=5)
            self.voice_panel_multi.Hide()
            
            # Action Buttons
            btn_sizer = wx.StdDialogButtonSizer()
            self.generate_btn = wx.Button(self, label=_("&Generate Speech"))
            self.generate_btn.Bind(wx.EVT_BUTTON, self.on_generate)
            btn_sizer.AddButton(self.generate_btn)
            
            self.play_btn = wx.Button(self, label=_("&Play"))
            self.play_btn.Bind(wx.EVT_BUTTON, self.on_play)
            self.play_btn.Enable(False)
            btn_sizer.AddButton(self.play_btn)
            
            self.save_btn = wx.Button(self, label=_("Save &Audio"))
            self.save_btn.Bind(wx.EVT_BUTTON, self.on_save)
            self.save_btn.Enable(False)
            btn_sizer.AddButton(self.save_btn)
            btn_sizer.Realize()
            main_sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

            # Talk With AI Button
            self.talk_btn = wx.Button(self, label=_("Talk With &AI"))
            self.talk_btn.Bind(wx.EVT_BUTTON, self.on_talk_with_ai)
            main_sizer.Add(self.talk_btn, flag=wx.ALIGN_CENTER | wx.ALL, border=5)
            
            # Footer
            footer_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.get_key_btn = wx.Button(self, label=_("API Key Settings"))
            self.get_key_btn.Bind(wx.EVT_BUTTON, self.on_settings)
            self.view_voices_btn = wx.Button(self, label=_("View voices in AI Studio"))
            self.view_voices_btn.Bind(wx.EVT_BUTTON, self.on_open_ai_studio)
            footer_sizer.Add(self.get_key_btn, flag=wx.ALL, border=6)
            footer_sizer.Add(self.view_voices_btn, flag=wx.ALL, border=6)
            main_sizer.Add(footer_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=5)
            
            self.close_btn = wx.Button(self, wx.ID_CANCEL, _("&Close"))
            main_sizer.Add(self.close_btn, flag=wx.ALIGN_CENTER | wx.ALL, border=5)
            
            self.SetSizerAndFit(main_sizer)
            self.CenterOnParent()
            self.Bind(wx.EVT_CLOSE, self.on_close)

        def _build_voice_panel_single(self) -> wx.Panel:
            panel = wx.Panel(self)
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            label = wx.StaticText(panel, label=_("Select &Voice:"))
            self.voice_choice_single = wx.Choice(panel, choices=[_("Loading voices...")])
            self.voice_choice_single.SetSelection(0)
            self.voice_choice_single.Bind(wx.EVT_CHOICE, self.on_voice_change)
            self.voice_choice_single.Bind(wx.EVT_CHAR_HOOK, self.on_voice_keypress_generic)
            self.voice_choice_single.Bind(wx.EVT_KEY_DOWN, self.on_voice_keypress_generic)
            sizer.Add(label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
            sizer.Add(self.voice_choice_single, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
            panel.SetSizer(sizer)
            return panel

        def _build_voice_panel_multi(self) -> wx.Panel:
            panel = wx.Panel(self)
            sizer = wx.BoxSizer(wx.VERTICAL)
            
            # Speaker 1
            spk1_sizer = wx.BoxSizer(wx.HORIZONTAL)
            spk1_label = wx.StaticText(panel, label=_("Speaker 1 Name:"))
            self.spk1_name_ctrl = wx.TextCtrl(panel, value="Speaker1", size=(100, -1))
            voice1_label = wx.StaticText(panel, label=_("Voice:"))
            self.voice_choice_multi1 = wx.Choice(panel, choices=[_("Loading voices...")])
            self.voice_choice_multi1.SetSelection(0)
            self.voice_choice_multi1.Bind(wx.EVT_CHOICE, self.on_voice_change)
            self.voice_choice_multi1.Bind(wx.EVT_CHAR_HOOK, self.on_voice_keypress_generic)
            self.voice_choice_multi1.Bind(wx.EVT_KEY_DOWN, self.on_voice_keypress_generic)
            spk1_sizer.Add(spk1_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
            spk1_sizer.Add(self.spk1_name_ctrl, flag=wx.RIGHT, border=10)
            spk1_sizer.Add(voice1_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
            spk1_sizer.Add(self.voice_choice_multi1, proportion=1, flag=wx.EXPAND)
            sizer.Add(spk1_sizer, flag=wx.EXPAND | wx.ALL, border=6)
            
            # Speaker 2
            spk2_sizer = wx.BoxSizer(wx.HORIZONTAL)
            spk2_label = wx.StaticText(panel, label=_("Speaker 2 Name:"))
            self.spk2_name_ctrl = wx.TextCtrl(panel, value="Speaker2", size=(100, -1))
            voice2_label = wx.StaticText(panel, label=_("Voice:"))
            self.voice_choice_multi2 = wx.Choice(panel, choices=[_("Loading voices...")])
            self.voice_choice_multi2.SetSelection(0)
            self.voice_choice_multi2.Bind(wx.EVT_CHOICE, self.on_voice_change_2)
            self.voice_choice_multi2.Bind(wx.EVT_CHAR_HOOK, self.on_voice_keypress_generic)
            self.voice_choice_multi2.Bind(wx.EVT_KEY_DOWN, self.on_voice_keypress_generic)
            spk2_sizer.Add(spk2_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
            spk2_sizer.Add(self.spk2_name_ctrl, flag=wx.RIGHT, border=10)
            spk2_sizer.Add(voice2_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
            spk2_sizer.Add(self.voice_choice_multi2, proportion=1, flag=wx.EXPAND)
            sizer.Add(spk2_sizer, flag=wx.EXPAND | wx.ALL, border=6)
            
            panel.SetSizer(sizer)
            return panel

        def on_close(self, evt: wx.Event) -> None:
            self.is_closed = True
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
            self.Destroy()

        def _temp_to_label(self, val_int: int) -> str:
            return f"{val_int / 10.0:.1f}"

        def on_temp_change(self, evt: wx.Event) -> None:
            new_value_int = evt.GetEventObject().GetValue()
            new_label_str = self._temp_to_label(new_value_int)
            self.temp_value_label.SetLabel(new_label_str)

        def on_toggle_settings(self, evt: wx.Event) -> None:
            is_shown = self.settings_checkbox.IsChecked()
            self.settings_panel.Show(is_shown)
            self.GetSizer().Layout()
            self.Fit()

        def on_model_change(self, evt: wx.Event) -> None:
            sel = self.model_choice.GetSelection()
            self.model = DEFAULT_MODEL if sel == 0 else SECOND_MODEL

        def on_mode_change(self, evt: wx.Event) -> None:
            self.mode_multi = self.mode_multi_rb.GetValue()
            self.voice_panel_single.Show(not self.mode_multi)
            self.voice_panel_multi.Show(self.mode_multi)
            self.GetSizer().Layout()
            self.Fit()

        def on_voice_change(self, evt: wx.Event) -> None:
            self.selected_voice_idx = evt.GetEventObject().GetSelection()

        def on_voice_change_2(self, evt: wx.Event) -> None:
            self.selected_voice_idx_2 = self.voice_choice_multi2.GetSelection()

        def on_voice_keypress_generic(self, evt: wx.Event) -> None:
            key = evt.GetKeyCode()
            # Usage of match statement (Python 3.10+)
            match key:
                case wx.WXK_SPACE:
                    ctrl = evt.GetEventObject()
                    idx = ctrl.GetSelection()
                    voice_name = self._get_selected_voice_name(ctrl, idx)
                    self._play_sample_for_voice(voice_name)
                case _:
                    evt.Skip()

        def _get_selected_voice_name(self, choice_ctrl: wx.Choice, idx: int | None) -> str:
            try:
                if idx is None or idx == wx.NOT_FOUND or not self.voices:
                    return self.voices[0]['name'] if self.voices else "Zephyr"
                voice_data = self.voices[idx]
                if isinstance(voice_data, dict) and 'name' in voice_data:
                    return voice_data['name']
                return str(voice_data)
            except IndexError:
                return self.voices[0]['name'] if self.voices else "Zephyr"
            except Exception as e:
                log.error(f"Failed to get selected voice name: {e}", exc_info=True)
                return "Zephyr"

        def on_settings(self, evt: wx.Event) -> None:
            self.Destroy()
            wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, NativeSpeechSettingsPanel)

        def on_open_ai_studio(self, evt: wx.Event) -> None:
            webbrowser.open("https://aistudio.google.com/generate-speech")

        def on_talk_with_ai(self, evt: wx.Event) -> None:
            if not talkWithAI:
                wx.CallAfter(wx.MessageBox, _("Talk With AI module is missing."), _("Error"), wx.OK | wx.ICON_ERROR)
                return

            if self.mode_multi:
                wx.CallAfter(wx.MessageBox, _("Talk With AI currently does not support multi-speaker mode. Please select Single-speaker."), _("Feature Limitation"), wx.OK | wx.ICON_WARNING)
                return

            if not self.api_key:
                wx.CallAfter(wx.MessageBox, _("No GEMINI_API_KEY configured."), _("Error"), wx.OK | wx.ICON_ERROR)
                return

            # Get current settings
            voice_name = self._get_selected_voice_name(self.voice_choice_single, self.selected_voice_idx)
            style_instructions = self.style_ctrl.GetValue().strip()

            try:
                # Close the main dialog first
                self.Close()
                
                # Show TalkWithAI dialog
                # We use gui.mainFrame as parent since self is being destroyed
                dlg = talkWithAI.TalkWithAIDialog(gui.mainFrame, self.api_key, voice_name, style_instructions)
                dlg.ShowModal()
            except Exception as e:
                log.error(f"Failed to open TalkWithAI dialog: {e}", exc_info=True)
                wx.CallAfter(wx.MessageBox, _("Failed to open Talk With AI: {error}").format(error=str(e)), _("Error"), wx.OK | wx.ICON_ERROR)

        def on_generate(self, evt: wx.Event) -> None:
            if self.is_generating:
                return
            if not GENAI_AVAILABLE:
                wx.CallAfter(wx.MessageBox, _("google-genai library not installed. Please restart NVDA."), _("Error"), wx.OK | wx.ICON_ERROR)
                return
            if not self.api_key:
                wx.CallAfter(wx.MessageBox, _("No GEMINI_API_KEY configured. Set it in NVDA settings."), _("Error"), wx.OK | wx.ICON_ERROR)
                return
            text = self.text_ctrl.GetValue().strip()
            if not text:
                wx.CallAfter(wx.MessageBox, _("Please enter text to generate."), _("Error"), wx.OK | wx.ICON_ERROR)
                return
                
            self.is_generating = True
            self.generate_btn.SetLabel(_("Generating..."))
            self.play_btn.Enable(False)
            self.save_btn.Enable(False)
            threading.Thread(target=self._generate_thread, args=(text,), daemon=True).start()

        def _generate_thread(self, text: str) -> None:
            ui.message(_("Generating speech, please wait..."))
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                log.error(f"Failed init genai client: {e}", exc_info=True)
                if not self.is_closed:
                    wx.CallAfter(wx.MessageBox, _("Failed to initialize Google GenAI client: {error}").format(error=str(e)), _("Error"), wx.OK | wx.ICON_ERROR)
                    wx.CallAfter(self._restore_generate_button)
                return

            def handle_success(saved_path: str | None) -> None:
                if self.is_closed: return
                if not saved_path:
                    ui.message(_("Failed to generate audio."))
                    return
                ui.message(_("Generation complete."))
                self.last_audio_path = saved_path
                safe_startfile(self.last_audio_path)
                wx.CallAfter(self.play_btn.Enable, True)
                wx.CallAfter(self.save_btn.Enable, True)

            try:
                temp = self.temp_slider.GetValue() / 10.0
                style_instructions = self.style_ctrl.GetValue().strip()
                final_text = f"{style_instructions}\n{text}" if style_instructions else text
                
                contents = [types.Content(role="user", parts=[types.Part.from_text(text=final_text)])]
                
                if not self.mode_multi:
                    voice_name = self._get_selected_voice_name(self.voice_choice_single, self.selected_voice_idx)
                    speech_config = types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)))
                else:
                    speaker1_name = self.spk1_name_ctrl.GetValue().strip() or "Speaker1"
                    speaker2_name = self.spk2_name_ctrl.GetValue().strip() or "Speaker2"
                    voice1 = self._get_selected_voice_name(self.voice_choice_multi1, self.selected_voice_idx)
                    voice2 = self._get_selected_voice_name(self.voice_choice_multi2, self.selected_voice_idx_2)
                    speech_config = types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(speaker=speaker1_name, voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice1))),
                                types.SpeakerVoiceConfig(speaker=speaker2_name, voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice2))),
                            ]
                        )
                    )
                
                generate_config = types.GenerateContentConfig(temperature=temp, response_modalities=["audio"], speech_config=speech_config)
                out_path_base = os.path.join(addon_dir, "last_audio_generated")
                
                if self.is_closed: return

                saved_path = self._stream_and_save_audio(self.client, self.model, contents, generate_config, out_path_base)
                
                if self.is_closed: return
                
                wx.CallAfter(handle_success, saved_path)
            
            except Exception as e:
                if self.is_closed: return
                ui.message(_("An error occurred during generation."))
                log.error(f"Unexpected error in generate_thread: {e}", exc_info=True)
                wx.CallAfter(wx.MessageBox, _("An unexpected error occurred: {error}").format(error=str(e)), _("Error"), wx.OK | wx.ICON_ERROR)
            finally:
                if not self.is_closed:
                    wx.CallAfter(self._restore_generate_button)

        def _restore_generate_button(self) -> None:
            self.generate_btn.SetLabel(_("&Generate Speech"))
            self.is_generating = False

        def _stream_and_save_audio(self, client: Any, model: str, contents: list[Any], config_obj: Any, out_path_base: str) -> str | None:
            file_index = 0
            saved_paths = []
            try:
                if self.is_closed: return None
                stream = client.models.generate_content_stream(model=model, contents=contents, config=config_obj)
                for chunk in stream:
                    if self.is_closed: return None
                    if not getattr(chunk, "candidates", None): continue
                    candidate = chunk.candidates[0]
                    if not candidate.content or not candidate.content.parts: continue
                    part = candidate.content.parts[0]
                    
                    if part.inline_data and getattr(part.inline_data, 'data', None):
                        inline = part.inline_data
                        ext = mimetypes.guess_extension(inline.mime_type or "") or ""
                        
                        if not ext or ext.lower() not in (".wav", ".mp3", ".ogg", ".flac"):
                            wav_bytes = convert_to_wav(inline.data, inline.mime_type)
                            filename = f"{out_path_base}_{file_index}.wav"
                            save_binary_file(filename, wav_bytes)
                        else:
                            filename = f"{out_path_base}_{file_index}{ext}"
                            save_binary_file(filename, inline.data)
                        
                        saved_paths.append(filename)
                        file_index += 1
                
                if not saved_paths:
                    wx.CallAfter(wx.MessageBox, _("No inline audio data returned by model."), _("Error"), wx.OK | wx.ICON_ERROR)
                    return None
                
                if len(saved_paths) > 1 and all(p.lower().endswith(".wav") for p in saved_paths):
                    out_all = f"{out_path_base}_combined.wav"
                    try:
                        merge_wav_files(saved_paths, out_all)
                        return out_all
                    except Exception as e:
                        log.error(f"Failed to merge WAV parts: {e}", exc_info=True)
                        return saved_paths[0]
                return saved_paths[0]
            
            except Exception as e:
                log.error(f"Error streaming/generating audio: {e}", exc_info=True)
                wx.CallAfter(wx.MessageBox, _("Failed to generate speech: {error}").format(error=str(e)), _("Error"), wx.OK | wx.ICON_ERROR)
                return None

        def on_play(self, evt: wx.Event) -> None:
            if not self.last_audio_path or not os.path.exists(self.last_audio_path): return
            safe_startfile(self.last_audio_path)

        def on_save(self, evt: wx.Event) -> None:
            if not self.last_audio_path or not os.path.exists(self.last_audio_path): return
            with wx.FileDialog(self, _("Save Audio File"), wildcard="WAV files (*.wav)|*.wav|MP3 files (*.mp3)|*.mp3", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL: return
                dest = dlg.GetPath()
                try:
                    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                    with open(self.last_audio_path, "rb") as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                    wx.CallAfter(wx.MessageBox, _("Audio saved to {path}").format(path=dest), _("Success"), wx.OK | wx.ICON_INFORMATION)
                except Exception as e:
                    wx.CallAfter(wx.MessageBox, _("Failed to save audio: {error}").format(error=str(e)), _("Error"), wx.OK | wx.ICON_ERROR)

        def _play_sample_for_voice(self, voice_name: str) -> None:
            if not voice_name: return
            url = f"{VOICE_SAMPLE_BASE}/{voice_name}.wav"
            threading.Thread(target=self._download_and_play_sample, args=(url,), daemon=True).start()

        def _download_and_play_sample(self, url: str) -> None:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200 or not resp.content: 
                    ui.message(_("Sample not available"))
                    return
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(resp.content)
                    temp_path = tmp.name
                ui.message(_("Playing voice sample"))
                winsound.PlaySound(temp_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                threading.Timer(10.0, lambda: os.remove(temp_path) if os.path.exists(temp_path) else None).start()
            except Exception as e:
                log.error(f"Failed to play sample: {e}", exc_info=True)
                ui.message(_("Failed to play sample"))

        def load_voices(self) -> None:
            try:
                log.info("Skipping API call for voices. Using fallback voices.")
                voices = [{"name": v, "label": v, "meta": {}} for v in FALLBACK_VOICES]
                def update_ui() -> None:
                    try:
                        self.voices = voices
                        voice_labels = [v["label"] for v in voices]
                        for choice_ctrl in (self.voice_choice_single, self.voice_choice_multi1, self.voice_choice_multi2):
                            choice_ctrl.Clear()
                            choice_ctrl.AppendItems(voice_labels)
                        if voices:
                            self.voice_choice_single.SetSelection(0)
                            self.voice_choice_multi1.SetSelection(0)
                        if len(voices) > 1:
                            self.voice_choice_multi2.SetSelection(1)
                    except Exception as e:
                        log.error(f"Failed to update voice UI: {e}", exc_info=True)
                wx.CallAfter(update_ui)
            except Exception as e:
                log.error(f"Unexpected error loading voices: {e}", exc_info=True)

    # Global Plugin Wiring
    class GlobalPlugin(globalPluginHandler.GlobalPlugin):
        def __init__(self) -> None:
            super().__init__()
            self.dialog = None  # Track active dialog instance
            if CONFIG_DOMAIN not in config.conf:
                config.conf[CONFIG_DOMAIN] = {"apiKey": ""}
            config.conf.spec[CONFIG_DOMAIN] = {"apiKey": "string(default='')"}
            
            if NativeSpeechSettingsPanel not in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
                gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(NativeSpeechSettingsPanel)
            
            toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
            self.menuItem = toolsMenu.Append(wx.ID_ANY, _("&Native Speech Generation"), _("Generate speech using Gemini TTS"))
            gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onShowDialog, self.menuItem)

        # Translators: A script to open the main dialog.
        @script(
            description=_("Open the Native Speech Generation dialog"),
            category=_("Native Speech Generation"),
            gesture="kb:NVDA+Control+Shift+G"
        )
        def script_openDialog(self, gesture: Any) -> None:
            self._openDialog()

        def onShowDialog(self, evt: wx.Event) -> None:
            wx.CallAfter(self._openDialog)

        def _openDialog(self) -> None:
            if self.dialog and self.dialog.IsShown():
                wx.CallAfter(
                    wx.MessageBox,
                    _("The Native Speech Generation add-on is already open. "
                      "Please close the dialog before opening it again."),
                    _("Add-on Already Running"),
                    wx.OK | wx.ICON_WARNING
                )
                return
            try:
                self.dialog = NativeSpeechDialog(gui.mainFrame)
                self.dialog.Bind(wx.EVT_CLOSE, self.onDialogClose)
                self.dialog.Show()
            except Exception as e:
                log.error(f"Error showing NativeSpeechDialog: {e}", exc_info=True)
                wx.CallAfter(
                    wx.MessageBox,
                    _("Failed to open Native Speech Generation dialog: {error}").format(error=str(e)),
                    _("Error"),
                    wx.OK | wx.ICON_ERROR
                )

        def onDialogClose(self, event: wx.Event) -> None:
            # Reset flag when dialog is closed
            self.dialog = None
            event.Skip()

        def terminate(self) -> None:
            if NativeSpeechSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
                gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(NativeSpeechSettingsPanel)
            try:
                gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self.menuItem)
            except Exception:
                pass
            super().terminate()
