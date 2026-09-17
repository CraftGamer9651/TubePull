# YouTube Video Downloader

A Python command-line script for downloading YouTube videos with quality options and progress tracking.

## Features

- Download YouTube videos in multiple quality options (1080p, 720p, 480p, 360p)
- Download audio-only versions in MP3 format with bitrate options (96, 128, 192, 256, 320 kbps)
- Real-time download progress tracking
- Beautiful web interface with video preview
- Proper file naming and organization
- Robust error handling for common issues
- Support for various YouTube URL formats

## Requirements

- Python 3.6 or higher
- yt-dlp library

## Installation

1. Ensure you have Python 3.6+ installed
2. Install the required dependency:
   ```bash
   pip install yt-dlp
   ```

## Usage

### Basic Usage

Download a video in default quality (720p):
```bash
python youtube_downloader.py https://www.youtube.com/watch?v=VIDEO_ID
