# Freek de Jonge Humor Detection

This repository currently contains a Google Colab notebook, `freek_de_jonge_humor_detection.ipynb`, for analyzing a Freek de Jonge comedy performance in three stages:

1. Detect laughter segments in an audio recording.
2. Align those laughter segments with a transcript.
3. Categorize the likely humor type of each laughing moment with the OpenAI API.

The notebook is built around an MP3 recording of `1980 - Freek de Jonge - De Komiek - Hele show.mp3` and a matching transcript JSON file.

## What The Notebook Does

The notebook runs an end-to-end workflow:

- Clones the external `laughter-detection` repository that provides the laughter segmentation model.
- Installs the Python dependencies needed in Colab.
- Loads a pretrained laughter detection checkpoint.
- Runs inference over a selected audio file.
- Saves detected laughter timestamps and, optionally, cropped laughter audio files and a TextGrid file.
- Merges laughter timestamps with transcript segments to attach context and spoken text to each laugh.
- Optionally sends each laughter-linked transcript segment to the OpenAI API for humor categorization.

## Expected Inputs

To run the full notebook, you should have:

- An audio file, typically an MP3 performance recording.
- A transcript JSON file aligned to the same recording.
- Access to Google Colab.
- An `OPENAI_API_KEY` if you want to run the final humor categorization step.

The notebook is written with Colab paths in mind and uses Google Drive for output storage.

## Main Workflow

### 1. Setup

The first cells:

- Clone `https://github.com/jorrytdejong/laughter-detection.git`
- Install packages such as `librosa`, `tgt`, `pyloudnorm`, `praatio`, `tensorboardX`, `torch`, `openai`, and `pydantic`
- Mount Google Drive when running in Colab

GPU is optional but recommended in Colab for faster inference.

### 2. Load The Laughter Detection Model

The notebook then:

- Switches into the cloned `laughter-detection` repository
- Imports the repo modules
- Loads the pretrained checkpoint from `checkpoints/in_use/resnet_with_augmentation/best.pth.tar`

### 3. Run Laughter Detection

You select an audio file and run inference with configurable settings such as:

- `threshold = 0.4`
- `min_length = 0.2`
- `save_to_audio_files = True`
- `save_to_textgrid = False`

This stage detects laughter intervals in the recording and can export each detected laugh as a separate WAV clip.

### 4. Merge With Transcript

The transcript alignment stage combines the detected laughter intervals with transcript segments and writes a richer JSON output that includes:

- Time range
- Context before the laugh-triggering line
- Text associated with the laugh
- Speaker information

The notebook uses `TRANSCRIPT_FPS = 25.0` for time conversion.

### 5. Categorize Humor With OpenAI

The final stage reads the transcript-enriched laughter segments and classifies the humor source using the OpenAI API.

The prompt in the notebook supports labels such as:

- Stupidity
- Self-mockery
- Primitive humor
- Black humor
- Irony
- Schadenfreude
- Language humor
- Exaggeration
- Understatement
- Clever observation
- Sudden twist
- Inappropriate remark
- Circular humor
- Anti-humor

For each segment, the notebook stores structured output with:

- The predicted primary category
- Confidence
- Evidence
- Reasoning
- An overall explanation

The categorization cell currently uses `gpt-5-nano`.

## Generated Outputs

Depending on which cells you run, the notebook writes outputs such as:

- `laughter_timestamps.json`
- `laughter_with_text.json`
- `laughter_with_humor_categories.json`
- Individual laughter WAV clips
- Optional Praat `TextGrid` annotations

Outputs are stored in a Google Drive folder under a path like:

`/content/drive/MyDrive/FreekdeJonge/laughter_detection/<audio-file-name>/`

## How To Use

1. Open `freek_de_jonge_humor_detection.ipynb` in Google Colab.
2. Run the setup and dependency cells.
3. Mount Google Drive if prompted.
4. Set the input audio file and confirm the transcript JSON path.
5. Run the laughter detection cell.
6. Run the transcript merge cell to create `laughter_with_text.json`.
7. Set `OPENAI_API_KEY` and run the humor categorization cell if you want labeled humor output.

## Notes

- The notebook is currently tailored to a Colab-based workflow rather than a packaged local CLI pipeline.
- It depends on the external `laughter-detection` repository for the laughter model and inference utilities.
- The repository currently focuses on the notebook and its analysis workflow rather than a standalone Python package.
