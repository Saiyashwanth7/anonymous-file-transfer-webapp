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
from models import Share, GroupShare
from typing import Annotated, List
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path as PathLib
from datetime import timezone, datetime
from pydantic import EmailStr, BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from .file_share import (
    ALLOWED_EXTENSIONS,
    MAXIMUM_FILE_SIZE,
    UPLOAD_DIR,
)


def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()


class EmailValidator(BaseModel):
    email: EmailStr


router = APIRouter(prefix="/group-mail", tags=["group-mail"])


db_dependency = Annotated[Session, Depends(get_db)]

SMTP_SERVER = "smtp.gmail.com" 
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") 

async def send_email(to_email: str, filename: str, download_token: str, base_url: str):
    download_link = f"{base_url}/group-mail/download/{download_token}"
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
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
    
async def group_mail_gshare(
    members: List[str],
    filename: str,
    share_id: int,
    db: db_dependency,
    base_url: str = Form(default="http://localhost:8000"),
):
    if not members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Add alteast one member"
        )
    success_count = 0
    failed_emails = []
    for email in members:
        try:
            receiving_record = (
                db.query(GroupShare)
                .filter(
                    GroupShare.share_id == share_id, GroupShare.receiver_email == email
                )
                .first()
            )
            success = await send_email(
                email, filename, receiving_record.token, base_url
            )
            if success:
                success_count += 1
            else:
                failed_emails.append(email)
        except Exception as e:
            print(f"Error sending email to {email}: {e}")
            failed_emails.append(email)

    if failed_emails:
        return f"Failed to send to: {failed_emails}"

    return (
        f"Group email summary: {success_count}/{len(members)} sent successfully",
        True,
    )


# reusable function for uploading file for single user
async def group_share(
    db: db_dependency, email_list: list, filerequest: UploadFile, titlerequest: str
):
    if not filerequest.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a valid file"
        )
    if len(email_list) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Emails cannot be recognized",
        )
    file_type = PathLib(filerequest.filename).suffix.lower()
    if file_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{file_type} not allowed"
        )
    new_title = f"{titlerequest}{file_type}"

    unique_name = f"{str(uuid.uuid4())}_{new_title}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    if file_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{file_type} type files not valid",
        )
    try:
        current_size = 0
        await filerequest.seek(0)
        with open(f"{file_path}", "wb") as f:
            while chunk := await filerequest.read(1024 * 1024):
                current_size += len(chunk)
                if current_size > MAXIMUM_FILE_SIZE:
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File exceeded the limit of 2GB",
                    )
                f.write(chunk)
        if current_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty files are not allowed",
            )
        recipient_Records = []
        new_file_record = Share(
            file_name=new_title,
            file_path=file_path,
            file_type=file_type,
        )
        db.add(new_file_record)
        db.commit()
        db.refresh(new_file_record)
        for email in email_list:
            new_record = GroupShare(
                receiver_email=email,
                share_id=new_file_record.id,
            )
            db.add(new_record)
            recipient_Records.append(new_record)
        db.commit()
        for record in recipient_Records:
            db.refresh(record)

        return recipient_Records,new_file_record.id

    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.rollback()
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{e}")

"""async def cleanup(filepath,db:db_dependency,group_request):
    try:
        # Delete the group share record
        db.delete(group_request)
        
        # Check if other group shares are using this file
        other_shares = db.query(GroupShare).filter(
            GroupShare.id != group_request.id
        ).count()
        
        # Only delete file if no other shares are using it
        if other_shares == 0 and os.path.exists(filepath):
            os.remove(filepath)
            
        db.commit()
        print(f"Cleaned up group share record and file: {filepath}")
        
    except Exception as e:
        print(f"Error in cleanup_group_share: {e}")
        db.rollback()"""

@router.get("/")
async def read_gshare(db: db_dependency):
    return db.query(GroupShare).all()


@router.post("/")
async def group_share_using_GS(
    db: db_dependency,
    filerequest: UploadFile,
    background_tasks: BackgroundTasks,
    titlerequest: str = Form(...),
    members: str = Form(...),
    baseurl: str = Form(default="http://localhost:8000"),
):
    if not filerequest.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File invalid"
        )
    file_type = PathLib(filerequest.filename).suffix.lower()
    if file_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"files of type {file_type} are invalid",
        )
    try:
        # Extract all the mails from the members form
        email_list = [email.strip() for email in members.split(",") if email.strip()]

        # validating emails of each reciever:
        validated_email = []
        for email in email_list:
            validated = EmailValidator(email=email)
            validated_email.append(validated.email)

        if len(validated_email) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid email addresses provided",
            )

        recipients, share_id = await group_share(
            db, email_list, filerequest, titlerequest
        )
        if len(recipients) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No recepients created",
            )

        background_tasks.add_task(
            group_mail_gshare, validated_email, titlerequest, share_id, db, baseurl
        )

        return {
            "message": "File uploaded and emails are being sent",
            "recipients_count": len(recipients),
            "recipients": [
                {
                    "email": r.receiver_email,
                    "token": r.token,
                    "expires": r.expires.isoformat(),
                }
                for r in recipients
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return f"Exception {e} occurred!"


@router.get("/download/{token}")
async def downlaod_group_shared_file(
    db: db_dependency, token: str, background_tasks: BackgroundTasks
):
    group_request = db.query(GroupShare).filter(GroupShare.token == token).first()
    share_id=group_request.share_id
    sharing_file=db.query(Share).filter(Share.id==share_id).first()
    if not sharing_file:
        raise HTTPException(status_code=404, detail="File Not Found")
    if not sharing_file.file_path:
        return {"message": "file path is None"}

    current_time = datetime.now(timezone.utc)
    if sharing_file.expires.tzinfo is None:
        expires_time = sharing_file.expires.replace(tzinfo=timezone.utc)
    else:
        expires_time = sharing_file.expires

    if current_time > expires_time:
        # Clean up expired record
        if os.path.exists(sharing_file.file_path):
            # Check if other group shares are using this file
            other_shares = (
                db.query(GroupShare)
                .filter(
                    Share.file_path == group_request.file_path,
                    Share.id != group_request.share_id,
                )
                .count()
            )

            # Only delete file if no other shares are using it
            if other_shares == 0:
                os.remove(sharing_file.file_path)

        db.delete(sharing_file)
        db.commit()
        raise HTTPException(status_code=404, detail="Download link has expired")

    #background_tasks.add_task(cleanup, sharing_file.file_path, db, sharing_file)

    return FileResponse(
        path=sharing_file.file_path,
        filename=sharing_file.file_name,
        media_type="application/octet-stream",
    )
