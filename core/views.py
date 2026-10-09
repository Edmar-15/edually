import os
from pathlib import Path

from django.conf import settings as django_settings
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import render
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.template.loader import render_to_string


def manifest(request):
    """Serve the PWA manifest with its expected MIME type."""
    manifest_path = Path(django_settings.BASE_DIR) / "static" / "manifest.json"

    if not manifest_path.is_file():
        raise Http404("Manifest file not found")

    data = manifest_path.read_text(encoding="utf-8")
    return HttpResponse(data, content_type="application/manifest+json")


def service_worker(request):
    """Serve the service worker with the configured version and cache headers."""
    sw_path = Path(django_settings.BASE_DIR) / "static" / "service-worker.js"

    if not sw_path.is_file():
        raise Http404("Service‑worker file not found")

    sw_source = sw_path.read_text(encoding="utf-8")
    sw_source = sw_source.replace("{{ PWA_SW_VERSION }}", str(django_settings.PWA_SW_VERSION))

    response = HttpResponse(sw_source, content_type="application/javascript")
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def offline(request):
    """Render the offline fallback page."""
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