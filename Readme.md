# GhostDrop

A FastAPI-based anonymous file sharing service that allows users to upload files and share them via email with automatic cleanup and expiration. No user authentication required - files disappear like ghosts after download!

## Features

- **Anonymous Sharing**: No user registration or authentication required
- **Individual File Sharing**: Upload files and get download tokens
- **Group File Sharing**: Share files with multiple recipients via email
- **Email Notifications**: Automatic email delivery with download links
- **Automatic Cleanup**: Files and records are automatically deleted after download or expiration
- **File Size Limits**: Maximum file size of 2GB
- **Time-based Expiration**: Files expire after 24 hours
- **Supported File Types**: Documents, images, videos, audio files, archives, and more

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory:
   ```
   EMAIL_ADDRESS=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   ```

4. Run the application:
   ```bash
   uvicorn src.main:app --reload
   ```

## API Endpoints

### Individual File Sharing

- **POST `/file/upload-file`**: Upload a file and get a download token
  - Parameters: `fileupload` (file), `title` (string)
  - Returns: File ID and download token

- **GET `/file/download-file/{token}`**: Download a file using its token
  - File is automatically deleted after download

- **POST `/file/via-email/`**: Upload and email download link to recipient
  - Parameters: `filerequest` (file), `title` (string), `email` (email), `base_url` (optional)

### Group File Sharing

- **POST `/group-mail/`**: Upload file and share with multiple recipients
  - Parameters: `filerequest` (file), `titlerequest` (string), `members` (comma-separated emails), `baseurl` (optional)
  - Sends individual download links to each recipient

- **GET `/group-mail/download/{token}`**: Download file using group share token
  - Each recipient gets a unique token

## Supported File Types

- Documents: `.txt`, `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`
- Videos: `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`
- Audio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`
- Archives: `.zip`, `.rar`, `.7z`, `.tar`, `.gz`
- Web: `.csv`, `.json`, `.xml`, `.html`, `.css`, `.js`

## Configuration

### Email Setup
The service uses Gmail SMTP by default. For Gmail:
1. Enable 2-factor authentication
2. Generate an App Password
3. Use the App Password in your `.env` file

### File Storage
- Files are stored in the `uploads/` directory
- Maximum file size: 2GB
- Files are automatically cleaned up after download or expiration

### Database
- Uses SQLite database (`app.db`) by default
- Automatic table creation on startup
- Background tasks clean up expired records every 10 minutes

## Security Features

- Unique tokens for each file share
- Time-based expiration (24 hours)
- One-time download links (files deleted after download)
- File type validation
- File size limits
- Empty file rejection

## Background Tasks

- **Auto Cleanup**: Removes expired files and database records every 10 minutes
- **Email Delivery**: Sends emails asynchronously without blocking file uploads
- **File Cleanup**: Removes files from storage after download

## Usage Examples

### Upload and Get Token
```bash
curl -X POST "http://localhost:8000/file/upload-file" \
  -F "fileupload=@example.pdf" \
  -F "title=MyDocument"
```

### Share with Multiple Recipients
```bash
curl -X POST "http://localhost:8000/group-mail/" \
  -F "filerequest=@example.pdf" \
  -F "titlerequest=SharedDocument" \
  -F "members=user1@email.com,user2@email.com,user3@email.com"
```

## Notes

- Each file can only be downloaded once (auto-deletion after download)
- Email delivery is handled in the background
- Files expire after 24 hours regardless of download status
- The service automatically handles timezone-aware expiration