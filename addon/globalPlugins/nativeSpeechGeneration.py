import os
import sys
import json
import threading
import time
from contextlib import contextmanager

# Ensure lib path is available only during imports to avoid namespace conflicts
addon_dir = os.path.dirname(__file__)
lib_dir = os.path.join(addon_dir, 'lib')

@contextmanager
def temp_sys_path(path):
    if path in sys.path:
        yield
        return
    sys.path.insert(0, path)
    try:
        yield
    finally:
        try:
            sys.path.remove(path)
        except ValueError:
            pass

# Import external dependencies inside temporary path
with temp_sys_path(lib_dir):
    try:
        from google import genai
        from google.genai import types
        GENAI_AVAILABLE = True
    except Exception:
        genai = None
        types = None
        GENAI_AVAILABLE = False

# NVDA / UI imports
import io
import mimetypes
import struct
import wave
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

addonHandler.initTranslation()
CONFIG_DOMAIN = "NativeSpeechGeneration"
DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
SECOND_MODEL = "gemini-2.5-pro-preview-tts"

FALLBACK_VOICES = [
    "Zephyr","Puck","Charon","Kore","Fenrir","Leda","Orus","Aoede",
    "Callirrhoe","Autonoe","Enceladus","Iapetus","Umbriel","Algieba",
    "Despina","Erinome","Algenib","Rasalgethi","Laomedeia","Achernar",
    "Alnilam","Schedar","Gacrux","Pulcherrima","Achird","Zubenelgenubi",
    "Vindemiatrix","Sadachbia","Sadaltager","Sulafat"
]

CACHE_FILE = os.path.join(addon_dir, "voices_cache.json")
CACHE_TTL = 24 * 60 * 60  # 24 hours

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

# audio helpers
def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)
    log.info(f"Saved audio file: {file_name}")

def parse_audio_mime_type(mime_type: str):
    bits_per_sample = 16
    rate = 24000
    if not mime_type:
        return {"bits_per_sample": bits_per_sample, "rate": rate}
    parts = mime_type.split(";")
    for p in parts:
        p = p.strip()
        if p.lower().startswith("rate="):
            try:
                rate = int(p.split("=",1)[1])
            except Exception:
                pass
        if "L" in p and p.lower().startswith("audio/l"):
            try:
                bits_per_sample = int(p.split("L",1)[1])
            except Exception:
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
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
        webbrowser.open("https://aistudio.google.com/apikey")

    def onSave(self):
        config.conf[CONFIG_DOMAIN]["apiKey"] = self.apiKeyCtrl.GetValue()

class NativeSpeechDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=_("Native Speech Generation (Gemini TTS)"))
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
        self._build_ui()
        threading.Thread(target=self.load_voices, daemon=True).start()
        self.text_ctrl.SetFocus()
    def on_toggle_settings(self, evt):
        is_shown = self.settings_checkbox.IsChecked()
        self.settings_panel.Show(is_shown)
        self.GetSizer().Layout()
        self.Fit()
    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        text_label = wx.StaticText(self, label=_("&Type text to convert here:"))
        self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(520,160))
        main_sizer.Add(text_label, flag=wx.ALL, border=6)
        main_sizer.Add(self.text_ctrl, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=6)

        style_label = wx.StaticText(self, label=_("&Style instructions (optional):"))
        self.style_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(520,60))
        main_sizer.Add(style_label, flag=wx.ALL, border=6)
        main_sizer.Add(self.style_ctrl, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=6)

        model_sizer = wx.BoxSizer(wx.HORIZONTAL)
        model_label = wx.StaticText(self, label=_("Select &Model:"))
        self.model_choice = wx.Choice(self, choices=[_("Flash (Standard Quality)"), _("Pro (High Quality)")])
        self.model_choice.SetSelection(0)
        self.model_choice.Bind(wx.EVT_CHOICE, self.on_model_change)
        model_sizer.Add(model_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=6)
        model_sizer.Add(self.model_choice, flag=wx.ALL, border=6)
        self.mode_single_rb = wx.RadioButton(self, label=_("Single-speaker"), style=wx.RB_GROUP)
        self.mode_multi_rb  = wx.RadioButton(self, label=_("Multi-speaker (2)"))
        self.mode_single_rb.SetValue(True)
        self.mode_single_rb.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change)
        self.mode_multi_rb.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change)
        model_sizer.Add(self.mode_single_rb, flag=wx.ALL, border=6)
        model_sizer.Add(self.mode_multi_rb, flag=wx.ALL, border=6)
        main_sizer.Add(model_sizer, flag=wx.EXPAND)
        self.settings_checkbox = wx.CheckBox(self, label=_("Advanced Settings (&Temperature)"))
        self.settings_checkbox.SetValue(False)
        main_sizer.Add(self.settings_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)
        self.settings_panel = wx.Panel(self)
        main_sizer.Add(self.settings_panel, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=6)
        pane_sizer = wx.BoxSizer(wx.VERTICAL)
        
        temp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        temp_label = wx.StaticText(self.settings_panel, label=_("Temperature:"))
        self.temp_slider = wx.Slider(self.settings_panel, value=10, minValue=0, maxValue=20, style=wx.SL_HORIZONTAL)
        self.temp_slider.SetLabel(self._temp_to_label(10)) 
        self.temp_value_label = wx.StaticText(self.settings_panel, label=self._temp_to_label(10))
        
        temp_sizer.Add(temp_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
        temp_sizer.Add(self.temp_slider, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        temp_sizer.Add(self.temp_value_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
        self.temp_slider.Bind(wx.EVT_SLIDER, self.on_temp_change)
        
        pane_sizer.Add(temp_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        self.settings_panel.SetSizer(pane_sizer)
        self.settings_panel.Hide()
        self.Bind(wx.EVT_CHECKBOX, self.on_toggle_settings, self.settings_checkbox)
        self.voice_panel_single = wx.Panel(self)
        self.voice_panel_multi = wx.Panel(self)
        single_sizer = wx.BoxSizer(wx.HORIZONTAL)
        single_voice_label = wx.StaticText(self.voice_panel_single, label=_("Select &Voice:"))
        self.voice_choice_single = wx.Choice(self.voice_panel_single, choices=[_("Loading voices...")])
        self.voice_choice_single.SetSelection(0)
        self.voice_choice_single.Bind(wx.EVT_CHOICE, self.on_voice_change)
        
        single_sizer.Add(single_voice_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        single_sizer.Add(self.voice_choice_single, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        self.voice_panel_single.SetSizer(single_sizer)
        multi_sizer = wx.BoxSizer(wx.VERTICAL)
        # Speaker 1
        spk1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        spk1_label = wx.StaticText(self.voice_panel_multi, label=_("Speaker 1 Name:"))
        self.spk1_name_ctrl = wx.TextCtrl(self.voice_panel_multi, value="Speaker1", size=(100,-1))
        voice1_label = wx.StaticText(self.voice_panel_multi, label=_("Voice:"))
        self.voice_choice_multi1 = wx.Choice(self.voice_panel_multi, choices=[_("Loading voices...")])
        self.voice_choice_multi1.SetSelection(0)
        self.voice_choice_multi1.Bind(wx.EVT_CHOICE, self.on_voice_change)
        spk1_sizer.Add(spk1_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=5)
        spk1_sizer.Add(self.spk1_name_ctrl, flag=wx.RIGHT, border=10)
        spk1_sizer.Add(voice1_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=5)
        spk1_sizer.Add(self.voice_choice_multi1, proportion=1, flag=wx.EXPAND)
        multi_sizer.Add(spk1_sizer, flag=wx.EXPAND | wx.ALL, border=6)
        # Speaker 2
        spk2_sizer = wx.BoxSizer(wx.HORIZONTAL)
        spk2_label = wx.StaticText(self.voice_panel_multi, label=_("Speaker 2 Name:"))
        self.spk2_name_ctrl = wx.TextCtrl(self.voice_panel_multi, value="Speaker2", size=(100,-1))
        voice2_label = wx.StaticText(self.voice_panel_multi, label=_("Voice:"))
        self.voice_choice_multi2 = wx.Choice(self.voice_panel_multi, choices=[])
        self.voice_choice_multi2.Bind(wx.EVT_CHOICE, self.on_voice_change_2)
        spk2_sizer.Add(spk2_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=5)
        spk2_sizer.Add(self.spk2_name_ctrl, flag=wx.RIGHT, border=10)
        spk2_sizer.Add(voice2_label, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=5)
        spk2_sizer.Add(self.voice_choice_multi2, proportion=1, flag=wx.EXPAND)
        multi_sizer.Add(spk2_sizer, flag=wx.EXPAND | wx.ALL, border=6)
        self.voice_panel_multi.SetSizer(multi_sizer)
        main_sizer.Add(self.voice_panel_single, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(self.voice_panel_multi, flag=wx.EXPAND | wx.ALL, border=5)
        self.voice_panel_multi.Hide()
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

    def on_close(self, evt):
        self.Destroy()

    def _temp_to_label(self, val_int):
        return f"{val_int/10.0:.1f}"

    def on_temp_change(self, evt):
        new_value_int = evt.GetEventObject().GetValue()
        new_label_str = self._temp_to_label(new_value_int)
        self.temp_value_label.SetLabel(new_label_str)
        self.temp_slider.SetLabel(new_label_str)

    def on_model_change(self, evt):
        sel = self.model_choice.GetSelection()
        self.model = DEFAULT_MODEL if sel == 0 else SECOND_MODEL

    def on_mode_change(self, evt):
        self.mode_multi = self.mode_multi_rb.GetValue()
        self.voice_panel_single.Show(not self.mode_multi)
        self.voice_panel_multi.Show(self.mode_multi)
        self.GetSizer().Layout()
        self.Fit()

    def on_voice_change(self, evt):
        self.selected_voice_idx = evt.GetEventObject().GetSelection()

    def on_voice_change_2(self, evt):
        self.selected_voice_idx_2 = self.voice_choice_multi2.GetSelection()

    def on_settings(self, evt):
        self.Destroy() 
        wx.CallAfter(gui.mainFrame._popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, NativeSpeechSettingsPanel)

    def on_open_ai_studio(self, evt):
        webbrowser.open("https://aistudio.google.com/generate-speech")

    def on_generate(self, evt):
        if self.is_generating:
            return
        if not GENAI_AVAILABLE:
            wx.MessageBox(_("google-genai library not installed. Install with: pip install google-genai"), _("Error"), wx.OK|wx.ICON_ERROR)
            return
        if not self.api_key:
            wx.MessageBox(_("No GEMINI_API_KEY configured. Set it in NVDA settings under NativeSpeechGeneration."), _("Error"), wx.OK|wx.ICON_ERROR)
            return
        text = self.text_ctrl.GetValue().strip()
        if not text:
            wx.MessageBox(_("Please enter text to generate."), _("Error"), wx.OK|wx.ICON_ERROR)
            return
        self.is_generating = True
        self.generate_btn.SetLabel(_("Generating..."))
        self.play_btn.Enable(False)
        self.save_btn.Enable(False)
        t = threading.Thread(target=self._generate_thread, args=(text,), daemon=True)
        t.start()

    def _generate_thread(self, text):
        ui.message(_("Generating speech, please wait..."))
        try:
            with temp_sys_path(lib_dir):
                client = genai.Client(api_key=self.api_key)
        except Exception as e:
            log.error(f"Failed init genai client: {e}", exc_info=True)
            wx.CallAfter(wx.MessageBox, _("Failed to initialize Google GenAI client: {error}").format(error=str(e)), _("Error"), wx.OK|wx.ICON_ERROR)
            wx.CallAfter(self.generate_btn.Enable, True)
            return
        def handle_success(saved_path):
            if not saved_path:
                ui.message(_("Failed to generate audio."))
                return
            ui.message(_("Generation complete."))
            self.last_audio_path = saved_path
            log.info(f"Speech generation successful. Audio at: {self.last_audio_path}")
            
            try:
                log.info(f"Attempting to autoplay: {self.last_audio_path}")
                os.startfile(self.last_audio_path)
            except Exception as e:
                log.error(f"Failed to autoplay audio: {e}", exc_info=True)
                wx.CallAfter(wx.MessageBox, _("Audio generated, but failed to play automatically: {error}").format(error=e), _("Info"), wx.OK | wx.ICON_INFORMATION)

            wx.CallAfter(self.play_btn.Enable, True)
            wx.CallAfter(self.save_btn.Enable, True)

        try:
            temp = self.temp_slider.GetValue() / 10.0
            style_instructions = self.style_ctrl.GetValue().strip()
            
            final_text = text
            if style_instructions:
                final_text = f"{style_instructions}\n{text}"
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=final_text)])]
            speech_config = None
            if not self.mode_multi:
                log.info("Generating in Single-speaker mode.")
                voice_name = self._get_selected_voice_name(self.voice_choice_single, self.selected_voice_idx)
                if not voice_name:
                    wx.CallAfter(wx.MessageBox, _("Please select a voice for Speaker 1."), _("Error"), wx.OK | wx.ICON_ERROR)
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
                     wx.CallAfter(wx.MessageBox, _("Please select voices for both speakers."), _("Error"), wx.OK | wx.ICON_ERROR)
                     return
                speech_config = types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker=speaker1_name,
                                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice1))
                            ),
                            types.SpeakerVoiceConfig(
                                speaker=speaker2_name,
                                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice2))
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
            log.error(f"An unexpected error occurred in generate_thread: {e}", exc_info=True)
            wx.CallAfter(wx.MessageBox, _("An unexpected error occurred: {error}").format(error=str(e)), _("Error"), wx.OK | wx.ICON_ERROR)
        finally:
            def restore_ui():
                self.generate_btn.SetLabel(_("&Generate Speech"))                # Secara fisik kembalikan fokus ke tombol
                self.is_generating = False
            wx.CallAfter(restore_ui)

    def _get_selected_voice_name(self, choice_ctrl, idx):
        try:
            if idx is None or idx == wx.NOT_FOUND or not self.voices:
                log.warning("Attempted to get voice name with invalid index or empty voice list.")
                return self.voices[0]['name'] if self.voices else "Zephyr"

            voice_data = self.voices[idx]
            if isinstance(voice_data, dict) and 'name' in voice_data:
                return voice_data['name']
            else:
                log.warning(f"Voice data at index {idx} is not in expected format: {voice_data}")
                return str(voice_data)

        except IndexError:
            log.warning(f"voice index {idx} out of range.")
            return self.voices[0]['name'] if self.voices else "Zephyr"
        except Exception as e:
            log.error(f"Failed to get the name of the selected voice: {e}", exc_info=True)
            return "Zephyr"

    def _stream_and_save_audio(self, client, model, contents, config_obj, out_path_base):
        file_index = 0
        saved_paths = []
        try:
            log.info(f"Streaming audio from model: {model}...")
            stream = client.models.generate_content_stream(model=model, contents=contents, config=config_obj)
            for chunk in stream:
                log.debug(f"Received a chunk from the stream.")

                if not chunk.candidates:
                    log.debug("Chunk has no candidates. Skipping.")
                    continue
                
                candidate = chunk.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    log.debug("Candidate has no content or parts. Skipping.")
                    continue

                part = candidate.content.parts[0]
                if part.inline_data and getattr(part.inline_data, 'data', None):
                    log.info("Found inline_data with audio bytes!")
                    inline = part.inline_data
                    data_buffer = inline.data
                    file_extension = mimetypes.guess_extension(inline.mime_type) or ""
                    if not file_extension:
                        wav_bytes = convert_to_wav(inline.data, inline.mime_type)
                        filename = f"{out_path_base}_{file_index}.wav"
                        save_binary_file(filename, wav_bytes)
                    else:
                        filename = f"{out_path_base}_{file_index}{file_extension}"
                        save_binary_file(filename, data_buffer)
                    saved_paths.append(filename)
                    file_index += 1
                else:
                    log.debug(f"Chunk received, but part has no inline_data. Part content: {part}")
                    if getattr(chunk, "text", None):
                        log.debug(f"Text chunk: {chunk.text}")
            if not saved_paths:
                wx.CallAfter(wx.MessageBox, _("No inline audio data returned by model."), _("Error"), wx.OK|wx.ICON_ERROR)
                return None
            if len(saved_paths) > 1 and all(p.lower().endswith(".wav") for p in saved_paths):
                out_all = f"{out_path_base}_combined.wav"
                try:
                    merge_wav_files(saved_paths, out_all)
                    return out_all
                except Exception as e:
                    log.error(f"Failed to merge streamed wav parts: {e}")
                    return saved_paths[0]
            return saved_paths[0]
        except Exception as e:
            log.error(f"Error streaming/generating audio: {e}")
            wx.CallAfter(wx.MessageBox, _("Failed to generate speech: {error}").format(error=str(e)), _("Error"), wx.OK|wx.ICON_ERROR)
            return None

    def on_play(self, evt):
        if not self.last_audio_path or not os.path.exists(self.last_audio_path):
            wx.MessageBox(_("No audio available to play."), _("Error"), wx.OK|wx.ICON_ERROR)
            return
        try:
            os.startfile(self.last_audio_path)
        except Exception as e:
            wx.MessageBox(_("Failed to play audio: {error}").format(error=str(e)), _("Error"), wx.OK|wx.ICON_ERROR)

    def on_save(self, evt):
        if not self.last_audio_path or not os.path.exists(self.last_audio_path):
            wx.MessageBox(_("No generated audio to save."), _("Error"), wx.OK|wx.ICON_ERROR)
            return
        with wx.FileDialog(self, _("Save Audio File"), wildcard="WAV files (*.wav)|*.wav|MP3 files (*.mp3)|*.mp3",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            dest = dlg.GetPath()
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(self.last_audio_path, "rb") as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                wx.MessageBox(_("Audio saved to {path}").format(path=dest), _("Success"), wx.OK|wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(_("Failed to save audio: {error}").format(error=str(e)), _("Error"), wx.OK|wx.ICON_ERROR)

    def load_voices(self):
        voices = _load_cache()
        if voices:
            log.info("Loaded voices from cache")
        else:
            voices = []
            if self.api_key:
                try:
                    with temp_sys_path(lib_dir):
                        import requests
                    model = self.model or DEFAULT_MODEL
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:listVoices"
                    params = {"key": self.api_key}
                    resp = requests.get(url, params=params, timeout=8)
                    resp.raise_for_status()
                    data = resp.json()
                    for v in data.get("voices", []):
                        name = v.get("name") or v.get("voiceName") or v.get("id")
                        gender = v.get("ssmlGender")
                        langs = v.get("languageCodes") or v.get("languages") or []
                        lang = ", ".join(langs)
                        label = name
                        extra = []
                        if gender:
                            extra.append(gender)
                        if lang:
                            extra.append(lang)
                        if extra:
                            label += f" ({' | '.join(extra)})"
                        voices.append({"name": name, "label": label, "meta": v})
                    if voices:
                        _save_cache(voices)
                        log.info(f"Fetched {len(voices)} voices from Gemini API")
                except Exception as e:
                    log.error(f"Failed to fetch voices from Gemini API: {e}")
            if not voices:
                voices = [{"name": v, "label": v, "meta": {}} for v in FALLBACK_VOICES]
                log.info("Using fallback voice list.")
        def update_ui():
            try:
                self.voices = voices
                voice_labels = [v.get("label") if isinstance(v, dict) else str(v) for v in voices]
                for choice_ctrl in [self.voice_choice_single, self.voice_choice_multi1, self.voice_choice_multi2]:
                    choice_ctrl.Clear()
                    choice_ctrl.AppendItems(voice_labels)
                if voices:
                    self.voice_choice_single.SetSelection(0)
                    self.voice_choice_multi1.SetSelection(0)
                if len(voices) > 1:
                    self.voice_choice_multi2.SetSelection(1)
                log.info(f"Loaded {len(voices)} voices into all controls")
            except Exception as e:
                log.error(f"Failed to update voice UI: {e}")
        wx.CallAfter(update_ui)

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        if CONFIG_DOMAIN not in config.conf:
            config.conf[CONFIG_DOMAIN] = {"apiKey": ""}
        config.conf.spec[CONFIG_DOMAIN] = {"apiKey": "string(default=)"}
        if NativeSpeechSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
            gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(NativeSpeechSettingsPanel)
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(NativeSpeechSettingsPanel)
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
            try:
                dlg.api_key = config.conf[CONFIG_DOMAIN]["apiKey"]
            except Exception:
                dlg.api_key = ""
            dlg.ShowModal()
        except Exception as e:
            log.error(f"Error showing NativeSpeechDialog: {e}")
            wx.MessageBox(_("Failed to open Native Speech Generation dialog: {error}").format(error=str(e)), _("Error"), wx.OK|wx.ICON_ERROR)

    def terminate(self):
        if NativeSpeechSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
            gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(NativeSpeechSettingsPanel)
        try:
            gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self.menuItem)
        except Exception:
            pass
        super().terminate()
