# slm/views.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Subject(models.Model):
    YEAR_TWO = '2'
    YEAR_THREE = '3'

    YEAR_CHOICES = [
        (YEAR_TWO, "Second"),
        (YEAR_THREE, "Third"),
    ]

    subject_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="A short, unique identifier for the subject (e.g. GEC101).",
    )
    subject_name = models.CharField(
        max_length=255,
        help_text="The full name of the subject.",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subjects",
        help_text="The user who created/uploaded the subject.",
    )
    year = models.CharField(
        max_length=1,
        choices=YEAR_CHOICES,
        default=YEAR_TWO,
        help_text="Identifer for subject intended year.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self) -> str:
        return f"{self.subject_code} – {self.subject_name}"


class Module(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="modules",
        help_text="Subject that this module belongs to.",
    )
    module_number = models.PositiveIntegerField(
        help_text="The sequential number inside the subject (1, 2, 3 …)."
    )
    module_name = models.CharField(
        max_length=255,
        help_text="Human‑readable title of the module.",
    )
    file = models.FileField(
        upload_to="modules/%Y/%m/%d/",
        help_text="The file that contains the module’s content (PDF, Word, PowerPoint).",
        max_length=255,
    )
    # -------------------------------------------------------------
    #  NEW FIELD – stores the HTML version of the uploaded file
    # -------------------------------------------------------------
    extracted_html = models.TextField(
        blank=True,
        help_text="HTML version of the uploaded document – generated on upload.",
    )
    
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("subject", "module_number")
        ordering = ["subject", "module_number"]
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    @property
    def file_icon(self) -> str:
        """Return a Font Awesome icon class based on the uploaded file type."""
        return self.file_icon_classes.split()[0]

    @property
    def file_icon_classes(self) -> str:
        """Return the icon class and color modifier for the file type."""
        name = (self.file.name or "").lower()

        if name.endswith(".pdf"):
            return "fas fa-file-pdf activity-icon--pdf"
        if name.endswith((".ppt", ".pptx", ".key")):
            return "fas fa-file-powerpoint activity-icon--ppt"
        if name.endswith((".doc", ".docx", ".rtf")):
            return "fas fa-file-word activity-icon--doc"
        if name.endswith((".xls", ".xlsx", ".csv")):
            return "fas fa-file-excel activity-icon--doc"
        if name.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return "fas fa-file-video activity-icon--ppt"
        if name.endswith((".mp3", ".wav", ".aac", ".ogg")):
            return "fas fa-file-audio activity-icon--doc"
        if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            return "fas fa-file-image activity-icon--doc"
        if name.endswith((".html", ".htm")):
            return "fas fa-file-code activity-icon--ppt"
        return "fas fa-file-alt activity-icon--default"

    def __str__(self) -> str:
        return f"{self.subject.subject_code} – Module {self.module_number}: {self.module_name}"

def user_media_path(instance, filename):
    """
    Store a user’s files under `media/users/<user‑pk>/<filename>`.
    Feel free to extend with a date‑based sub‑folder if you like:
        f'users/{instance.author_id}/{timezone.now():%Y/%m/%d}/{filename}'
    """
    return f"users/{instance.author_id}/{filename}"


class PersonalMaterial(models.Model):
    """
    A file that belongs to a single user.  No connection to Subject/Module.
    """
    title = models.CharField(
        max_length=255,
        help_text=_("Human‑readable title for the file."),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_materials",
        help_text=_("Owner of the file."),
    )
    file = models.FileField(
        upload_to=user_media_path,
        max_length=255,
        help_text=_("The uploaded document."),
    )
    extracted_html = models.TextField(
        blank=True,
        help_text=_(
            "HTML version generated from the uploaded document (optional, "
            "usually filled by a background task)."
        ),
    )

    class Visibility(models.TextChoices):
        PRIVATE = "PR", _("Private – only the owner can see it")
        PUBLIC = "PU", _("Public – any logged‑in user can see it")
        # you can add RESTRICTED later without a migration

    visibility = models.CharField(
        max_length=2,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        help_text=_("Who may view this file."),
    )
    
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Personal Material")
        verbose_name_plural = _("Personal Materials")
        indexes = [
            models.Index(fields=["visibility"], name="idx_personal_visibility"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.author})"
    
    # -----------------------------------------------------------------
    #  File‑type icon helpers – mirrors the logic used for ``Module``.
    # -----------------------------------------------------------------
    @property
    def file_icon(self) -> str:
        """Return the primary Font Awesome class for the uploaded file."""
        return self.file_icon_classes.split()[0] if self.file_icon_classes else "fas"

    @property
    def file_icon_classes(self) -> str:
        """
        Return the Font Awesome class and colour modifier for the file type.
        This is used by the dashboard to show a nice icon next to each
        personal‑material entry.
        """
        name = (self.file.name or "").lower()

        if name.endswith(".pdf"):
            return "fas fa-file-pdf activity-icon--pdf"
        if name.endswith((".ppt", ".pptx", ".key")):
            return "fas fa-file-powerpoint activity-icon--ppt"
        if name.endswith((".doc", ".docx", ".rtf")):
            return "fas fa-file-word activity-icon--doc"
        if name.endswith((".xls", ".xlsx", ".csv")):
            return "fas fa-file-excel activity-icon--doc"
        if name.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return "fas fa-file-video activity-icon--ppt"
        if name.endswith((".mp3", ".wav", ".aac", ".ogg")):
            return "fas fa-file-audio activity-icon--doc"
        if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            return "fas fa-file-image activity-icon--doc"
        if name.endswith((".html", ".htm")):
            return "fas fa-file-code activity-icon--ppt"
        return "fas fa-file-alt activity-icon--default"
    

class HighlightAnswer(models.Model):
    """
    One row per exact highlighted string that has already been sent to the AI.
    """
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="highlight_answers",
        null=True,
        blank=True,
        help_text="Module the answer belongs to (null when it belongs to a personal material).",
    )
    personal_material = models.ForeignKey(
        "PersonalMaterial",
        on_delete=models.CASCADE,
        related_name="highlight_answers",
        null=True,
        blank=True,
        help_text="PersonalMaterial the answer belongs to (null when it belongs to a module).",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="highlight_answers",
        help_text="User that asked the question – guarantees a private cache."
    )
    # store the *canonical* version of the highlighted text (lower‑cased)
    query = models.CharField(max_length=255,
                             help_text="Exact highlighted text (lower‑cased).")
    # -----------------------------------------------------------------
    # NEW – character offsets of the highlighted fragment within the
    # extracted HTML (the string that is shown on the preview page).
    # ``start_offset`` is inclusive, ``end_offset`` is exclusive.
    # -----------------------------------------------------------------
    start_offset = models.IntegerField(
        null=True,
        blank=True,
        help_text="Character offset where the highlight starts in the extracted HTML.",
    )
    end_offset = models.IntegerField(
        null=True,
        blank=True,
        help_text="Character offset where the highlight ends (exclusive).",
    )

    answer_simplified = models.TextField(
        blank=True,
        null=True,
        help_text="Simplified explanation."
    )
    answer_technical = models.TextField(
        blank=True,
        null=True,
        help_text="Technical explanation."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # a user can have many highlights for the same text – they are
        # distinguished by the character offsets.
        unique_together = (
            "module",
            "personal_material",
            "query",
            "owner",
            "start_offset",
            "end_offset",
        )
        ordering = ["-created_at"]
        verbose_name = "Highlight answer"
        verbose_name_plural = "Highlight answers"


class HighlightAnnotation(models.Model):
    """
    A free‑form note attached to a highlighted fragment.
    """
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="highlight_annotations",
        null=True,
        blank=True,
        help_text="Module the annotation belongs to (null for personal material).",
    )
    personal_material = models.ForeignKey(
        "PersonalMaterial",
        on_delete=models.CASCADE,
        related_name="highlight_annotations",
        null=True,
        blank=True,
        help_text="Personal material the annotation belongs to (null for module).",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="highlight_annotations",
        help_text="User that created the annotation.",
    )
    query = models.CharField(
        max_length=255,
        help_text="Exact highlighted text (lower‑cased).",
    )
    # -----------------------------------------------------------------
    # NEW – offsets so the annotation is tied to the exact occurrence.
    # -----------------------------------------------------------------
    start_offset = models.IntegerField(
        null=True,
        blank=True,
        help_text="Character offset where the annotation starts.",
    )
    end_offset = models.IntegerField(
        null=True,
        blank=True,
        help_text="Character offset where the annotation ends (exclusive).",
    )
    note = models.TextField(
        blank=True,
        help_text="Free‑form annotation written by the user.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # a user may have only one annotation per query + offset per target
        unique_together = (
            "module",
            "personal_material",
            "query",
            "owner",
            "start_offset",
            "end_offset",
        )
        ordering = ["-created_at"]
        verbose_name = "Highlight annotation"
        verbose_name_plural = "Highlight annotations"