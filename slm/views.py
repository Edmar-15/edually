import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import ValidationError
from .models import Subject, Module


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


# -----------------------------------------------------------------
# Helper – turn a Subject into the dict the front‑end expects
# -----------------------------------------------------------------
def subject_to_dict(subject, request_user=None):
    """
    Returns a flat dict that can be JSON‑encoded.
    Extra keys:
        * author_name – printable name of the author
        * is_owner    – true if request_user == author (used to show edit/delete)
    """
    return {
        "id": subject.id,
        "subject_code": subject.subject_code,
        "subject_name": subject.subject_name,
        "author_id": subject.author_id,
        "author_name": str(subject.author),
        "year": subject.year,
        "year_display": subject.get_year_display(),
        "is_owner": request_user is not None and subject.author_id == request_user.id,
        "created_at": subject.created_at.isoformat(),
        "updated_at": subject.updated_at.isoformat(),
        "detail_url": f"/slm/subjects/{subject.id}/modules/",
    }


def validate_year_choice(value):
    """
    Return the cleaned value if it belongs to Subject.YEAR_CHOICES.
    Raise ValidationError otherwise.
    """
    if value is None:
        return None                     # client omitted the key → keep default
    allowed = {c[0] for c in Subject.YEAR_CHOICES}
    if value not in allowed:
        raise ValidationError(
            f"Invalid year '{value}'. Allowed values are: {', '.join(sorted(allowed))}"
        )
    return value


# -------------------------------------------------
# 1️⃣  GET – paginated list of public subjects
# -------------------------------------------------
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

PAGE_SIZE = 9                     # 3 cards per row × 2 rows = 6 cards (matches your static layout)

@require_GET
@ensure_csrf_cookie               # sets csrftoken for later POSTs
def api_subject_list(request):
    """
    GET /slm/api/subjects/?page=1
    Returns JSON like:
    {
        "results": [ … list of subjects for this page … ],
        "page": 1,
        "total_pages": 4,
        "has_previous": false,
        "has_next": true,
        "previous_page_number": null,
        "next_page_number": 2
    }
    """
    qs = Subject.objects.select_related("author").all()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        # If the page is out of range we return the last page (empty list is also fine)
        page_obj = paginator.page(paginator.num_pages)

    # Serialize only the objects that belong to this page
    results = [
        subject_to_dict(s, request_user=request.user)
        for s in page_obj.object_list
    ]

    payload = {
        "results": results,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "has_previous": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
        "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
    }
    return JsonResponse(payload, safe=False)


# -----------------------------------------------------------------
# 2️⃣  POST – create a new subject (logged‑in users only)
# -----------------------------------------------------------------
@login_required
@require_POST
def api_subject_create(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    code = payload.get("subject_code", "").strip()
    name = payload.get("subject_name", "").strip()
    raw_year = payload.get("year")                # <-- NEW

    if not code or not name:
        return JsonResponse({"error": "Both fields are required."}, status=400)

    # ---- Validate the year choice ---------------------------------
    try:
        clean_year = validate_year_choice(raw_year)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    subject = Subject.objects.create(
        subject_code=code,
        subject_name=name,
        author=request.user,
        year=clean_year or Subject.YEAR_FIRST,    # fallback to default if omitted
    )
    return JsonResponse(
        subject_to_dict(subject, request_user=request.user),
        status=201,
    )

# -----------------------------------------------------------------
# 3️⃣  PUT – update a subject (owner only)
# -----------------------------------------------------------------
@login_required
@require_http_methods(["PUT", "PATCH"])
def api_subject_update(request, pk):
    try:
        subject = Subject.objects.get(pk=pk)
    except Subject.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if subject.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # ---- normal fields -------------------------------------------------
    if "subject_code" in payload:
        subject.subject_code = payload["subject_code"].strip()
    if "subject_name" in payload:
        subject.subject_name = payload["subject_name"].strip()

    # ---- year -----------------------------------------------------------
    if "year" in payload:
        try:
            subject.year = validate_year_choice(payload["year"])
        except ValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    subject.save()
    return JsonResponse(subject_to_dict(subject, request_user=request.user))

# -----------------------------------------------------------------
# 4️⃣  DELETE – remove a subject (owner only)
# -----------------------------------------------------------------
@login_required
@require_http_methods(["DELETE"])
def api_subject_delete(request, pk):
    try:
        subject = Subject.objects.get(pk=pk)
    except Subject.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if subject.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    subject.delete()
    return JsonResponse({}, status=204)   # empty body


def subject_modules(request, subject_id):
    """
    Renders a normal HTML page that shows **all modules belonging to
    the given subject**.
    """
    subject = get_object_or_404(Subject, pk=subject_id)

    # If your `Module` model has a FK called `subject` use:
    modules = Module.objects.filter(subject=subject).select_related('subject')
    # If you used a related_name on the FK you could also do:
    # modules = subject.modules.all()

    context = {
        "subject": subject,
        "modules": modules,
    }
    return render(request, "slm/subject_modules.html", context)


@require_GET
def api_subject_year_choices(request):
    """
    Returns JSON:
    {
        "choices": [
            {"value": "1", "label": "First"},
            {"value": "2", "label": "Second"},
            {"value": "3", "label": "Third"},
            {"value": "4", "label": "Four"}
        ]
    }
    """
    return JsonResponse(
        {"choices": [{"value": v, "label": l} for v, l in Subject.YEAR_CHOICES]}
    )