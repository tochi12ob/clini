#!/usr/bin/env python3
"""
Test script to verify database connection is using the local database
"""
import os
from dotenv import load_dotenv
import database

# Load environment variables
load_dotenv()

def test_database_connection():
    print("Testing database connection...")
    print(f"DATABASE_URL from environment: {os.getenv('DATABASE_URL')}")
    print(f"SQLALCHEMY_DATABASE_URL from database.py: {database.SQLALCHEMY_DATABASE_URL}")
    
    # Test connection
    try:
        if database.check_database_connection():
            print("✅ Database connection successful!")
            
            # Get database info
            db_info = database.get_database_info()
            print(f"Database info: {db_info}")
        else:
            print("❌ Database connection failed!")
    except Exception as e:
        print(f"❌ Error testing database connection: {e}")

if __name__ == "__main__":
    test_database_connection() 