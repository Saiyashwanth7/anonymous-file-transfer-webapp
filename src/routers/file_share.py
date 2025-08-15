from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    Form,
    BackgroundTasks,
    HTTPException,
)
from fastapi.responses import FileResponse
from starlette import status
from database import sessionLocal
from models import Share
from typing import Annotated
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path as PathLib
from datetime import timezone, datetime
from pydantic import EmailStr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/file", tags=["file"])

db_dependency = Annotated[Session, Depends(get_db)]


# Email configuration
SMTP_SERVER = "smtp.gmail.com"  # for Gmail
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  # Set in .env file
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # Use App Password if using Gmail


# Function to send email
async def send_email(to_email: str, filename: str, download_token: str, base_url: str):
    download_link = f"{base_url}/file/download-file/{download_token}"
    subject = f"File Ready for Download: {filename}"
    body = f"""
    Hello!
    
    Your file "{filename}" has been uploaded and is ready for download.
    
    Download Link: {download_link}
    
    Important Notes:
    - This file will be automatically deleted after download
    - The link expires in 24 hours
    - The file can only be downloaded once
    
    If you did not request this file, please ignore this email.
    
    Best regards,
    File Sharing Service
    """
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")


async def cleanup(filepath: str, db: db_dependency, filerequest):
    try:
        db.delete(filerequest)
        db.commit()
        os.remove(filepath)
    except Exception as e:
        print(f"{e} from 'Cleanup'")


MAXIMUM_FILE_SIZE = 2 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.mp3', '.wav', '.flac', '.aac', '.ogg',
    '.zip', '.rar', '.7z', '.tar', '.gz',
    '.csv', '.json', '.xml', '.html', '.css', '.js'
}


async def core_share(
    db: db_dependency,
    filerequest: UploadFile,
    file_path: str,
    file_type: str,
    new_title: str,
):
    current_size = 0
    with open(f"{file_path}", "wb") as f:
        while chunk := await filerequest.read(1024 * 1024):
            current_size += len(chunk)
            if current_size > MAXIMUM_FILE_SIZE:
                f.close()
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File size exceeded maximum file size of 2GB ",
                )
            f.write(chunk)
            # here we are using chunks to support larger data

    # added the file name and path into DB
    new_file = Share(file_name=new_title, file_path=file_path, file_type=file_type)
    db.add(new_file)
    db.commit()
    db.refresh(new_file)


@router.get("/")
async def read_db(db: db_dependency):
    return db.query(Share).all()


@router.post("/upload-file")
async def upload_file(
    db: db_dependency, fileupload: UploadFile, title: str = Form(...)
):
    if not fileupload.filename:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Upload a File"
        )

    # here the file type and the new name are joined
    file_type = PathLib(fileupload.filename).suffix
    if file_type.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{file_type} - Files not acceptable",
        )

    new_name = f"{title}{file_type}"

    unique_name = f"{str(uuid.uuid4())}_{new_name}"

    # created a path to store the uploaded file below
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        # lets first add the file into local storage
        # Now we will write the uploaded file into the local storage file path
        current_size = 0
        with open(f"{file_path}", "wb") as f:
            while chunk := await fileupload.read(1024 * 1024):
                current_size += len(chunk)
                if current_size > MAXIMUM_FILE_SIZE:
                    f.close()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size exceeded maximum file size of 2GB ",
                    )
                f.write(chunk)
                # here we are using chunks to support larger data

        # added the file name and path into DB
        new_file = Share(file_name=new_name, file_path=file_path, file_type=file_type)
        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        return {
            "status": "uploaded",
            "file_id": new_file.id,
            "Download token": new_file.token,
            "size": fileupload.size,
        }

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}"
        )


@router.get("/download-file/{token}")
async def download_file(
    db: db_dependency, background_tasks: BackgroundTasks, token: str
):
    filerequest = db.query(Share).filter(Share.token == token).first()
    if not filerequest:
        raise HTTPException(status_code=404, detail="File Not Found")
    if not filerequest.file_path:
        return {"message": "file path is None"}

    current_time = datetime.now(timezone.utc)
    if filerequest.expires.tzinfo is None:
        expires_time = filerequest.expires.replace(tzinfo=timezone.utc)
    else:
        expires_time = filerequest.expires

    if current_time > expires_time:
        db.delete(filerequest)
        db.commit()
        os.remove(filerequest.file_path)
        raise HTTPException(status_code=404, detail="Time bound exceeded")

    background_tasks.add_task(cleanup, filerequest.file_path, db, filerequest)

    return FileResponse(
        path=filerequest.file_path,
        filename=filerequest.file_name,
        media_type="application/octet-stream",
    )


@router.post("/via-email/")
async def share_via_email(
    db: db_dependency,
    background_tasks: BackgroundTasks,
    filerequest: UploadFile,
    title: str = Form(...),
    email: EmailStr = Form(...),
    base_url: str = Form(default="http://localhost:8000"),
):
    if not filerequest.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a file"
        )
    file_type = PathLib(filerequest.filename).suffix
    new_title = f"{str(uuid.uuid4())}_{title}.{file_type}"
    file_path = os.path.join(UPLOAD_DIR, new_title)

    try:
        # lets first add the file into local storage
        # Now we will write the uploaded file into the local storage file path
        current_size = 0
        with open(f"{file_path}", "wb") as f:
            while chunk := await filerequest.read(1024 * 1024):
                current_size += len(chunk)
                if current_size > MAXIMUM_FILE_SIZE:
                    f.close()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size exceeded maximum file size of 2GB ",
                    )
                f.write(chunk)
                # here we are using chunks to support larger data

        # added the file name and path into DB
        new_file = Share(file_name=new_title, file_path=file_path, file_type=file_type)
        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        background_tasks.add_task(
            send_email,
            email,
            new_file.file_name,
            new_file.token,
            base_url
        )

        background_tasks.add_task(cleanup, new_file.file_path, db, new_file)

        return {"message": "Email sent succefully"}

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
            db.rollback()
        return f"Exception {e} occurred!"
