from fastapi import FastAPI,HTTPException,status
from database import engine,sessionLocal
from models import Base,GroupShare,Share
from routers import file_share,group_share
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime,timezone
from contextlib import asynccontextmanager
import asyncio

Base.metadata.create_all(bind=engine)


async def auto_cleanup_Share():
    while True:
        db=sessionLocal()
        try:
            current_datetime=datetime.now(timezone.utc)
            db.query(Share).filter(Share.expires<current_datetime).delete()
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"{e} occured")
        finally:
            db.close()
        await asyncio.sleep(600)
        
async def auto_cleanup_GroupShare():
    while True:
        db=sessionLocal()
        try:
            current_datetime=datetime.now(timezone.utc)
            db.query(GroupShare).filter(GroupShare.expires<current_datetime).delete()
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"{e} occured")
        finally:
            db.close()
        await asyncio.sleep(600)
    
@asynccontextmanager
async def lifespan(app:FastAPI):
    task=asyncio.create_task(auto_cleanup_GroupShare())
    task2=asyncio.create_task(auto_cleanup_Share())
    yield
    task.cancel()
    task2.cancel()

app = FastAPI(lifespan=lifespan)
app.include_router(file_share.router)
app.include_router(group_share.router)