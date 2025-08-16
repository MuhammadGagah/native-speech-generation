# Native Speech Generation for NVDA

**Author:** Muhammad Gagah <muha.aku@gmail.com>

Harness the power of Google's state-of-the-art Gemini AI for high-quality speech generation directly within NVDA. This add-on provides a user-friendly dialog to convert text into natural-sounding audio, supporting both single-speaker narration and dynamic multi-speaker dialogues.

## Features

-   **High-Quality Voices**: Choose between **Gemini Flash** for standard-quality, low-latency speech and **Gemini Pro** for premium, life-like audio generation.
-   **Single and Multi-Speaker Modes**: Easily generate audio for a single narrator or create dynamic dialogues with two distinct speakers.
-   **Advanced Voice Control**:
    -   **Speaker Naming**: In multi-speaker mode, assign custom names to each speaker (e.g., "John", "Mary"). The AI will automatically assign the correct voice based on the names in your script.
    -   **Style Instructions**: Provide prompts (e.g., "Speak in a cheerful tone") to guide the AI's performance and delivery.
    -   **Temperature Control**: Adjust the temperature slider in the Advanced Settings to influence the creativity of the speech output. Lower values produce more stable, predictable speech, while higher values allow for more variation.
-   **Accessible & Clean Interface**: All controls are fully accessible. Advanced settings are tucked away in a collapsible panel to keep the main interface focused and easy to navigate.
-   **Seamless Workflow**:
    -   **Instant Autoplay**: Audio is automatically played upon successful generation.
    -   **Playback & Save**: Easily replay the last generated audio or save it as a high-quality `.wav` file.
-   **Smart Voice Loading**: The add-on fetches the latest available voices from the Gemini API and caches them for 24 hours to ensure fast startup times.

## Requirements

-   NVDA (latest version recommended).
-   An internet connection is required for API communication.
-   A **Google Gemini API Key**.

## Installation and Setup

1.  Download and install the add-on like any other NVDA add-on.
2.  Restart NVDA when prompted.
3.  **Crucially, you must configure your Gemini API Key.**
    -   Go to the [Google AI Studio](https://aistudio.google.com/apikey) to create and copy your API key.
    -   In NVDA, go to the **NVDA Menu -> Tools -> Native Speech Generation**.
    -   In the dialog that appears, click the **"API Key Settings"** button. This will open the NVDA Settings dialog directly to the "Native Speech Generation" category.
    -   Paste your API key into the "GEMINI API Key" field and click "OK" to save.

## How to Use

1.  Open the Native Speech Generation dialog by pressing the default shortcut **`NVDA+Control+Shift+G`** or by going to the **NVDA Menu -> Tools -> Native Speech Generation**.

### Main Interface

-   **Text to convert, enter here**: The main text area where you type or paste the content you want to convert to speech.
-   **Style instructions (optional)**: Enter prompts here to influence the tone and delivery of the speech (e.g., "Narrate in a calm, soothing voice", "Speak with excitement").
-   **Select Model**:
    -   **Flash (Standard Quality)**: Default. Best for quick generation and general use.
    -   **Pro (High Quality)**: Best for final productions requiring premium, natural-sounding audio.
-   **Speaker Mode**:
    -   **Single-speaker**: For standard text-to-speech with one voice.
    -   **Multi-speaker (2)**: For dialogues between two people.

### Generating Speech

#### Single-Speaker Mode

1.  Ensure the "Single-speaker" radio button is selected.
2.  Select the desired voice from the "Select Voice" dropdown.
3.  Enter your text in the main text area.
4.  Optionally, add style instructions.
5.  Click the **"Generate Speech"** button.
6.  You will hear "Generating speech, please wait...". Upon completion, the audio will play automatically.

#### Multi-Speaker Mode

1.  Select the "Multi-speaker (2)" radio button. This will reveal controls for two speakers.
2.  For each speaker (Speaker 1 and Speaker 2):
    -   Enter a unique name in the **"Speaker Name"** field (e.g., "Alice", "Bob").
    -   Select a distinct voice from the corresponding **"Voice"** dropdown.
3.  In the main text area, format your script by starting each line with the speaker's name followed by a colon. **The names must exactly match what you entered in the "Speaker Name" fields.**

    **Example Text:**
    ```
    Alice: Hi Bob, how are you today?
    Bob: I'm doing great, Alice! The weather is fantastic.
    ```
4.  Click the **"Generate Speech"** button. The AI will read the dialogue, assigning the correct voices based on the speaker names.

### Advanced Settings

-   Click the **"Advanced Settings (Temperature)"** checkbox to reveal the temperature slider.
-   **Temperature Slider**: Controls the randomness of the output. The default value is `1.0`.
    -   `0.0`: Most deterministic and stable.
    -   `2.0`: Most creative and varied.

### Buttons

-   **Generate Speech**: Starts the audio generation process.
-   **Play**: Replays the last successfully generated audio.
-   **Save Audio**: Opens a dialog to save the last generated audio as a `.wav` file.
-   **API Key Settings**: Opens the NVDA Settings dialog to the add-on's configuration panel.
-   **View voices in AI Studio**: Opens the Google AI Studio website in your browser for reference.
-   **Close**: Closes the dialog. You can also press `Escape`.

## Input Gestures

The following gestures can be customized via **NVDA Menu -> Preferences -> Input Gestures**, under the "Native Speech Generation" category.

-   **`NVDA+Control+Shift+G`**: Opens the Native Speech Generation dialog.

## Contributing

Suggestions and improvements are always welcome! If you have any feedback, ideas, or bug reports, please feel free to reach out.

-   **Email:** Contact me at `muha.aku@gmail.com`
-   **GitHub:** Open an issue or a pull request on the [project's GitHub repository](https://github.com/muhammadGagah).