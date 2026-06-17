from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required(login_url='account:login')
def slmlists(request):
    return render(request, 'slm/slms.html')