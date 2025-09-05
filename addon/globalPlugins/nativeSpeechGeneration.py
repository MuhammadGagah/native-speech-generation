# -*- coding: utf-8 -*-
# ========== Standard Library Imports ==========
import io
import json
import mimetypes
import os
import struct
import sys
import tempfile
import threading
import time
import wave
from contextlib import contextmanager

# Windows-only sound & launch helpers
import winsound  # Non-blocking async play for WAV samples on Windows

# ========== Third-party Imports ==========
# Deferred import via temp_sys_path for google-genai (shipped in add-on lib/)
import requests

# ========== NVDA / wx Imports ==========
import wx
import webbrowser
import globalPluginHandler
import gui
from gui.settingsDialogs import SettingsPanel
import addonHandler
import config
from scriptHandler import script
from logHandler import log
import ui

# Enable localization
addonHandler.initTranslation()

# ========== Constants & Defaults ==========
CONFIG_DOMAIN = "NativeSpeechGeneration"
DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
SECOND_MODEL = "gemini-2.5-pro-preview-tts"

# Public sample base (used by AI Studio voice samples)
VOICE_SAMPLE_BASE = "https://www.gstatic.com/aistudio/voices/samples"

# Fallback voice list if API retrieval isn't available (unchanged)
FALLBACK_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
]

# Cache path & TTL (kept; currently unused as we skip remote voice fetch)
addon_dir = os.path.dirname(__file__)
lib_dir = os.path.join(addon_dir, 'lib')
CACHE_FILE = os.path.join(addon_dir, "voices_cache.json")
CACHE_TTL = 24 * 60 * 60  # 24 hours

# ========== Scoped sys.path Injection ==========
@contextmanager
def temp_sys_path(path: str):
    """
    Temporarily inject a directory to sys.path for controlled imports,
    then reliably remove it to avoid polluting import graph.
    """
    if path in sys.path:
        # Already present, nothing to add or later remove
        yield
        return
    sys.path.insert(0, path)
    try:
        yield
    finally:
        # Remove only if still present (defensive)
        try:
            sys.path.remove(path)
        except ValueError:
            pass

# ========== Conditional google-genai Import ==========
with temp_sys_path(lib_dir):
    try:
        from google import genai
        from google.genai import types
        GENAI_AVAILABLE = True
        log.info("google-genai loaded successfully from add-on lib.")
    except Exception as _e:
        genai = None
        types = None
        GENAI_AVAILABLE = False
        log.warning("google-genai not available; set GENAI_AVAILABLE=False")

# ========== Small Cache Helpers (kept; ready for future use) ==========
def _save_cache(data):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"ts": int(time.time()), "data": data}, f)
    except Exception as e:
        log.error(f"Failed saving voices cache: {e}")

def _load_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            j = json.load(f)
        ts = j.get('ts', 0)
        if int(time.time()) - ts > CACHE_TTL:
            return None
        return j.get('data')
    except Exception as e:
        log.error(f"Failed loading voices cache: {e}")
        return None

# ========== Audio Helpers ==========
def parse_audio_mime_type(mime_type: str):
    """
    Parse minimal audio MIME metadata, mainly rate and bit depth.
    Example: "audio/L16; rate=24000" -> 16-bit, 24000 Hz
    Defaults: 16-bit, 24000 Hz.
    """
    bits_per_sample = 16
    rate = 24000
    if not mime_type:
        return {"bits_per_sample": bits_per_sample, "rate": rate}
    parts = [p.strip() for p in mime_type.split(";")]
    for p in parts:
        if p.lower().startswith("rate="):
            try:
                rate = int(p.split("=", 1)[1])
            except Exception:
                pass
        # Some providers use audio/L16, audio/L24 to indicate depth
        if "L" in p and p.lower().startswith("audio/l"):
            try:
                bits_per_sample = int(p.split("L", 1)[1])
            except Exception:
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """
    Convert raw linear PCM data from inline chunks (e.g., audio/L16;rate=24000) to WAV bytes.
    If the MIME indicates it's already WAV, return bytes as-is.
    """
    if mime_type and "wav" in mime_type.lower():
        return audio_data

    params = parse_audio_mime_type(mime_type)
    bits_per_sample = params.get("bits_per_sample", 16) or 16
    sample_rate = params.get("rate", 24000) or 24000
    num_channels = 1  # inline data is typically mono for TTS streaming
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    # Build minimal PCM WAV header
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16,
        1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample,
        b"data", data_size
    )
    return header + audio_data

def merge_wav_files(input_paths, output_path):
    """
    Concatenate multiple PCM WAV files that share identical audio parameters.
    This is needed because the streaming may produce multiple WAV chunks.
    """
    if not input_paths:
        raise ValueError("No input WAV files to merge.")

    # Read params from first file
    with wave.open(input_paths[0], 'rb') as w0:
        params = w0.getparams()
        frames = [w0.readframes(w0.getnframes())]

    # Validate and collect frames
    for p in input_paths[1:]:
        with wave.open(p, 'rb') as wi:
            if wi.getparams() != params:
                raise ValueError("WAV files have different parameters; cannot merge safely.")
            frames.append(wi.readframes(wi.getnframes()))

    # Write combined file
    with wave.open(output_path, 'wb') as wo:
        wo.setparams(params)
        for fr in frames:
            wo.writeframes(fr)
    log.info(f"Merged {len(input_paths)} WAV files -> {output_path}")

def save_binary_file(file_name, data):
    """
    Persist bytes to disk with logging. Ensures directory exists.
    """
    os.makedirs(os.path.dirname(file_name) or ".", exist_ok=True)
    with open(file_name, "wb") as f:
        f.write(data)
    log.info(f"Saved audio file: {file_name}")

def safe_startfile(path):
    """
    Safely attempt to open a file with the associated application on Windows.
    """
    try:
        os.startfile(path)
    except Exception as e:
        log.error(f"Failed to open file: {e}", exc_info=True)
        wx.CallAfter(wx.MessageBox, _("Audio generated, but failed to play automatically: {error}").format(error=e),
                     _("Info"), wx.OK | wx.ICON_INFORMATION)

# ========== Settings Panel ==========
class NativeSpeechSettingsPanel(SettingsPanel):
    title = _("Native Speech Generation")

    def makeSettings(self, settingsSizer):
        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        self.apiKeyCtrl = sHelper.addLabeledControl(_("&GEMINI API Key:"), wx.TextCtrl)
        try:
            self.apiKeyCtrl.SetValue(config.conf[CONFIG_DOMAIN]["apiKey"])
        except Exception:
            self.apiKeyCtrl.SetValue("")
        self.getKeyBtn = sHelper.addItem(wx.Button(self, label=_("&How to get API Key...")))
        self.getKeyBtn.Bind(wx.EVT_BUTTON, self.onGetKey)

    def onGetKey(self, evt):
        # Open API key page in default browser
        webbrowser.open("https://aistudio.google.com/apikey")

    def onSave(self):
        # Persist API key in NVDA config
        config.conf[CONFIG_DOMAIN]["apiKey"] = self.apiKeyCtrl.GetValue()

# ========== Main Dialog ==========
class NativeSpeechDialog(wx.Dialog):
    """
    Main UI dialog for generating speech with Gemini TTS (single or multi-speaker).
    """
    def __init__(self, parent):
        super().__init__(parent, title=_("Native Speech Generation (Gemini TTS)"))

        # Config & runtime state
        try:
            self.api_key = config.conf[CONFIG_DOMAIN]["apiKey"]
        except Exception:
            self.api_key = ""

        self.last_audio_path = None
        self.model = DEFAULT_MODEL
        self.mode_multi = False
        self.voices = []
        self.selected_voice_idx = 0
        self.selected_voice_idx_2 = 0
        self.is_generating = False

        # Build UI and kick off voices loading
        self._build_ui()
        threading.Thread(target=self.load_voices, daemon=True).start()
        self.text_ctrl.SetFocus()

    # ---------- UI Builders ----------
    def _build_ui(self):
        """
        Build controls and layout. Keep structure same but refactor for clarity.
        """
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Text input area
        text_label = wx.StaticText(self, label=_("&Type text to convert here:"))
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(520, 160))
        main_sizer.Add(text_label, flag=wx.ALL, border=6)
        main_sizer.Add(self.text_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)

        # Optional style instructions
        style_label = wx.StaticText(self, label=_("&Style instructions (optional):"))
        self.style_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(520, 60))
        main_sizer.Add(style_label, flag=wx.ALL, border=6)
        main_sizer.Add(self.style_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)

        # Model selection + mode selection
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

        # Advanced settings (Temperature)
        self.settings_checkbox = wx.CheckBox(self, label=_("Advanced Settings (&Temperature)"))
        self.settings_checkbox.SetValue(False)
        main_sizer.Add(self.settings_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)

        self.settings_panel = wx.Panel(self)
        main_sizer.Add(self.settings_panel, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
        pane_sizer = wx.BoxSizer(wx.VERTICAL)

        temp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        temp_label = wx.StaticText(self.settings_panel, label=_("Temperature:"))
        self.temp_slider = wx.Slider(self.settings_panel, value=10, minValue=0, maxValue=20, style=wx.SL_HORIZONTAL)
        self.temp_value_label = wx.StaticText(self.settings_panel, label=self._temp_to_label(10))
        # Keep label synced with slider changes
        self.temp_slider.Bind(wx.EVT_SLIDER, self.on_temp_change)
        temp_sizer.Add(temp_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5)
        temp_sizer.Add(self.temp_slider, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        temp_sizer.Add(self.temp_value_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5)
        pane_sizer.Add(temp_sizer, flag=wx.EXPAND | wx.ALL, border=5)

        self.settings_panel.SetSizer(pane_sizer)
        self.settings_panel.Hide()
        self.Bind(wx.EVT_CHECKBOX, self.on_toggle_settings, self.settings_checkbox)

        # Voice panels (single vs multi)
        self.voice_panel_single = self._build_voice_panel_single()
        self.voice_panel_multi = self._build_voice_panel_multi()
        main_sizer.Add(self.voice_panel_single, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(self.voice_panel_multi, flag=wx.EXPAND | wx.ALL, border=5)
        self.voice_panel_multi.Hide()

        # Buttons (Generate / Play / Save)
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

        # Footer: settings & voices page
        footer_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.get_key_btn = wx.Button(self, label=_("API Key Settings"))
        self.get_key_btn.Bind(wx.EVT_BUTTON, self.on_settings)
        self.view_voices_btn = wx.Button(self, label=_("View voices in AI Studio"))
        self.view_voices_btn.Bind(wx.EVT_BUTTON, self.on_open_ai_studio)
        footer_sizer.Add(self.get_key_btn, flag=wx.ALL, border=6)
        footer_sizer.Add(self.view_voices_btn, flag=wx.ALL, border=6)
        main_sizer.Add(footer_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        # Close
        self.close_btn = wx.Button(self, wx.ID_CANCEL, _("&Close"))
        main_sizer.Add(self.close_btn, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        self.SetSizerAndFit(main_sizer)
        self.CenterOnParent()
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def _build_voice_panel_single(self):
        """
        Build the single-speaker voice selector panel.
        """
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(panel, label=_("Select &Voice:"))
        self.voice_choice_single = wx.Choice(panel, choices=[_("Loading voices...")])
        self.voice_choice_single.SetSelection(0)
        self.voice_choice_single.Bind(wx.EVT_CHOICE, self.on_voice_change)
        # Space to play sample on keypress (Space)
        self.voice_choice_single.Bind(wx.EVT_CHAR_HOOK, self.on_voice_keypress_generic)
        sizer.Add(label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        sizer.Add(self.voice_choice_single, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        panel.SetSizer(sizer)
        return panel

    def _build_voice_panel_multi(self):
        """
        Build the two-speaker voice selector panel.
        """
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
        spk2_sizer.Add(spk2_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        spk2_sizer.Add(self.spk2_name_ctrl, flag=wx.RIGHT, border=10)
        spk2_sizer.Add(voice2_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        spk2_sizer.Add(self.voice_choice_multi2, proportion=1, flag=wx.EXPAND)
        sizer.Add(spk2_sizer, flag=wx.EXPAND | wx.ALL, border=6)

        panel.SetSizer(sizer)
        return panel

    # ---------- Window / General ----------
    def on_close(self, evt):
        self.Destroy()

    # ---------- Advanced Settings ----------
    def _temp_to_label(self, val_int: int) -> str:
        return f"{val_int / 10.0:.1f}"

    def on_temp_change(self, evt):
        new_value_int = evt.GetEventObject().GetValue()
        new_label_str = self._temp_to_label(new_value_int)
        self.temp_value_label.SetLabel(new_label_str)

    def on_toggle_settings(self, evt):
        is_shown = self.settings_checkbox.IsChecked()
        self.settings_panel.Show(is_shown)
        self.GetSizer().Layout()
        self.Fit()

    # ---------- Model / Mode ----------
    def on_model_change(self, evt):
        sel = self.model_choice.GetSelection()
        self.model = DEFAULT_MODEL if sel == 0 else SECOND_MODEL

    def on_mode_change(self, evt):
        self.mode_multi = self.mode_multi_rb.GetValue()
        self.voice_panel_single.Show(not self.mode_multi)
        self.voice_panel_multi.Show(self.mode_multi)
        self.GetSizer().Layout()
        self.Fit()

    # ---------- Voice Selection ----------
    def on_voice_change(self, evt):
        self.selected_voice_idx = evt.GetEventObject().GetSelection()

    def on_voice_change_2(self, evt):
        self.selected_voice_idx_2 = self.voice_choice_multi2.GetSelection()

    def on_voice_keypress_generic(self, evt):
        """
        Handle Space to preview the currently highlighted voice (works for all three Choice controls).
        """
        key = evt.GetKeyCode()
        if key == wx.WXK_SPACE:
            ctrl = evt.GetEventObject()
            idx = ctrl.GetSelection()
            voice_name = self._get_selected_voice_name(ctrl, idx)
            self._play_sample_for_voice(voice_name)
        else:
            evt.Skip()

    def _get_selected_voice_name(self, choice_ctrl, idx: int) -> str:
        """
        Safely resolve a voice name from self.voices by index with fallbacks.
        """
        try:
            if idx is None or idx == wx.NOT_FOUND or not self.voices:
                log.warning("Attempting to get voice with invalid index or empty voices list.")
                return self.voices[0]['name'] if self.voices else "Zephyr"
            voice_data = self.voices[idx]
            # Allow for dict or plain string
            if isinstance(voice_data, dict) and 'name' in voice_data:
                return voice_data['name']
            return str(voice_data)
        except IndexError:
            log.warning(f"Voice index {idx} out of range.")
            return self.voices[0]['name'] if self.voices else "Zephyr"
        except Exception as e:
            log.error(f"Failed to get selected voice name: {e}", exc_info=True)
            return "Zephyr"

    # ---------- Settings Shortcuts ----------
    def on_settings(self, evt):
        """
        Close dialog and open Settings panel focused on our section.
        """
        self.Destroy()
        wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, NativeSpeechSettingsPanel)

    def on_open_ai_studio(self, evt):
        webbrowser.open("https://aistudio.google.com/generate-speech")

    # ---------- Generate / Stream / Save ----------
    def on_generate(self, evt):
        if self.is_generating:
            return

        if not GENAI_AVAILABLE:
            wx.MessageBox(_("google-genai library not installed. Install with: pip install google-genai"),
                          _("Error"), wx.OK | wx.ICON_ERROR)
            return

        if not self.api_key:
            wx.MessageBox(_("No GEMINI_API_KEY configured. Set it in NVDA settings under NativeSpeechGeneration."),
                          _("Error"), wx.OK | wx.ICON_ERROR)
            return

        text = self.text_ctrl.GetValue().strip()
        if not text:
            wx.MessageBox(_("Please enter text to generate."), _("Error"), wx.OK | wx.ICON_ERROR)
            return

        # Lock UI
        self.is_generating = True
        self.generate_btn.SetLabel(_("Generating..."))
        self.play_btn.Enable(False)
        self.save_btn.Enable(False)

        t = threading.Thread(target=self._generate_thread, args=(text,), daemon=True)
        t.start()

    def _generate_thread(self, text: str):
        """
        Worker thread: build request, stream audio, and save output file.
        """
        ui.message(_("Generating speech, please wait..."))

        # Create client inside thread to avoid cross-thread state issues
        try:
            with temp_sys_path(lib_dir):
                client = genai.Client(api_key=self.api_key)
        except Exception as e:
            log.error(f"Failed init genai client: {e}", exc_info=True)
            wx.CallAfter(wx.MessageBox, _("Failed to initialize Google GenAI client: {error}").format(error=str(e)),
                         _("Error"), wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self._restore_generate_button)
            return

        def handle_success(saved_path):
            """
            Update UI after successful generation and autoplay output.
            """
            if not saved_path:
                ui.message(_("Failed to generate audio."))
                return
            ui.message(_("Generation complete."))
            self.last_audio_path = saved_path
            log.info(f"Speech generation successful. Audio at: {self.last_audio_path}")
            safe_startfile(self.last_audio_path)
            wx.CallAfter(self.play_btn.Enable, True)
            wx.CallAfter(self.save_btn.Enable, True)

        try:
            # Temperature & optional style prompt
            temp = self.temp_slider.GetValue() / 10.0
            style_instructions = self.style_ctrl.GetValue().strip()
            final_text = f"{style_instructions}\n{text}" if style_instructions else text

            contents = [types.Content(role="user", parts=[types.Part.from_text(text=final_text)])]

            # Build speech config (single vs multi)
            if not self.mode_multi:
                log.info("Generating in Single-speaker mode.")
                voice_name = self._get_selected_voice_name(self.voice_choice_single, self.selected_voice_idx)
                if not voice_name:
                    wx.CallAfter(wx.MessageBox, _("Please select a voice for Speaker 1."),
                                 _("Error"), wx.OK | wx.ICON_ERROR)
                    return
                speech_config = types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                    )
                )
            else:
                log.info("Generating in Multi-speaker mode.")
                speaker1_name = self.spk1_name_ctrl.GetValue().strip() or "Speaker1"
                speaker2_name = self.spk2_name_ctrl.GetValue().strip() or "Speaker2"
                voice1 = self._get_selected_voice_name(self.voice_choice_multi1, self.selected_voice_idx)
                voice2 = self._get_selected_voice_name(self.voice_choice_multi2, self.selected_voice_idx_2)
                if not voice1 or not voice2:
                    wx.CallAfter(wx.MessageBox, _("Please select voices for both speakers."),
                                 _("Error"), wx.OK | wx.ICON_ERROR)
                    return
                speech_config = types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker=speaker1_name,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice1))
                            ),
                            types.SpeakerVoiceConfig(
                                speaker=speaker2_name,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice2))
                            ),
                        ]
                    )
                )

            generate_config = types.GenerateContentConfig(
                temperature=temp,
                response_modalities=["audio"],
                speech_config=speech_config
            )

            out_path_base = os.path.join(addon_dir, "last_audio_generated")
            saved_path = self._stream_and_save_audio(client, self.model, contents, generate_config, out_path_base)
            handle_success(saved_path)

        except Exception as e:
            ui.message(_("An error occurred during generation."))
            log.error(f"Unexpected error in generate_thread: {e}", exc_info=True)
            wx.CallAfter(wx.MessageBox, _("An unexpected error occurred: {error}").format(error=str(e)),
                         _("Error"), wx.OK | wx.ICON_ERROR)
        finally:
            wx.CallAfter(self._restore_generate_button)

    def _restore_generate_button(self):
        """
        Restore Generate button label and internal state; called on UI thread.
        """
        self.generate_btn.SetLabel(_("&Generate Speech"))
        self.is_generating = False

    def _stream_and_save_audio(self, client, model, contents, config_obj, out_path_base):
        """
        Consume streaming responses from genai, extract inline audio bytes,
        and save them into one or more audio files. When multiple WAV chunks
        are produced, attempt to merge into a single WAV.

        Returns a single file path to be used as 'last_audio_path'.
        """
        file_index = 0
        saved_paths = []
        try:
            log.info(f"Streaming audio from model: {model}...")
            stream = client.models.generate_content_stream(model=model, contents=contents, config=config_obj)

            for chunk in stream:
                log.debug("Received a chunk from the stream.")

                if not getattr(chunk, "candidates", None):
                    log.debug("Chunk has no candidates. Skipping.")
                    continue

                candidate = chunk.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    log.debug("Candidate has no content or parts. Skipping.")
                    continue

                part = candidate.content.parts[0]
                # Inline audio bytes come via inline_data for audio modality
                if part.inline_data and getattr(part.inline_data, 'data', None):
                    log.info("Found inline_data with audio bytes.")
                    inline = part.inline_data
                    data_buffer = inline.data
                    # Try to use extension from MIME if available, else default to WAV conversion
                    ext = mimetypes.guess_extension(inline.mime_type or "") or ""
                    if not ext or ext.lower() not in (".wav", ".mp3", ".ogg", ".flac"):
                        # Unknown/RAW linear PCM -> convert to WAV
                        wav_bytes = convert_to_wav(inline.data, inline.mime_type)
                        filename = f"{out_path_base}_{file_index}.wav"
                        save_binary_file(filename, wav_bytes)
                    else:
                        filename = f"{out_path_base}_{file_index}{ext}"
                        save_binary_file(filename, data_buffer)
                    saved_paths.append(filename)
                    file_index += 1
                else:
                    # Optional: log textual chunks if present during audio streaming
                    if getattr(chunk, "text", None):
                        log.debug(f"Text chunk: {chunk.text}")

            if not saved_paths:
                wx.CallAfter(wx.MessageBox, _("No inline audio data returned by model."),
                             _("Error"), wx.OK | wx.ICON_ERROR)
                return None

            # If there are multiple WAV parts, try merging them for convenience.
            if len(saved_paths) > 1 and all(p.lower().endswith(".wav") for p in saved_paths):
                out_all = f"{out_path_base}_combined.wav"
                try:
                    merge_wav_files(saved_paths, out_all)
                    return out_all
                except Exception as e:
                    log.error(f"Failed to merge WAV parts: {e}", exc_info=True)
                    # Fallback to the first chunk if merge fails.
                    return saved_paths[0]

            # Otherwise return the first produced file (common case)
            return saved_paths[0]

        except Exception as e:
            log.error(f"Error streaming/generating audio: {e}", exc_info=True)
            wx.CallAfter(wx.MessageBox, _("Failed to generate speech: {error}").format(error=str(e)),
                         _("Error"), wx.OK | wx.ICON_ERROR)
            return None

    # ---------- Play / Save ----------
    def on_play(self, evt):
        if not self.last_audio_path or not os.path.exists(self.last_audio_path):
            wx.MessageBox(_("No audio available to play."), _("Error"), wx.OK | wx.ICON_ERROR)
            return
        safe_startfile(self.last_audio_path)

    def on_save(self, evt):
        if not self.last_audio_path or not os.path.exists(self.last_audio_path):
            wx.MessageBox(_("No generated audio to save."), _("Error"), wx.OK | wx.ICON_ERROR)
            return

        # Offer both WAV and MP3 as in the original behavior.
        with wx.FileDialog(
            self,
            _("Save Audio File"),
            wildcard="WAV files (*.wav)|*.wav|MP3 files (*.mp3)|*.mp3",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            dest = dlg.GetPath()
            try:
                os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                with open(self.last_audio_path, "rb") as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                wx.MessageBox(_("Audio saved to {path}").format(path=dest),
                              _("Success"), wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(_("Failed to save audio: {error}").format(error=str(e)),
                              _("Error"), wx.OK | wx.ICON_ERROR)

    # ---------- Voice Sample Preview ----------
    def _play_sample_for_voice(self, voice_name: str):
        """
        Download and play a short sample for the selected voice (non-blocking).
        """
        if not voice_name:
            ui.message(_("No voice selected"))
            return
        url = f"{VOICE_SAMPLE_BASE}/{voice_name}.wav"
        threading.Thread(target=self._download_and_play_sample, args=(url,), daemon=True).start()

    def _download_and_play_sample(self, url: str):
        """
        Retrieve WAV sample and play asynchronously via winsound.
        """
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
        except Exception as e:
            log.error(f"Failed to play sample: {e}", exc_info=True)
            ui.message(_("Failed to play sample"))

    # ---------- Voice Loading ----------
    def load_voices(self):
        """
        Currently we skip remote API and use a safe fallback list.
        This preserves feature parity and avoids runtime dependency issues.
        """
        try:
            log.info("Skipping API call for voices. Using fallback voices.")
            voices = [{"name": v, "label": v, "meta": {}} for v in FALLBACK_VOICES]

            def update_ui():
                try:
                    self.voices = voices
                    voice_labels = [v["label"] for v in voices]
                    # Populate all three Choice controls consistently
                    for choice_ctrl in (self.voice_choice_single, self.voice_choice_multi1, self.voice_choice_multi2):
                        choice_ctrl.Clear()
                        choice_ctrl.AppendItems(voice_labels)
                    # Default selections
                    if voices:
                        self.voice_choice_single.SetSelection(0)
                        self.voice_choice_multi1.SetSelection(0)
                    if len(voices) > 1:
                        self.voice_choice_multi2.SetSelection(1)
                    log.info(f"Loaded {len(voices)} voices into all controls (fallback mode).")
                except Exception as e:
                    log.error(f"Failed to update voice UI: {e}", exc_info=True)

            wx.CallAfter(update_ui)

        except Exception as e:
            # Fixed indentation: this except belongs to the outer try.
            log.error(f"Unexpected error loading voices: {e}", exc_info=True)

# ========== Global Plugin Wiring ==========
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """
    Registers settings panel, menu item, and gesture to open the dialog.
    """
    def __init__(self):
        super().__init__()
        # Ensure config domain exists
        if CONFIG_DOMAIN not in config.conf:
            config.conf[CONFIG_DOMAIN] = {"apiKey": ""}
        config.conf.spec[CONFIG_DOMAIN] = {"apiKey": "string(default=)"}

        # Ensure settings panel is registered once
        if NativeSpeechSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
            gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(NativeSpeechSettingsPanel)
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(NativeSpeechSettingsPanel)

        # Add to Tools menu
        toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
        self.menuItem = toolsMenu.Append(wx.ID_ANY, _("&Native Speech Generation"), _("Generate speech using Gemini TTS"))
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onShowDialog, self.menuItem)

    @script(
        description=_("Open the Native Speech Generation dialog"),
        category=_("Native Speech Generation"),
        gesture="kb:NVDA+Control+Shift+G"
    )
    def script_openDialog(self, gesture):
        wx.CallAfter(self.showDialog)

    def onShowDialog(self, evt):
        wx.CallAfter(self.showDialog)

    def showDialog(self):
        try:
            dlg = NativeSpeechDialog(gui.mainFrame)
            # Keep reading API key at open time in case user has changed it
            try:
                dlg.api_key = config.conf[CONFIG_DOMAIN]["apiKey"]
            except Exception:
                dlg.api_key = ""
            dlg.ShowModal()
        except Exception as e:
            log.error(f"Error showing NativeSpeechDialog: {e}", exc_info=True)
            wx.MessageBox(
                _("Failed to open Native Speech Generation dialog: {error}").format(error=str(e)),
                _("Error"),
                wx.OK | wx.ICON_ERROR
            )

    def terminate(self):
        # Cleanup settings panel registration
        if NativeSpeechSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
            gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(NativeSpeechSettingsPanel)
        # Remove menu item if present
        try:
            gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self.menuItem)
        except Exception:
            pass
        super().terminate()
