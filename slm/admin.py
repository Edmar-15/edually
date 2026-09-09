from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Subject,
    Module,
    PersonalMaterial,
    HighlightAnswer,
    HighlightAnnotation,
)


# ============================================================
# MODULE INLINE
# ============================================================

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0

    fields = (
        "module_number",
        "module_name",
        "file",
        "is_archived",
        "updated_at",
    )

    readonly_fields = (
        "updated_at",
    )

    ordering = (
        "module_number",
    )


# ============================================================
# SUBJECT ADMIN
# ============================================================

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):

    list_display = (
        "subject_code",
        "subject_name",
        "year",
        "author",
        "module_count",
        "is_archived",
        "updated_at",
    )

    list_filter = (
        "year",
        "is_archived",
        "updated_at",
    )

    search_fields = (
        "subject_code",
        "subject_name",
        "author__username",
        "author__email",
    )

    ordering = (
        "subject_code",
    )

    list_per_page = 25

    autocomplete_fields = (
        "author",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = (
        ModuleInline,
    )

    fieldsets = (
        (
            "Subject Information",
            {
                "fields": (
                    "subject_code",
                    "subject_name",
                    "year",
                    "author",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_archived",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(description="Modules", ordering="modules")
    def module_count(self, obj):
        return obj.modules.count()


# ============================================================
# MODULE ADMIN
# ============================================================

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):

    list_display = (
        "module_number",
        "module_name",
        "subject",
        "file_type",
        "has_extracted_html",
        "is_archived",
        "updated_at",
    )

    list_filter = (
        "subject",
        "is_archived",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "module_name",
        "subject__subject_code",
        "subject__subject_name",
    )

    ordering = (
        "subject",
        "module_number",
    )

    list_per_page = 25

    autocomplete_fields = (
        "subject",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "extracted_html_status",
    )

    fieldsets = (
        (
            "Module Information",
            {
                "fields": (
                    "subject",
                    "module_number",
                    "module_name",
                    "file",
                )
            },
        ),
        (
            "Extracted Content",
            {
                "fields": (
                    "extracted_html",
                    "extracted_html_status",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_archived",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(description="File type")
    def file_type(self, obj):
        name = (obj.file.name or "").lower()

        if name.endswith(".pdf"):
            return "PDF"

        if name.endswith((".doc", ".docx", ".rtf")):
            return "Word"

        if name.endswith((".ppt", ".pptx", ".key")):
            return "PowerPoint"

        return "Other"

    @admin.display(description="Extracted HTML")
    def has_extracted_html(self, obj):
        if obj.extracted_html:
            return format_html(
                '<span style="color:#198754;font-weight:600;">✓ Yes</span>'
            )

        return format_html(
            '<span style="color:#dc3545;font-weight:600;">✕ No</span>'
        )

    @admin.display(description="Extraction status")
    def extracted_html_status(self, obj):
        if not obj.extracted_html:
            return format_html(
                '<strong style="color:#dc3545;">No extracted content</strong>'
            )

        return format_html(
            '<strong style="color:#198754;">Extracted content available</strong>'
        )


# ============================================================
# PERSONAL MATERIAL
# ============================================================

@admin.register(PersonalMaterial)
class PersonalMaterialAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "author",
        "visibility",
        "has_extracted_html",
        "is_archived",
        "updated_at",
    )

    list_filter = (
        "visibility",
        "is_archived",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "author__username",
        "author__email",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    autocomplete_fields = (
        "author",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Material",
            {
                "fields": (
                    "title",
                    "author",
                    "file",
                    "visibility",
                )
            },
        ),
        (
            "Extracted Content",
            {
                "fields": (
                    "extracted_html",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_archived",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(description="Extracted HTML")
    def has_extracted_html(self, obj):
        return bool(obj.extracted_html)


# ============================================================
# HIGHLIGHT ANSWERS
# ============================================================

@admin.register(HighlightAnswer)
class HighlightAnswerAdmin(admin.ModelAdmin):

    list_display = (
        "query",
        "owner",
        "target",
        "offsets",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "query",
        "owner__username",
        "owner__email",
        "answer_simplified",
        "answer_technical",
        "module__module_name",
        "module__subject__subject_code",
        "personal_material__title",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    autocomplete_fields = (
        "module",
        "personal_material",
        "owner",
    )

    readonly_fields = (
        "created_at",
    )

    fieldsets = (
        (
            "Highlight",
            {
                "fields": (
                    "query",
                    "owner",
                    "module",
                    "personal_material",
                    "start_offset",
                    "end_offset",
                )
            },
        ),
        (
            "AI Answers",
            {
                "fields": (
                    "answer_simplified",
                    "answer_technical",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(description="Target")
    def target(self, obj):
        if obj.module:
            return str(obj.module)

        if obj.personal_material:
            return str(obj.personal_material)

        return "—"

    @admin.display(description="Offsets")
    def offsets(self, obj):
        if obj.start_offset is None or obj.end_offset is None:
            return "—"

        return f"{obj.start_offset} → {obj.end_offset}"


# ============================================================
# HIGHLIGHT ANNOTATIONS
# ============================================================

@admin.register(HighlightAnnotation)
class HighlightAnnotationAdmin(admin.ModelAdmin):

    list_display = (
        "query",
        "owner",
        "target",
        "offsets",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "query",
        "note",
        "owner__username",
        "owner__email",
        "module__module_name",
        "module__subject__subject_code",
        "personal_material__title",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    autocomplete_fields = (
        "module",
        "personal_material",
        "owner",
    )

    readonly_fields = (
        "created_at",
    )

    fieldsets = (
        (
            "Highlight",
            {
                "fields": (
                    "query",
                    "owner",
                    "module",
                    "personal_material",
                    "start_offset",
                    "end_offset",
                )
            },
        ),
        (
            "Annotation",
            {
                "fields": (
                    "note",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    @admin.display(description="Target")
    def target(self, obj):
        if obj.module:
            return str(obj.module)

        if obj.personal_material:
            return str(obj.personal_material)

        return "—"

    @admin.display(description="Offsets")
    def offsets(self, obj):
        if obj.start_offset is None or obj.end_offset is None:
            return "—"

        return f"{obj.start_offset} → {obj.end_offset}"