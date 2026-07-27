# core/views.py
import os
from pathlib import Path

from django.conf import settings as django_settings   # <- note the alias
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import render


# --------------------------------------------------------------
# 1️⃣  Manifest (served as JSON with the correct MIME type)
# --------------------------------------------------------------
def manifest(request):
    """
    Returns the static file ``static/manifest.json`` with the MIME type
    ``application/manifest+json`` that browsers expect for a Web‑App
    Manifest.
    """
    manifest_path = Path(django_settings.BASE_DIR) / "static" / "manifest.json"

    if not manifest_path.is_file():
        raise Http404("Manifest file not found")

    # Read the file once per request – it’s tiny, so fine.
    data = manifest_path.read_text(encoding="utf-8")
    return HttpResponse(data, content_type="application/manifest+json")


# --------------------------------------------------------------
# 2️⃣  Service‑worker (served as a normal JS file)
# --------------------------------------------------------------
def service_worker(request):
    """
    Returns ``static/service-worker.js`` with a proper JavaScript MIME type.
    The response is cache‑friendly – we set a long max‑age; you can
    bust the cache by adding a query‑string (e.g. ?v=20240801) when you
    register the worker.
    """
    sw_path = Path(django_settings.BASE_DIR) / "static" / "service-worker.js"

    if not sw_path.is_file():
        raise Http404("Service‑worker file not found")

    # FileResponse streams the file efficiently.
    response = FileResponse(open(sw_path, "rb"), content_type="application/javascript")
    # Cache the worker for a year – the query‑string version bump will
    # force a refresh when you need it.
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


# --------------------------------------------------------------
# 3️⃣  Offline fallback page (used by the worker)
# --------------------------------------------------------------
def offline(request):
    """
    Very small template that tells the user they are offline.
    Must be reachable without any authentication or DB queries.
    """
    return render(request, "offline.html", status=200)
