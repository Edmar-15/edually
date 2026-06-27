from django.db import models
from django.conf import settings

# Create your models here.
class Subject(models.Model):
    
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
        help_text="The file that contains the module’s content (PDF, video, zip, …).",
        max_length=255,
    )
    
    class Meta:
        unique_together = ("subject", "module_number")
        ordering = ["subject", "module_number"]
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self) -> str:
        return f"{self.subject.subject_code} – Module {self.module_number}: {self.module_name}"