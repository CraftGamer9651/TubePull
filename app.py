#!/usr/bin/env python3
"""
Flask Web Interface for YouTube Video Downloader
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import os
import sys
import json
import threading
import time
from pathlib import Path
import tempfile
import uuid
from youtube_downloader import YouTubeDownloader
import bcrypt

app = Flask(__name__)
app.secret_key = 'youtube-downloader-secret-key-change-in-production'

# Global storage for download progress and session files
download_progress = {}
user_downloads = {}

# Admin credentials
ADMIN_USERNAME = "callemh"
ADMIN_PASSWORD_HASH = '$2a$12$7gwWXJvaKEl8XhHg9xE0oeYlJp9aNAPADIhK/8qR.KqqQ5S86Sn7i'.encode(
    'utf-8')


class ProgressTracker:
    """Custom progress tracker for web interface"""

    def __init__(self, download_id):
        self.download_id = download_id
        self.progress_data = {
            'status': 'starting',
            'percent': 0,
            'speed': '',
            'filename': '',
            'error': None
        }
        download_progress[download_id] = self.progress_data

    def progress_hook(self, d):
        """Progress hook for yt-dlp"""
        print(f"Progress hook called: {d}")  # Debug logging

        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                speed = d.get('speed', 0)
                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"

                self.progress_data.update({
                    'status':
                    'downloading',
                    'percent':
                    round(percent, 1),
                    'speed':
                    speed_str,
                    'filename':
                    os.path.basename(d.get('filename', ''))
                })
            elif '_percent_str' in d:
                try:
                    percent_str = d['_percent_str'].strip()
                    percent = float(percent_str.replace('%', ''))
                    self.progress_data.update({
                        'status':
                        'downloading',
                        'percent':
                        percent,
                        'filename':
                        os.path.basename(d.get('filename', ''))
                    })
                except:
                    pass
            else:
                # Handle cases where we don't have total_bytes
                self.progress_data.update({
                    'status':
                    'downloading',
                    'percent':
                    50,  # Show some progress
                    'filename':
                    os.path.basename(d.get('filename', ''))
                })

        elif d['status'] == 'finished':
            self.progress_data.update({
                'status':
                'finished',
                'percent':
                100,
                'filename':
                os.path.basename(d['filename'])
            })
        elif d['status'] == 'error':
            self.progress_data.update({
                'status': 'error',
                'error': 'Download failed'
            })


def get_user_session():
    """Get or create user session ID"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']


def get_user_download_dir(user_id):
    """Get user-specific download directory"""
    user_dir = Path('user_downloads') / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


class WebYouTubeDownloader(YouTubeDownloader):
    """Extended YouTube downloader with web progress tracking"""

    def __init__(self, download_dir, progress_tracker=None):
        super().__init__(download_dir)
        self.progress_tracker = progress_tracker

    def download_video(self,
                       url,
                       quality='720p',
                       audio_only=False,
                       audio_quality='192'):
        """Download video with web progress tracking"""
        if not self.is_valid_youtube_url(url):
            if self.progress_tracker:
                self.progress_tracker.progress_data[
                    'error'] = "Invalid YouTube URL"
            return False

        # Get video info first
        video_info = self.get_video_info(url)
        if not video_info:
            if self.progress_tracker:
                self.progress_tracker.progress_data[
                    'error'] = "Could not fetch video information"
            return False

        # Configure download options
        ydl_opts = {
            'outtmpl': str(self.download_dir / '%(title)s.%(ext)s'),
            'restrictfilenames': True,
        }

        if self.progress_tracker:
            ydl_opts['progress_hooks'] = [self.progress_tracker.progress_hook]

        if audio_only:
            ydl_opts.update({
                'format':
                'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': audio_quality,
                }],
            })
        else:
            quality_formats = {
                '1080p': 'best[height<=1080]',
                '720p': 'best[height<=720]',
                '480p': 'best[height<=480]',
                '360p': 'best[height<=360]'
            }
            format_selector = quality_formats.get(quality, 'best[height<=720]')
            ydl_opts['format'] = format_selector

        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Ensure we mark as finished even if progress hook didn't catch it
            if self.progress_tracker:
                self.progress_tracker.progress_data.update({
                    'status': 'finished',
                    'percent': 100
                })
            return True

        except Exception as e:
            print(f"Download error: {e}")  # Debug logging
            if self.progress_tracker:
                self.progress_tracker.progress_data['error'] = str(e)
                self.progress_tracker.progress_data['status'] = 'error'
            return False


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/download', methods=['POST'])
def start_download():
    """Start a download"""
    data = request.get_json()
    url = data.get('url', '').strip()
    quality = data.get('quality', '720p')
    audio_only = data.get('audio_only', False)
    audio_quality = data.get('audio_quality', '192')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Get user session and download directory
    user_id = get_user_session()
    user_download_dir = get_user_download_dir(user_id)

    # Generate unique download ID
    download_id = str(uuid.uuid4())

    # Create progress tracker
    progress_tracker = ProgressTracker(download_id)

    # Start download in background thread
    def download_thread():
        downloader = WebYouTubeDownloader(user_download_dir,
                                          progress_tracker=progress_tracker)
        try:
            success = downloader.download_video(url, quality, audio_only,
                                                audio_quality)
            if success:
                # Track the downloaded file for this user
                if user_id not in user_downloads:
                    user_downloads[user_id] = []

                filename = progress_tracker.progress_data.get('filename', '')
                if filename:
                    user_downloads[user_id].append({
                        'filename': filename,
                        'download_id': download_id,
                        'timestamp': time.time()
                    })

            if not success and not progress_tracker.progress_data.get('error'):
                progress_tracker.progress_data['error'] = "Download failed"
        except Exception as e:
            progress_tracker.progress_data['error'] = str(e)

    thread = threading.Thread(target=download_thread)
    thread.daemon = True
    thread.start()

    return jsonify({'download_id': download_id})


@app.route('/api/progress/<download_id>')
def get_progress(download_id):
    """Get download progress"""
    progress = download_progress.get(
        download_id, {
            'status': 'not_found',
            'percent': 0,
            'speed': '',
            'filename': '',
            'error': 'Download not found'
        })
    return jsonify(progress)


@app.route('/api/downloads')
def list_downloads():
    """List downloaded files for current user"""
    user_id = get_user_session()
    user_download_dir = get_user_download_dir(user_id)
    files = []

    if user_download_dir.exists():
        for file_path in user_download_dir.glob('*'):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                files.append({
                    'name': file_path.name,
                    'size': f"{size_mb:.1f} MB",
                    'download_url': f'/download/{file_path.name}'
                })

    return jsonify({'files': files})


@app.route('/download/<filename>')
def download_file(filename):
    """Download a file for current user"""
    user_id = get_user_session()
    user_download_dir = get_user_download_dir(user_id)
    file_path = user_download_dir / filename

    # Security check: ensure file belongs to current user and exists
    if file_path.exists() and file_path.is_file(
    ) and user_download_dir in file_path.parents:
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found or access denied'}), 404


@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    """Get video information"""
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    downloader = YouTubeDownloader()
    if not downloader.is_valid_youtube_url(url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    video_info = downloader.get_video_info(url)
    if not video_info:
        return jsonify({'error': 'Could not fetch video information'}), 400

    # Format duration
    duration = video_info.get('duration', 0)
    duration_min = duration // 60
    duration_sec = duration % 60
    video_info['duration_formatted'] = f"{duration_min}:{duration_sec:02d}"

    return jsonify(video_info)


@app.route('/admin')
def admin_login():
    """Admin login page"""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    """Handle admin login"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if username in ADMIN_USERNAME and ADMIN_PASSWORD_HASH and bcrypt.checkpw(
            password.encode('utf-8'), ADMIN_PASSWORD_HASH):
        session['admin_logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('admin_login'))


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard showing all downloads"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    all_downloads = []
    base_dir = Path('user_downloads')

    if base_dir.exists():
        for user_dir in base_dir.iterdir():
            if user_dir.is_dir():
                user_id = user_dir.name
                for file_path in user_dir.glob('*'):
                    if file_path.is_file():
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        modified_time = file_path.stat().st_mtime
                        all_downloads.append({
                            'user_id':
                            user_id,
                            'filename':
                            file_path.name,
                            'size':
                            f"{size_mb:.1f} MB",
                            'download_time':
                            time.strftime('%Y-%m-%d %H:%M:%S',
                                          time.localtime(modified_time)),
                            'download_url':
                            f'/admin/download/{user_id}/{file_path.name}'
                        })

    # Sort by download time (newest first)
    all_downloads.sort(key=lambda x: x['download_time'], reverse=True)

    return render_template('admin_dashboard.html', downloads=all_downloads)


@app.route('/admin/download/<user_id>/<filename>')
def admin_download_file(user_id, filename):
    """Admin download any user's file"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    user_download_dir = Path('user_downloads') / user_id
    file_path = user_download_dir / filename

    if file_path.exists() and file_path.is_file():
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404


@app.route('/admin/erase-all-data', methods=['POST'])
def admin_erase_all_data():
    """Erase all user download data"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        import shutil

        base_dir = Path('user_downloads')
        if base_dir.exists():
            # Remove all user directories and files
            shutil.rmtree(base_dir)
            # Recreate empty directory
            base_dir.mkdir(exist_ok=True)

        # Also clear any progress tracking data
        download_progress.clear()

        return jsonify({
            'success': True,
            'message': 'All data has been erased successfully'
        })

    except Exception as e:
        return jsonify({'error': f'Failed to erase data: {str(e)}'}), 500


def cleanup_old_user_downloads():
    """Clean up user download directories older than 24 hours"""
    try:
        base_dir = Path('user_downloads')
        if not base_dir.exists():
            return

        current_time = time.time()
        for user_dir in base_dir.iterdir():
            if user_dir.is_dir():
                # Check if directory is older than 24 hours
                dir_age = current_time - user_dir.stat().st_mtime
                if dir_age > 24 * 3600:  # 24 hours in seconds
                    # Remove old user directory and files
                    import shutil
                    shutil.rmtree(user_dir)
                    print(f"Cleaned up old user downloads: {user_dir.name}")
    except Exception as e:
        print(f"Error during cleanup: {e}")


if __name__ == '__main__':
    # Create user downloads base directory
    Path('user_downloads').mkdir(exist_ok=True)

    # Clean up old downloads on startup
    cleanup_old_user_downloads()

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
