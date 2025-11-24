import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")




# --- Construct DB URL ---
if DB_HOST:  # Local run via TCP
    DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    )
else:  # Cloud Run socket
    DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@/{DB_NAME}"
        f"?unix_socket=/cloudsql/{INSTANCE_CONNECTION_NAME}"
    )

# --- Create SQLAlchemy engine & session ---
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,    # avoid stale connections
    pool_recycle=280,      # Cloud SQL disconnect timeout safety
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
