from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    Form,
    BackgroundTasks,
    Path,
    HTTPException,
)
from fastapi.responses import FileResponse
from starlette import status
from database import sessionLocal, engine
import models
from models import Share
from typing import Annotated
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path as PathLib
from datetime import timezone,timedelta,datetime


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


async def cleanup(filepath: str, db:db_dependency, filerequest):
    try:
        db.delete(filerequest)
        db.commit()
        os.remove(filepath)
    except Exception as e:
        print(f"{e} from 'Cleanup'")


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
    new_name = f"{title}{file_type}"

    unique_name = f"{str(uuid.uuid4())}_{new_name}"

    # created a path to store the uploaded file below
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        # lets first add the file into local storage
        # Now we will write the uploaded file into the local storage file path
        with open(f"{file_path}", "wb") as f:
            while chunk := await fileupload.read(1024 * 1024):
                f.write(chunk)
                # here we are using chunks to support larger data

        # added the file name and path into DB
        new_file = Share(file_name=new_name, file_path=file_path)
        db.add(new_file)
        db.commit()
        db.refresh(new_file)

        return {
            "status": "uploaded",
            "file_id": new_file.id,
            "Download token": new_file.token,
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
        return {"message":"file path is None"}
    
    current_time=datetime.now(timezone.utc)
    if filerequest.expires.tzinfo is None:
        expires_time = filerequest.expires.replace(tzinfo=timezone.utc)
    else:
        expires_time=filerequest.expires
        
    if current_time>expires_time:
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
