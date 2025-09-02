import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import os
from dotenv import load_dotenv
from pathlib import Path

# Point to .env inside src
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Debug print
print("DATABASE_URL from env:", os.getenv("DATABASE_URL"))

SQL_ALCHEMY_DB = os.getenv("DATABASE_URL")

if not SQL_ALCHEMY_DB:
    raise ValueError("DATABASE_URL is not set. Check your .env file.")

engine = create_engine(SQL_ALCHEMY_DB)

sessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
