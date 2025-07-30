from sqlalchemy import Column,Integer,String
from database import Base

class Share(Base):
    __tablename__="filestorage"
    id=Column(Integer,primary_key=True,index=True)
    file_name=Column(String,unique=True)
    file_path=Column(String)
    
