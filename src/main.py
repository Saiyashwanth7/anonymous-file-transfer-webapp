from fastapi import FastAPI,Depends,UploadFile,Form,BackgroundTasks,Path,HTTPException
from fastapi.responses import FileResponse
from starlette import status
from database import sessionLocal,engine
import models
from models import Share
from typing import Annotated
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path as PathLib

models.Base.metadata.create_all(bind=engine)

def get_db():
    db=sessionLocal()
    try:
        yield db
    finally:
        db.close() 
        
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)

app=FastAPI()

db_dependency=Annotated[Session,Depends(get_db)]

def cleanup(filepath:str,db,filerequest):
    try:
        db.delete(filerequest)
        db.commit()
        os.remove(filepath)
    except Exception as e:
        print(e)
        
        
@app.get('/')
async def read_db(db:db_dependency):
    return db.query(Share).all()

@app.post('/upload-file')
async def upload_file(db:db_dependency,fileupload:UploadFile,title:str=Form(...)):
    if not fileupload.filename:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,detail="Upload a File")
    
    #here the file type and the new name are joined
    file_type=PathLib(fileupload.filename).suffix
    new_name=f"{title}{file_type}"

    unique_name=f"{str(uuid.uuid4())}_{new_name}"
    
    #created a path to store the uploaded file below
    file_path=os.path.join(UPLOAD_DIR,unique_name)
    
    try:
        #lets first add the file into local storage
        #Now we will write the uploaded file into the local storage file path
        with open(f"{file_path}","wb") as f:
            while chunk:= await fileupload.read(1024*1024):
                f.write(chunk)
                #here we are using chunks to support larger data
                
        #added the file name and path into DB
        new_file=Share(file_name=new_name,file_path=file_path)
        db.add(new_file)
        db.commit()
        
        return {"status": "uploaded", "file_id": new_file.id}
    
    except Exception as e:
        if os.path(file_path):
            os.remove(file_path)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Db operation error")
    
       

@app.get('/download-file/{file_id}')
async def download_file(db:db_dependency,background_taska:BackgroundTasks,file_id:int=Path(...,ge=1)):
    filerequest=db.query(Share).filter(Share.id==file_id).first()
    if not filerequest:
        raise HTTPException(status_code=404,detail="File Not Found")
    background_taska.add_task(cleanup,filerequest.file_path,db,filerequest)
    return FileResponse(path=filerequest.file_path,filename=filerequest.file_name,media_type='application/octet-stream')