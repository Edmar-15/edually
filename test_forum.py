#!/usr/bin/env python
import os
import django
import sys

# Set Django settings module before importing Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

# Now setup Django
django.setup()

# Import after Django setup
from django.test import Client, override_settings

# Test with override_settings to ensure ALLOWED_HOSTS is set
with override_settings(ALLOWED_HOSTS=['*'], DEBUG=True):
    client = Client()
    response = client.get('/forum/')
    print(f"Status: {response.status_code}")
    if response.status_code >= 400:
        print(f"Error:")
        error_content = response.content.decode()[:2000]
        print(error_content)
    else:
        print("✓ Forum page loaded successfully!")
        response_text = response.content.decode()
        if "Community Forum" in response_text:
            print("✓ Forum template rendered correctly")
        else:
            print("✗ Forum template not rendered correctly")
            print(response_text[:500])
