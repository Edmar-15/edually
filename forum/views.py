from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required(login_url='account:login')
def feed(request):
    return render(request, 'forum/feed.html')