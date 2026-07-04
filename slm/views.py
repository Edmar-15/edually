import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import ValidationError
from django.db import models
from .models import Subject, Module, PersonalMaterial
import os
from .content_extractor import extract_content
import logging as logger


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
    
def module_to_dict(module, request_user=None):
    """
    Convert a Module instance into the flat dict the front‑end expects.
    """
    return {
        "id": module.id,
        "subject_id": module.subject_id,
        "subject_code": module.subject.subject_code,
        "module_number": module.module_number,
        "module_name": module.module_name,
        "file_url": module.file.url if module.file else "",
        "extracted_html": module.extracted_html or "",   # <-- NEW
        "is_owner": request_user is not None and module.subject.author_id == request_user.id,
        "created_at": getattr(module, "created_at", "").isoformat() if hasattr(module, "created_at") else "",
        "updated_at": getattr(module, "updated_at", "").isoformat() if hasattr(module, "updated_at") else "",
    }


# -----------------------------------------------------------------
# Helper – ensure an uploaded file is one of the three allowed types
# -----------------------------------------------------------------
def validate_module_file(file_obj):
    """
    Raises ``ValidationError`` if ``file_obj`` does not have an allowed
    extension (pdf, doc, docx, ppt, pptx).  The check is based on the
    filename – Django’s ``FileField`` already stores the original name.
    """
    if not file_obj:
        raise ValidationError("No file provided")

    allowed = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported file type “{ext}”. Allowed types: pdf, doc, docx, ppt, pptx."
        )
    return True


@require_GET
@ensure_csrf_cookie
def api_module_list(request, subject_id):
    """
    GET /slm/api/subjects/<subject_id>/modules/?page=1
    Returns the same pagination meta‑structure that the subject list does.
    """
    subject = get_object_or_404(Subject, pk=subject_id)
    qs = Module.objects.filter(subject=subject).order_by("module_number")

    paginator = Paginator(qs, PAGE_SIZE)          # reuse PAGE_SIZE from above
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    results = [
        module_to_dict(m, request_user=request.user)
        for m in page_obj.object_list
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


@login_required
@require_http_methods(["POST"])
def api_module_create(request, subject_id):
    """POST /slm/api/subjects/<subject_id>/modules/  (multipart/form-data)"""
    subject = get_object_or_404(Subject, pk=subject_id)

    if subject.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    module_number = request.POST.get("module_number")
    module_name   = request.POST.get("module_name", "").strip()
    file_obj      = request.FILES.get("file")

    # ---- validation -------------------------------------------------
    try:
        module_number = int(module_number)
        if module_number <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"error": "module_number must be a positive integer"}, status=400)

    if not module_name:
        return JsonResponse({"error": "module_name is required"}, status=400)

    # ---- file‑type validation (still done in the helper) ------------
    try:
        validate_module_file(file_obj)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # ---- create the Model row ---------------------------------------
    try:
        module = Module.objects.create(
            subject=subject,
            module_number=module_number,
            module_name=module_name,
            file=file_obj,
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # ---- 1️⃣ Extract content -----------------------------------------
    try:
        html = extract_content(module.file)
        module.extracted_html = html
        module.save(update_fields=["extracted_html"])
    except ValueError as exc:
        # Extraction failed – we keep the file, just warn the client.
        logger.warning("Extraction failed for module %s: %s", module.id, exc)

    # ---- 2️⃣ Return fresh payload ------------------------------------
    return JsonResponse(
        module_to_dict(module, request_user=request.user),
        status=201,
    )
# -------------------------------------------------------


# -----------------------------------------------------------------
# 6️⃣  UPDATE – PUT a module (JSON only – no file change)
# -----------------------------------------------------------------
@login_required
@require_http_methods(["PUT", "PATCH"])
def api_module_update(request, pk):
    """PUT /slm/api/modules/<pk>/  (JSON payload)"""
    try:
        module = Module.objects.select_related("subject").get(pk=pk)
    except Module.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    # Only the *author* of the *subject* may edit the module
    if module.subject.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # -------------------------------------------------------------
    # 1️⃣  Validate & apply *module_number* (must stay unique per subject)
    # -------------------------------------------------------------
    if "module_number" in payload:
        try:
            new_num = int(payload["module_number"])
            if new_num <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse(
                {"error": "module_number must be a positive integer"},
                status=400,
            )

        # Is there another module in the SAME subject with this number?
        conflict = (
            Module.objects.filter(subject=module.subject, module_number=new_num)
            .exclude(pk=module.pk)
            .exists()
        )
        if conflict:
            return JsonResponse(
                {
                    "error": "module_number already exists for this subject – choose another number"
                },
                status=400,
            )

        module.module_number = new_num

    # -------------------------------------------------------------
    # 2️⃣  Validate *module_name*
    # -------------------------------------------------------------
    if "module_name" in payload:
        name = payload["module_name"].strip()
        if not name:
            return JsonResponse(
                {"error": "module_name cannot be blank"}, status=400
            )
        module.module_name = name

    # (file updates are handled by the separate file‑replace endpoint)

    try:
        module.save()
    except Exception as exc:
        # Any unexpected DB error – return its message
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(module_to_dict(module, request_user=request.user))


@login_required
@require_http_methods(["DELETE"])
def api_module_delete(request, pk):
    """DELETE /slm/api/modules/<pk>/delete/"""
    try:
        module = Module.objects.select_related("subject").get(pk=pk)
    except Module.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if module.subject.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    module.delete()
    return JsonResponse({}, status=204)


@login_required
@require_http_methods(["POST"])
def api_module_file_replace(request, pk):
    """
    POST /slm/api/modules/<pk>/file/   (multipart)

    1️⃣  Validate ownership + file type (same as in `api_module_create`).
    2️⃣  Replace the file on the model instance.
    3️⃣  **Run the content extractor** on the newly‑uploaded file.
    4️⃣  Store the resulting HTML in ``module.extracted_html``.
    5️⃣  Return a fresh JSON payload (including the new ``extracted_html``).

    The front‑end already calls this endpoint from the edit‑modal, so after
    a successful request it will simply reload the module list and display the
    updated preview.
    """
    # -------------------------------------------------------------
    # 1️⃣  Grab the module & check permission
    # -------------------------------------------------------------
    try:
        module = Module.objects.select_related("subject").get(pk=pk)
    except Module.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if module.subject.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    # -------------------------------------------------------------
    # 2️⃣  Validate the uploaded file
    # -------------------------------------------------------------
    file_obj = request.FILES.get("file")
    if not file_obj:
        return JsonResponse({"error": "File missing"}, status=400)

    try:
        validate_module_file(file_obj)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # -------------------------------------------------------------
    # 3️⃣  Swap the file on the model instance
    # -------------------------------------------------------------
    module.file = file_obj
    module.save()

    # -------------------------------------------------------------
    # 4️⃣  Run the extractor and store the HTML preview
    # -------------------------------------------------------------
    try:
        html = extract_content(module.file)
        module.extracted_html = html
        # ``update_fields`` ensures we only touch the HTML column – the file
        # field is already saved.
        module.save(update_fields=["extracted_html"])
    except ValueError as exc:          # extraction failed – keep the file
        logger.warning(
            "Extraction failed after file replace for module %s: %s",
            module.id,
            exc,
        )
        # We *don’t* abort the request – the file was successfully stored.
        # The client will simply see the old (or empty) preview.

    # -------------------------------------------------------------
    # 5️⃣  Return the fresh payload (includes the new HTML)
    # -------------------------------------------------------------
    return JsonResponse(
        module_to_dict(module, request_user=request.user)
    )


@login_required
def module_detail(request, subject_id, module_id):
    """
    Render a page that shows the extracted HTML of a module.
    The original file can still be downloaded.
    """
    subject = get_object_or_404(Subject, pk=subject_id)
    module  = get_object_or_404(Module, pk=module_id, subject=subject)

    context = {
        "subject": subject,
        "module": module,
    }
    return render(request, "slm/module_detail.html", context)


# -----------------------------------------------------------------
# PERSONAL MATERIAL – helpers
# -----------------------------------------------------------------
def personal_material_to_dict(pm, request_user=None):
    """
    Serialise a PersonalMaterial for the JS widget.
    """
    return {
        "id": pm.id,
        "title": pm.title,
        "author_id": pm.author_id,
        "author_name": str(pm.author),
        "visibility": pm.visibility,
        "visibility_display": pm.get_visibility_display(),
        "file_url": pm.file.url if pm.file else "",
        "extracted_html": pm.extracted_html or "",
        "is_owner": request_user is not None and pm.author_id == request_user.id,
        "created_at": pm.created_at.isoformat(),
        "updated_at": pm.updated_at.isoformat(),
    }


# -------------------------------------------------------------
# 1️⃣  LIST – GET (paginated)
# -------------------------------------------------------------
@require_GET
@ensure_csrf_cookie
def api_personal_material_list(request):
    """
    GET /slm/api/personal-materials/?page=1&visibility=all|public

    * When the user is **authenticated**, we return:
        – all his/her own materials (both PRIVATE and PUBLIC)
        – plus, if ``visibility=public`` is supplied, every PUBLIC material
          from any user (i.e. the “Public Learning Materials” page).

    * When the user is **anonymous**, we only return PUBLIC materials.
    """
    # -----------------------------------------------------------------
    # 1️⃣  Determine the filter
    # -----------------------------------------------------------------
    visibility = request.GET.get("visibility", "own")   # own | public | all
    qs = PersonalMaterial.objects.all().select_related("author")

    if request.user.is_authenticated:
        if visibility == "own":
            qs = qs.filter(author=request.user)                 # only mine
        elif visibility == "public":
            qs = qs.filter(visibility=PersonalMaterial.Visibility.PUBLIC)
        else:   # “all” – my + public from others
            qs = qs.filter(
                models.Q(author=request.user) |
                models.Q(visibility=PersonalMaterial.Visibility.PUBLIC)
            )
    else:
        # anonymous users can only see PUBLIC things
        qs = qs.filter(visibility=PersonalMaterial.Visibility.PUBLIC)

    file_type = request.GET.get("type")
    if file_type in {"pdf", "doc", "ppt"}:
        if file_type == "pdf":
            qs = qs.filter(file__iendswith=".pdf")
        elif file_type == "doc":
            qs = qs.filter(models.Q(file__iendswith=".doc") | models.Q(file__iendswith=".docx"))
        elif file_type == "ppt":
            qs = qs.filter(models.Q(file__iendswith=".ppt") | models.Q(file__iendswith=".pptx"))

    # -----------------------------------------------------------------
    # 2️⃣  Pagination (reuse PAGE_SIZE from the top of the file)
    # -----------------------------------------------------------------
    paginator = Paginator(qs.order_by("-created_at"), PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    payload = {
        "results": [
            personal_material_to_dict(pm, request_user=request.user)
            for pm in page_obj.object_list
        ],
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "has_previous": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "previous_page_number": page_obj.previous_page_number()
        if page_obj.has_previous()
        else None,
        "next_page_number": page_obj.next_page_number()
        if page_obj.has_next()
        else None,
    }
    return JsonResponse(payload, safe=False)


# -------------------------------------------------------------
# 2️⃣  CREATE – POST (multipart/form‑data)
# -------------------------------------------------------------
@login_required
@require_http_methods(["POST"])
def api_personal_material_create(request):
    """
    POST /slm/api/personal-materials/create/
    Expected fields:
        title          – text
        visibility     – “PR” or “PU”
        file           – uploaded document (pdf/docx/pptx)
    """
    title = request.POST.get("title", "").strip()
    visibility = request.POST.get("visibility", "").strip()
    file_obj = request.FILES.get("file")

    # ---- basic validation -------------------------------------------------
    if not title:
        return JsonResponse({"error": "Title is required"}, status=400)

    if visibility not in dict(PersonalMaterial.Visibility.choices):
        return JsonResponse(
            {"error": "Invalid visibility – choose Private or Public"},
            status=400,
        )

    try:
        validate_module_file(file_obj)          # reuse the same helper as modules
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # ---- create the model -------------------------------------------------
    pm = PersonalMaterial.objects.create(
        title=title,
        author=request.user,
        visibility=visibility,
        file=file_obj,
    )

    # ---- run content extractor (optional) --------------------------------
    try:
        html = extract_content(pm.file)
        pm.extracted_html = html
        pm.save(update_fields=["extracted_html"])
    except ValueError as exc:
        logger.warning("Content extraction failed for PersonalMaterial %s: %s", pm.id, exc)

    return JsonResponse(
        personal_material_to_dict(pm, request_user=request.user),
        status=201,
    )


# -------------------------------------------------------------
# 3️⃣  UPDATE – PUT / PATCH (JSON only – metadata)
# -------------------------------------------------------------
@login_required
@require_http_methods(["PUT", "PATCH"])
def api_personal_material_update(request, pk):
    """PUT /slm/api/personal-materials/<pk>/ – edit title / visibility."""
    pm = get_object_or_404(PersonalMaterial, pk=pk)

    if pm.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    if "title" in payload:
        new_title = payload["title"].strip()
        if not new_title:
            return JsonResponse({"error": "Title cannot be blank"}, status=400)
        pm.title = new_title

    if "visibility" in payload:
        new_vis = payload["visibility"]
        if new_vis not in dict(PersonalMaterial.Visibility.choices):
            return JsonResponse({"error": "Invalid visibility value"}, status=400)
        pm.visibility = new_vis

    pm.save()
    return JsonResponse(personal_material_to_dict(pm, request_user=request.user))


# -------------------------------------------------------------
# 4️⃣  DELETE – DELETE
# -------------------------------------------------------------
@login_required
@require_http_methods(["DELETE"])
def api_personal_material_delete(request, pk):
    """DELETE /slm/api/personal-materials/<pk>/delete/"""
    pm = get_object_or_404(PersonalMaterial, pk=pk)

    if pm.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    pm.delete()
    return JsonResponse({}, status=204)


# -------------------------------------------------------------
# 5️⃣  FILE REPLACE – POST (multipart)
# -------------------------------------------------------------
@login_required
@require_http_methods(["POST"])
def api_personal_material_file_replace(request, pk):
    """
    POST /slm/api/personal-materials/<pk>/file/
    Allows the owner to upload a new file for an existing material.
    Content extraction is re‑run and the new HTML is saved.
    """
    pm = get_object_or_404(PersonalMaterial, pk=pk)

    if pm.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    file_obj = request.FILES.get("file")
    if not file_obj:
        return JsonResponse({"error": "File missing"}, status=400)

    try:
        validate_module_file(file_obj)
    except ValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # -----------------------------------------------------------------
    # Replace the file and re‑extract
    # -----------------------------------------------------------------
    pm.file = file_obj
    pm.save()                         # stores the file

    try:
        html = extract_content(pm.file)
        pm.extracted_html = html
        pm.save(update_fields=["extracted_html"])
    except ValueError as exc:
        logger.warning(
            "Content extraction failed after file replace for PersonalMaterial %s: %s",
            pm.id,
            exc,
        )
        # continue – the file is still replaced

    return JsonResponse(personal_material_to_dict(pm, request_user=request.user))


@login_required
def personal_material_detail(request, pk):
    """
    Show the extracted HTML preview (if any) for a PersonalMaterial.
    * Owners can view private or public items.
    * Other users see only PUBLIC items.
    """
    pm = get_object_or_404(PersonalMaterial, pk=pk)

    # Visibility guard – non‑owners may only see PUBLIC items
    if pm.visibility == PersonalMaterial.Visibility.PRIVATE and pm.author_id != request.user.id:
        return JsonResponse({"error": "Permission denied"}, status=403)

    context = {
        "pm": pm,                 # used by the template
    }
    return render(request, "slm/personal_material_detail.html", context)