# Changelog

## v1.2

**What's New in v1.2**

* **Added**: API Key visibility toggle in NVDA settings (option to show/hide Gemini API key).
* **Added**: Automatic NVDA restart after dependency installation completes.
* **Added**: Ukrainian translation by George.
* **Improved**: Dialog stability by wrapping all `wx.MessageBox` calls in `wx.CallAfter` to prevent freezes.
* **Improved**: Error dialogs are now standardized and non-blocking where appropriate.
* **Refactored**: Safer configuration handling with guards for missing keys.
* **Cleaned**: Removed unused imports, simplified logging, and improved inline translator comments.

---

## v1.1

**What's New in v1.1**

* **Added**: Ability to play voice samples directly from voice selection.
* **Refactored**: Code structure for better readability and PEP8 compliance.
* **Improved**: Error handling, UI layout, and logging.
* **Optimized**: Voice selection logic and threading for better performance.
* **Enhanced**: Audio format detection and WAV conversion for inline PCM.

---

## v1.0

**Initial Release**

* First release of **Native Speech Generation** add-on.
