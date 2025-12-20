# Native Speech Generation for NVDA

**Author:** Muhammad Gagah [muha.aku@gmail.com](mailto:muha.aku@gmail.com)

Native Speech Generation is an NVDA add-on that integrates **Google Gemini AI** to generate high-quality, natural-sounding speech directly within NVDA.
It provides a clean, fully accessible interface for converting text into audio, supporting both **single-speaker narration** and **dynamic multi-speaker dialogues**.

This add-on is designed for smooth workflows, accessibility-first interaction, and flexible voice control suitable for narration, dialogue, and audio content production.

---

## Features

### High-Quality Speech Generation

* Choose between:

  * **Gemini Flash** Standard quality, fast generation, low latency.
  * **Gemini Pro** Premium, more realistic voices (paid model).

### Single & Multi-Speaker Modes

* **Single-speaker narration** for standard text-to-speech.
* **Multi-speaker (2 speakers)** mode for dialogues with distinct voices.

### Advanced Voice Control

* **Speaker Naming**
  Assign custom names (e.g., *John*, *Mary*) in multi-speaker mode.
  The AI automatically maps voices based on speaker names in the script.
* **Style Instructions**
  Provide prompts such as *“Speak in a cheerful tone”* or *“Narrate calmly”* to guide delivery.
* **Temperature Control**
  Adjust output variation and creativity:

  * Lower values → more stable and predictable speech.
  * Higher values → more expressive and varied speech.

### Accessible & Clean Interface

* Fully accessible with screen readers.
* Advanced options are placed in a collapsible panel to keep the main dialog simple and focused.

### Seamless Workflow

* Audio plays automatically after generation.
* Generated audio can be replayed or saved as a high-quality `.wav` file.
* Designed for minimal friction during repeated generation and playback.

### Smart Voice Loading & Caching

* Available voices are fetched dynamically from the Gemini API.
* Voice data is cached for **24 hours** to reduce API calls and speed up startup.

---

## Requirements

* NVDA (latest version recommended).
* Active internet connection.
* A valid **Google Gemini API Key**.

---

## Installation

1. Download the latest add-on package from the
   **Releases page:**
   [https://github.com/MuhammadGagah/native-speech-generation/releases](https://github.com/MuhammadGagah/native-speech-generation/releases)
2. Install it like any standard NVDA add-on.
3. Restart NVDA when prompted.

---

## API Key Setup (Required)

1. Create an API key from **Google AI Studio**:
   [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Open NVDA and go to:
   **NVDA Menu → Tools → Native Speech Generation**
3. Click **“API Key Settings”**.
4. This opens NVDA Settings directly in the *Native Speech Generation* category.
5. Paste your **Gemini API Key** into the *GEMINI API Key* field.
6. Click **OK** to save.

---

## How to Use

Open the dialog using:

* **NVDA+Control+Shift+G**, or
* **NVDA Menu → Tools → Native Speech Generation**

### Main Interface Elements

* **Text to convert**
  Enter or paste the text you want to convert to speech.
* **Style instructions (optional)**
  Provide guidance for tone, emotion, or delivery.
* **Select Model**

  * Flash (Standard Quality)
  * Pro (High Quality)
* **Speaker Mode**

  * Single-speaker
  * Multi-speaker (2)

---

## Generating Speech

### Single-Speaker Mode

1. Select **Single-speaker**.
2. Choose a voice from the *Select Voice* dropdown.
3. Enter your text.
4. Optionally add style instructions.
5. Click **Generate Speech**.
6. The audio will play automatically after generation.

---

### Multi-Speaker Mode

1. Select **Multi-speaker (2)**.
2. For each speaker:

   * Enter a unique **Speaker Name**.
   * Select a distinct **Voice**.
3. Format the text so each line starts with the speaker name followed by a colon.

**Example:**

```
Alice: Hi Bob, how are you today?
Bob: I'm doing great, Alice! The weather is fantastic.
```

4. Click **Generate Speech**.
   Voices will be assigned automatically based on the speaker names.

---

## Advanced Settings

* Enable **Advanced Settings (Temperature)** to show the slider.
* **Temperature Range**:

  * `0.0` → Most deterministic and stable.
  * `1.0` → Default balance.
  * `2.0` → Most creative and varied.

---

## Buttons Overview

* **Generate Speech** – Start speech generation.
* **Play** – Replay the last generated audio.
* **Save Audio** – Save the last audio as a `.wav` file.
* **API Key Settings** – Open the add-on configuration in NVDA Settings.
* **View voices in AI Studio** – Opens Google AI Studio in a browser.
* **Close** – Close the dialog (or press `Escape`).

---

## Input Gestures

Customizable via:
**NVDA Menu → Preferences → Input Gestures → Native Speech Generation**

Default gesture:

* **NVDA+Control+Shift+G** – Open Native Speech Generation dialog.

---

## Development & Contribution Guide

If you want to develop or modify this add-on, follow the steps below.

### Environment Setup

* **Python 32-bit (3.11.9 recommended)**
  [https://www.python.org/downloads/release/python-3119/](https://www.python.org/downloads/release/python-3119/)
* **SCons 4.9.1 or newer**

  ```
  pip install scons
  ```
* **GNU Gettext Tools** (optional, recommended for localization)

  * Usually preinstalled on Linux/Cygwin.
  * Windows: [https://gnuwin32.sourceforge.net/downlinks/gettext.php](https://gnuwin32.sourceforge.net/downlinks/gettext.php)
* **Markdown 3.8+** (for documentation conversion)

  ```
  pip install markdown
  ```

### Additional Dependencies

Install the Gemini SDK directly into the add-on library path:

```
python.exe -m pip install google-genai --target "D:/myAdd-on/Native-Speech-Generation/addon/globalPlugins/lib"
```

Adjust the path according to your local add-on source directory.

Then copy the following from your Python installation into:

```
addon/globalPlugins/lib
```

* `zoneinfo` folder
* `secrets.py` file

---

## Contributing

Contributions, suggestions, and bug reports are very welcome.

* Open an **Issue** for bugs or feature requests.
* Submit a **Pull Request** for code contributions.

**Contact**

* Email: `muha.aku@gmail.com`
* GitHub: [https://github.com/MuhammadGagah](https://github.com/MuhammadGagah)
