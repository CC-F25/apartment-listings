# database.py for listings microservice
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

db_host = os.environ.get("MYSQL_HOST", "localhost")
db_user = os.environ.get("MYSQL_USER", "root")
db_pass = os.environ.get("MYSQL_PASSWORD", "your_password")
db_name = os.environ.get("MYSQL_DB", "apartment_listings")
db_port = os.environ.get("MYSQL_PORT", "3306")


if os.environ.get("DATABASE_URL"):
    DATABASE_URL = os.environ.get("DATABASE_URL")
else:
    DATABASE_URL = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
