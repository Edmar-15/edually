from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string

# Create your views here.
@login_required(login_url='account:login')
def slmlists(request):
    tabs = [
        {
            "title": "Self Learning Modules",
            "description":'All public modules you can enrol in',
            "content": render_to_string("components/tabs/tab_self.html"),
        },
        {
            "title": "My SLMs",
            "description":'Your own created modules',
            "content": render_to_string("components/tabs/tab_my_slms.html"),
        },
        {
            "title": "My Learning Materials",
            "description":'Notes, PDFs, videos you uploaded',
            "content": render_to_string("components/tabs/tab_learning_materials.html"),
        },
        {
            "title": "Public Learning Materials",
            "description":'Resources shared by the community',
            "content": render_to_string("components/tabs/tab_public_materials.html"),
        },
    ]
    
    return render(request, 'slm/slms.html', {"tabs": tabs})