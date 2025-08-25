import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging
from typing import Generator
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

# For testing, you might want to use SQLite
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///./test_clinic_ai.db"
)

# Determine if we're in test mode
TESTING = os.getenv("TESTING", "false").lower() == "true"

# Use test database if in testing mode
if TESTING:
    SQLALCHEMY_DATABASE_URL = TEST_DATABASE_URL
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=True  # Set to False in production
    )
else:
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=300,    # Recycle connections every 5 minutes
        echo=False  # Set to True for debugging SQL queries
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Create metadata instance for migrations
metadata = MetaData()


def get_database_session() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    This will be used with FastAPI's Depends() function.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """
    Create all tables in the database.
    This should only be used for initial setup or testing.
    In production, use Alembic migrations.
    """
    try:
        # Import models to ensure they are registered with Base
        from models import (
            Clinic, Patient, Staff, Appointment, Call, 
            KnowledgeBase, InsurancePlan, CallAnalytics, SystemLog
        )
        
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def drop_tables():
    """
    Drop all tables in the database.
    WARNING: This will delete all data!
    Only use for testing or complete reset.
    """
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise

def check_database_connection() -> bool:
    """
    Check if database connection is working.
    Returns True if connection is successful, False otherwise.
    """
    try:
        # Try to execute a simple query
        with engine.connect() as connection:
            from sqlalchemy import text
            connection.execute(text("SELECT 1"))
            connection.commit()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def get_database_info() -> dict:
    """
    Get information about the database connection.
    Useful for health checks and debugging.
    """
    try:
        info = {
            "url": SQLALCHEMY_DATABASE_URL.split("@")[-1] if "@" in SQLALCHEMY_DATABASE_URL else "SQLite",
            "driver": engine.driver,
            "pool_size": engine.pool.size() if hasattr(engine.pool, 'size') else "N/A",
            "checked_in": engine.pool.checkedin() if hasattr(engine.pool, 'checkedin') else "N/A",
            "checked_out": engine.pool.checkedout() if hasattr(engine.pool, 'checkedout') else "N/A",
            "connected": check_database_connection()
        }
        return info
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return {"error": str(e), "connected": False}

class DatabaseManager:
    """
    Database manager class for handling common database operations.
    """
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return SessionLocal()
    
    def create_session_context(self):
        """
        Create a context manager for database sessions.
        Usage:
            with db_manager.create_session_context() as session:
                # Use session here
        """
        return self.session_context()
    
    def session_context(self):
        """Context manager for database sessions."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def execute_raw_sql(self, sql: str, params: dict = None):
        """Execute raw SQL query. Use with caution."""
        try:
            with self.engine.connect() as connection:
                if params:
                    result = connection.execute(sql, params)
                else:
                    result = connection.execute(sql)
                return result.fetchall()
        except Exception as e:
            logger.error(f"Error executing raw SQL: {e}")
            raise
    
    def backup_database(self, backup_path: str = None):
        """
        Create a database backup (PostgreSQL only).
        For SQLite, you can just copy the file.
        """
        if TESTING or "sqlite" in SQLALCHEMY_DATABASE_URL:
            logger.warning("Backup not implemented for SQLite in this example")
            return False
        
        try:
            import subprocess
            
            # Parse database URL for pg_dump
            # This is a basic example - in production, use more robust parsing
            if not backup_path:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"clinic_ai_backup_{timestamp}.sql"
            
            # Extract database info from URL
            # DATABASE_URL format: postgresql://user:password@host:port/database
            url_parts = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "").split("/")
            database_name = url_parts[-1]
            connection_parts = url_parts[0].split("@")
            user_pass = connection_parts[0].split(":")
            host_port = connection_parts[1].split(":")
            
            username = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ""
            host = host_port[0]
            port = host_port[1] if len(host_port) > 1 else "5432"
            
            # Run pg_dump
            env = os.environ.copy()
            if password:
                env["PGPASSWORD"] = password
            
            cmd = [
                "pg_dump",
                "-h", host,
                "-p", port,
                "-U", username,
                "-f", backup_path,
                database_name
            ]
            
            subprocess.run(cmd, env=env, check=True)
            logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return False

# Create a global database manager instance
db_manager = DatabaseManager()

# Dependency function for FastAPI
def get_db():
    """
    FastAPI dependency function to get database session.
    Use this in your route handlers:
    
    @app.get("/items/")
    def read_items(db: Session = Depends(get_db)):
        # Use db session here
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database dependency error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# Database initialization function
def init_database():
    """
    Initialize the database.
    This function should be called when starting the application.
    """
    try:
        logger.info("Initializing database...")
        
        # Check if connection works
        if not check_database_connection():
            raise Exception("Cannot connect to database")
        
        # In production, you'll use Alembic migrations instead
        # create_tables()  # Uncomment for initial setup without Alembic
        
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# Utility functions for common database operations
def get_or_create(session: Session, model, defaults=None, **kwargs):
    """
    Get an existing record or create a new one.
    
    Args:
        session: Database session
        model: SQLAlchemy model class
        defaults: Dict of default values for creation
        **kwargs: Filter criteria
    
    Returns:
        Tuple of (instance, created_flag)
    """
    try:
        instance = session.query(model).filter_by(**kwargs).first()
        if instance:
            return instance, False
        else:
            params = dict((k, v) for k, v in kwargs.items())
            if defaults:
                params.update(defaults)
            instance = model(**params)
            session.add(instance)
            session.commit()
            return instance, True
    except Exception as e:
        session.rollback()
        logger.error(f"Error in get_or_create: {e}")
        raise

def safe_delete(session: Session, instance):
    """
    Safely delete an instance with error handling.
    
    Args:
        session: Database session
        instance: Model instance to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        session.delete(instance)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting instance: {e}")
        return False

def bulk_insert(session: Session, model, data_list: list):
    """
    Bulk insert data for better performance.
    
    Args:
        session: Database session
        model: SQLAlchemy model class
        data_list: List of dictionaries with data to insert
    
    Returns:
        Number of records inserted
    """
    try:
        session.bulk_insert_mappings(model, data_list)
        session.commit()
        return len(data_list)
    except Exception as e:
        session.rollback()
        logger.error(f"Error in bulk insert: {e}")
        raise