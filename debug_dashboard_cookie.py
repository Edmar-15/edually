import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from account.models import UserConsent
from slm.models import Subject, Module

settings.ALLOWED_HOSTS.append('testserver')
User = get_user_model()

User.objects.filter(email='debug_student@example.com').delete()
Subject.objects.filter(subject_code='DEBUG_GEC101').delete()
user = User.objects.create_user(email='debug_student@example.com', password='secret123', username='debug_student')
UserConsent.objects.create(user=user, version='1.0')

client = Client()
client.force_login(user)
subj = Subject.objects.create(subject_code='DEBUG_GEC101', subject_name='General Education', author=user)
mod1 = Module.objects.create(subject=subj, module_number=1, module_name='First Module', file='modules/test1.pdf')
mod2 = Module.objects.create(subject=subj, module_number=2, module_name='Second Module', file='modules/test2.pdf')

cookie_value = json.dumps([mod2.pk, mod1.pk])
client.cookies['eduallyRecentModules'] = cookie_value
print('cookie set:', cookie_value)
print('client cookies before logout:', client.cookies.items())
client.logout()
client.force_login(user)
print('client cookies after logout/login:', client.cookies.items())
response = client.get('/account/dashboard/')
print('status code:', response.status_code)
print('recent modules in session:', client.session.get('recent_modules'))
print('contains Second Module:', b'Second Module' in response.content)
print('content snippet:', response.content.decode('utf-8').split('Recently visited modules', 1)[-1][:400])
