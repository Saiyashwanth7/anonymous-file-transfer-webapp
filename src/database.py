from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

SQL_ALCHEMY_DB = "sqlite:///app.db"

engine = create_engine(SQL_ALCHEMY_DB, connect_args={"check_same_thread": False})

sessionLocal=sessionmaker(autocommit=False,autoflush=False,bind=engine)

Base=declarative_base()