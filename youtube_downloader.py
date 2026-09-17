#!/usr/bin/env python3
"""
YouTube Video Downloader Script

A command-line tool for downloading YouTube videos with quality options
and progress tracking using yt-dlp.
"""

import argparse
import os
import sys
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed. Please install it using:")
    print("pip install yt-dlp")
    sys.exit(1)


class YouTubeDownloader:
    """YouTube video downloader with quality options and progress tracking."""
    
    def __init__(self, download_dir="downloads"):
        """Initialize the downloader with a specified download directory."""
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
    def is_valid_youtube_url(self, url):
        """Validate if the provided URL is a valid YouTube URL."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+'
        ]
        
        for pattern in youtube_patterns:
            if re.match(pattern, url):
                return True
        return False
    
    def progress_hook(self, d):
        """Progress hook for yt-dlp to display download progress."""
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                speed = d.get('speed', 0)
                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
                
                print(f"\rDownloading: {percent:.1f}% | Speed: {speed_str}", end='', flush=True)
            elif '_percent_str' in d:
                print(f"\rDownloading: {d['_percent_str']}", end='', flush=True)
        elif d['status'] == 'finished':
            print(f"\nDownload completed: {d['filename']}")
    
    def get_video_info(self, url):
        """Get video information without downloading."""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown Uploader'),
                    'view_count': info.get('view_count', 0)
                }
        except Exception as e:
            print(f"Error getting video info: {str(e)}")
            return None
    
    def download_video(self, url, quality='720p', audio_only=False, audio_quality='192'):
        """Download video with specified quality or audio-only with bitrate option."""
        if not self.is_valid_youtube_url(url):
            print("Error: Invalid YouTube URL provided.")
            return False
        
        # Get video info first
        print("Fetching video information...")
        video_info = self.get_video_info(url)
        if video_info:
            print(f"Title: {video_info['title']}")
            print(f"Uploader: {video_info['uploader']}")
            duration_min = video_info['duration'] // 60
            duration_sec = video_info['duration'] % 60
            print(f"Duration: {duration_min}:{duration_sec:02d}")
            print()
        
        # Configure download options
        ydl_opts = {
            'outtmpl': str(self.download_dir / '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'restrictfilenames': True,  # Avoid special characters in filenames
        }
        
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': audio_quality,
                }],
            })
            print(f"Downloading audio-only version at {audio_quality} kbps...")
        else:
            # Set video quality
            quality_formats = {
                '1080p': 'best[height<=1080]',
                '720p': 'best[height<=720]',
                '480p': 'best[height<=480]',
                '360p': 'best[height<=360]'
            }
            
            format_selector = quality_formats.get(quality, 'best[height<=720]')
            ydl_opts['format'] = format_selector
            print(f"Downloading video in {quality} quality...")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print(f"\nSuccessfully downloaded to: {self.download_dir}")
            return True
            
        except yt_dlp.DownloadError as e:
            print(f"\nDownload error: {str(e)}")
            return False
        except Exception as e:
            print(f"\nUnexpected error: {str(e)}")
            return False
    
    def list_downloads(self):
        """List all downloaded files in the download directory."""
        files = list(self.download_dir.glob('*'))
        if not files:
            print(f"No downloads found in {self.download_dir}")
            return
        
        print(f"Downloaded files in {self.download_dir}:")
        for i, file_path in enumerate(files, 1):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"{i:2d}. {file_path.name} ({size_mb:.1f} MB)")


def main():
    """Main function to handle command-line arguments and execute downloads."""
    parser = argparse.ArgumentParser(
        description="Download YouTube videos with quality options and progress tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://www.youtube.com/watch?v=dQw4w9WgXcQ
  %(prog)s https://youtu.be/dQw4w9WgXcQ --quality 1080p
  %(prog)s https://youtu.be/dQw4w9WgXcQ --quality 480p
  %(prog)s https://www.youtube.com/watch?v=dQw4w9WgXcQ --audio-only --audio-quality 320
  %(prog)s https://youtu.be/dQw4w9WgXcQ --audio-only --audio-quality 128
  %(prog)s --list
        """
    )
    
    parser.add_argument(
        'url',
        nargs='?',
        help='YouTube video URL to download'
    )
    
    parser.add_argument(
        '--quality', '-q',
        choices=['1080p', '720p', '480p', '360p'],
        default='720p',
        help='Video quality to download (default: 720p)'
    )
    
    parser.add_argument(
        '--audio-only', '-a',
        action='store_true',
        help='Download audio only (MP3 format)'
    )
    
    parser.add_argument(
        '--audio-quality', '-aq',
        choices=['96', '128', '192', '256', '320'],
        default='192',
        help='Audio quality for MP3 downloads in kbps (default: 192)'
    )
    
    parser.add_argument(
        '--download-dir', '-d',
        default='my_downloads',
        help='Directory to save downloads (default: my_downloads)'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all downloaded files'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='YouTube Downloader 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = YouTubeDownloader(args.download_dir)
    
    # Handle list command
    if args.list:
        downloader.list_downloads()
        return
    
    # Validate URL argument
    if not args.url:
        parser.error("URL is required unless using --list option")
    
    # Validate URL format
    if not downloader.is_valid_youtube_url(args.url):
        print("Error: Please provide a valid YouTube URL")
        print("Supported formats:")
        print("  - https://www.youtube.com/watch?v=VIDEO_ID")
        print("  - https://youtu.be/VIDEO_ID")
        print("  - https://www.youtube.com/embed/VIDEO_ID")
        sys.exit(1)
    
    # Check if yt-dlp can access the URL
    print(f"Processing URL: {args.url}")
    print(f"Download directory: {args.download_dir}")
    print("-" * 50)
    
    # Download the video
    success = downloader.download_video(
        args.url,
        quality=args.quality,
        audio_only=args.audio_only,
        audio_quality=args.audio_quality
    )
    
    if success:
        print("\nDownload completed successfully!")
    else:
        print("\nDownload failed. Please check the URL and your internet connection.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        sys.exit(1)
