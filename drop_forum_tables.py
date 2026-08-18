#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Disable foreign keys to allow dropping tables
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    
    # Drop forum tables
    cursor.execute("DROP TABLE IF EXISTS forum_replyupvote")
    cursor.execute("DROP TABLE IF EXISTS forum_postupvote")
    cursor.execute("DROP TABLE IF EXISTS forum_reply")
    cursor.execute("DROP TABLE IF EXISTS forum_post")
    cursor.execute("DROP TABLE IF EXISTS forum_category")
    
    # Re-enable foreign key checks
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    
    # Clear migration records
    cursor.execute("DELETE FROM django_migrations WHERE app = 'forum'")
    
    print("✓ Forum tables dropped successfully")
    print("✓ Forum migration records cleared")

