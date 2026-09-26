# core/views.py
import os
from pathlib import Path

from django.conf import settings as django_settings   # <- note the alias
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import render
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.template.loader import render_to_string


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

    sw_source = sw_path.read_text(encoding="utf-8")
    sw_source = sw_source.replace("{{ PWA_SW_VERSION }}", str(django_settings.PWA_SW_VERSION))

    response = HttpResponse(sw_source, content_type="application/javascript")
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


def _error_page(status_code, title, message):
    content = render_to_string(
        "errors/error.html",
        {
            "status_code": status_code,
            "title": title,
            "message": message,
        },
    )
    return HttpResponse(content, status=status_code)


def bad_request(request, exception=None):
    return _error_page(
        400, "Bad request", "The request could not be understood. Please check it and try again."
    )


def forbidden(request, exception=None):
    return _error_page(
        403, "Access denied", "You do not have permission to view this page."
    )


def csrf_failure(request, reason=""):
    return _error_page(
        403, "Request blocked", "This request could not be verified. Refresh the page and try again."
    )


def page_not_found(request, exception=None):
    return _error_page(
        404, "Page not found", "The page may have moved, or the address may be incorrect."
    )


def server_error(request):
    return _error_page(
        500, "Something went wrong", "An unexpected error occurred. Please try again shortly."
    )


def robots_txt(request):
    content = """User-agent: *
Allow: /

Disallow: /admin/
Disallow: /account/
Disallow: /aihelper/
Disallow: /slm/api/

Sitemap: https://edually.ddns.net/sitemap.xml
"""

    return HttpResponse(content, content_type="text/plain")


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            "landing",
        ]

    def location(self, item):
        return reverse(item)