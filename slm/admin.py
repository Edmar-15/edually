from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Subject,
    Module,
    PersonalMaterial,
    HighlightAnswer,
    HighlightAnnotation,
)


# ============================================================
# EXTRACTED CONTENT EDITOR
# ============================================================

class ExtractedHTMLTextarea(forms.Textarea):
    """
    Large HTML source editor used for extracted document content.

    The extracted content is stored as HTML and rendered by the
    student-facing SLM pages. This widget intentionally keeps the
    content as HTML instead of converting it into a rich-text format.
    """

    def __init__(self, attrs=None):
        default_attrs = {
            "rows": 40,
            "class": "edually-extracted-html-editor",
            "spellcheck": "false",
            "autocomplete": "off",
            "wrap": "off",
            "style": (
                "width: 100%; "
                "box-sizing: border-box; "
                "padding: 16px; "
                "border-radius: 8px; "
                "font-family: "
                "'SFMono-Regular', Consolas, "
                "'Liberation Mono', Menlo, monospace; "
                "font-size: 13px; "
                "line-height: 1.6; "
                "tab-size: 4; "
                "resize: vertical; "
            ),
        }

        if attrs:
            default_attrs.update(attrs)

        super().__init__(attrs=default_attrs)


class ExtractedContentFormMixin:
    """
    Shared form configuration for models containing extracted_html.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "extracted_html" in self.fields:
            self.fields["extracted_html"].widget = ExtractedHTMLTextarea(
                attrs={
                    "aria-label": "Extracted HTML content",
                }
            )

            self.fields["extracted_html"].help_text = (
                "Edit the extracted HTML shown to students. "
                "You can correct text, headings, paragraphs, lists, "
                "tables, and other extracted content here. "
                "Changes affect the extracted content only and do not "
                "modify the original uploaded file."
            )


# ============================================================
# MODULE FORM
# ============================================================

class ModuleAdminForm(ExtractedContentFormMixin, forms.ModelForm):

    class Meta:
        model = Module
        fields = "__all__"


# ============================================================
# PERSONAL MATERIAL FORM
# ============================================================

class PersonalMaterialAdminForm(
    ExtractedContentFormMixin,
    forms.ModelForm,
):

    class Meta:
        model = PersonalMaterial
        fields = "__all__"


# Phase 2E: Learning Content admin overview
class LearningContentAdminOverview:
    """Read-only list summaries; leave Django Admin CRUD and access checks intact."""

    change_list_template = "admin/slm/change_list.html"
    change_form_template = "admin/slm/change_form.html"
    overview_title = "Learning content"
    overview_description = "Find and review learning records."

    def get_overview_stats(self, request):
        qs = self.model.objects.all()
        total = qs.count()
        if self.model is Subject:
            return (
                ("Total subjects", total),
                ("Available subjects", qs.filter(is_archived=False).count()),
                ("Archived subjects", qs.filter(is_archived=True).count()),
                ("Second-year subjects", qs.filter(year=Subject.YEAR_TWO).count()),
            )
        if self.model is Module:
            return (
                ("Total modules", total),
                ("Available modules", qs.filter(is_archived=False).count()),
                ("Archived modules", qs.filter(is_archived=True).count()),
                ("Extracted content ready", qs.exclude(extracted_html="").count()),
            )
        if self.model is PersonalMaterial:
            return (
                ("Total materials", total),
                ("Private materials", qs.filter(visibility=PersonalMaterial.Visibility.PRIVATE).count()),
                ("Public materials", qs.filter(visibility=PersonalMaterial.Visibility.PUBLIC).count()),
                ("Archived materials", qs.filter(is_archived=True).count()),
            )
        return (
            ("Total records", total),
            ("Module highlights", qs.filter(module__isnull=False).count()),
            ("Personal material highlights", qs.filter(personal_material__isnull=False).count()),
        )

    def changelist_view(self, request, extra_context=None):
        if request.method == "GET" and self.has_view_or_change_permission(request):
            extra_context = {
                **(extra_context or {}),
                "edually_slm_overview": {
                    "title": self.overview_title,
                    "description": self.overview_description,
                    "stats": [
                        {"label": label, "value": value}
                        for label, value in self.get_overview_stats(request)
                    ],
                },
            }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description="Availability", ordering="is_archived")
    def availability_badge(self, obj):
        archived = obj.is_archived
        return format_html(
            '<span class="edually-slm-badge edually-slm-badge--{}">{}</span>',
            "muted" if archived else "positive",
            "Archived" if archived else "Available",
        )

    @admin.display(description="Extracted HTML")
    def extraction_badge(self, obj):
        ready = bool(obj.extracted_html)
        return format_html(
            '<span class="edually-slm-badge edually-slm-badge--{}">{}</span>',
            "positive" if ready else "warning",
            "Ready" if ready else "Not available",
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
class SubjectAdmin(LearningContentAdminOverview, admin.ModelAdmin):
    overview_title = "Learning subjects"
    overview_description = "Review subject owners, year levels, module totals, and availability."

    list_display = ("subject_identity", "year", "author", "module_count", "availability_badge", "updated_at")
    list_display_links = ("subject_identity",)

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
    search_help_text = "Search subject code, name, or owner."

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

    @admin.display(description="Modules", ordering="_edually_module_total")
    def module_count(self, obj):
        return obj._edually_module_total

    @admin.display(description="Subject", ordering="subject_code")
    def subject_identity(self, obj):
        return format_html(
            '<span class="edually-slm-primary">{}</span><span class="edually-slm-secondary">{}</span>',
            obj.subject_code, obj.subject_name,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author").annotate(
            _edually_module_total=Count("modules", distinct=True)
        )


# ============================================================
# MODULE ADMIN
# ============================================================

@admin.register(Module)
class ModuleAdmin(LearningContentAdminOverview, admin.ModelAdmin):
    overview_title = "Learning modules"
    overview_description = "Find module files, review extraction readiness, and archive status."

    form = ModuleAdminForm

    list_display = ("module_identity", "subject", "file_type", "has_extracted_html", "availability_badge", "updated_at")
    list_display_links = ("module_identity",)

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
    search_help_text = "Search module name, subject code, or subject name."

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
                "description": (
                    "<strong>Editable student content</strong><br>"
                    "The HTML below is the extracted version of the "
                    "uploaded document. This is the content displayed "
                    "on the student-facing module page.<br><br>"
                    "<strong>Important:</strong> Editing this field does "
                    "not modify the original PDF, DOCX, or PPTX file."
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
        return self.extraction_badge(obj)

    @admin.display(description="Extraction status")
    def extracted_html_status(self, obj):
        return self.extraction_badge(obj)

    @admin.display(description="Module", ordering="module_number")
    def module_identity(self, obj):
        return format_html(
            '<span class="edually-slm-primary">Module {} · {}</span>',
            obj.module_number, obj.module_name,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("subject")


# ============================================================
# PERSONAL MATERIAL
# ============================================================

@admin.register(PersonalMaterial)
class PersonalMaterialAdmin(LearningContentAdminOverview, admin.ModelAdmin):
    overview_title = "Personal learning materials"
    overview_description = "Review user-owned files, visibility, extraction readiness, and archive status."

    form = PersonalMaterialAdminForm

    list_display = ("material_identity", "author", "visibility_badge", "has_extracted_html", "availability_badge", "updated_at")
    list_display_links = ("material_identity",)

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
    search_help_text = "Search material title, owner username, or email."

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
                "description": (
                    "<strong>Editable student content</strong><br>"
                    "The HTML below is the extracted version of the "
                    "uploaded material. You can manually correct or "
                    "modify it here.<br><br>"
                    "<strong>Important:</strong> Editing this field does "
                    "not modify the original uploaded file."
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
        return self.extraction_badge(obj)

    @admin.display(description="Material", ordering="title")
    def material_identity(self, obj):
        return format_html('<span class="edually-slm-primary">{}</span>', obj.title)

    @admin.display(description="Visibility", ordering="visibility")
    def visibility_badge(self, obj):
        public = obj.visibility == PersonalMaterial.Visibility.PUBLIC
        return format_html(
            '<span class="edually-slm-badge edually-slm-badge--{}">{}</span>',
            "positive" if public else "muted",
            "Public" if public else "Private",
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author")


# ============================================================
# HIGHLIGHT ANSWERS
# ============================================================

@admin.register(HighlightAnswer)
class HighlightAnswerAdmin(LearningContentAdminOverview, admin.ModelAdmin):

    overview_title = "AI highlight answers"
    overview_description = "Review existing AI explanations and their linked learning material."
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
    search_help_text = "Search highlighted text, owner, or related material."

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
class HighlightAnnotationAdmin(LearningContentAdminOverview, admin.ModelAdmin):

    overview_title = "Highlight annotations"
    overview_description = "Find learner notes attached to highlighted passages."
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
    search_help_text = "Search highlighted text, owner, or related material."

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