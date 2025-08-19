from sqlalchemy import Column,Integer,String,DATETIME,ForeignKey
from database import Base
from datetime import timezone,datetime,timedelta
import secrets

class Share(Base):
    __tablename__="filestorage"
    id=Column(Integer,primary_key=True,index=True)
    file_name=Column(String)
    file_path=Column(String)
    token=Column(String,unique=True,index=True,default=lambda: secrets.token_urlsafe(32))
    created=Column(DATETIME,default=lambda: datetime.now(timezone.utc))
    expires=Column(DATETIME,default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    file_type=Column(String)

class GroupShare(Base):
    __tablename__="grouptable"
    id=Column(Integer,primary_key=True,index=True)
    share_id=Column(String,ForeignKey('filestorage.id'))
    receiver_email=Column(String)
    token=Column(String,unique=True,index=True,default=lambda: secrets.token_urlsafe(32))
    created=Column(DATETIME,default=lambda: datetime.now(timezone.utc))
    expires=Column(DATETIME,default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))