from django.db import models
from django.conf import settings

class Subject(models.Model):
    YEAR_FIRST = '1'
    YEAR_TWO = '2'
    YEAR_THREE = '3'
    YEAR_FOUR = '4'

    YEAR_CHOICES = [
        (YEAR_FIRST, "First"),
        (YEAR_TWO, "Second"),
        (YEAR_THREE, "Third"),
        (YEAR_FOUR, "Four"),
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
        default=YEAR_FIRST,
        help_text="Identifer for subject intended year.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    class Meta:
        unique_together = ("subject", "module_number")
        ordering = ["subject", "module_number"]
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self) -> str:
        return f"{self.subject.subject_code} – Module {self.module_number}: {self.module_name}"
