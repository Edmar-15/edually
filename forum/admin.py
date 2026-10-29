# Phase 2D: EduAlly Forum Management
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Category, Post, Reply, PostUpvote, ReplyUpvote, Report


class ForumOverviewAdmin:
    """Shared changelist overview; all record operations remain Django Admin."""

    change_list_template = "admin/forum/change_list.html"
    change_form_template = "admin/forum/change_form.html"
    list_per_page = 25
    overview_title = "Forum records"
    overview_description = "Search and review discussion records."

    def get_overview_stats(self, request):
        return ()

    def changelist_view(self, request, extra_context=None):
        if request.method == "GET" and self.has_view_or_change_permission(request):
            overview = {
                "title": self.overview_title,
                "description": self.overview_description,
                "stats": self.get_overview_stats(request),
            }
            extra_context = {**(extra_context or {}), "edually_forum_overview": overview}
        return super().changelist_view(request, extra_context=extra_context)


def _status_badge(label, status):
    return format_html(
        '<span class="edually-forum-badge edually-forum-badge--{}">{}</span>',
        status, label,
    )


@admin.register(Category)
class CategoryAdmin(ForumOverviewAdmin, admin.ModelAdmin):
    overview_title = "Forum categories"
    overview_description = "Organize discussion topics and check how many visible posts each category contains."
    list_display = ("category_identity", "slug", "visible_posts", "created_at")
    list_display_links = ("category_identity",)
    list_filter = ("created_at",)
    search_fields = ("name", "slug", "description")
    search_help_text = "Search category names, slugs, or descriptions."
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _edually_visible_posts=Count(
                "post", filter=Q(post__is_deleted=False, post__is_archived=False), distinct=True
            )
        )

    @admin.display(description="Category", ordering="name")
    def category_identity(self, obj):
        return format_html('<span class="edually-forum-primary">{}</span>', obj.name)

    @admin.display(description="Visible posts", ordering="_edually_visible_posts")
    def visible_posts(self, obj):
        return obj._edually_visible_posts

    def get_overview_stats(self, request):
        data = Category.objects.aggregate(
            total=Count("pk", distinct=True),
            with_posts=Count(
                "pk", filter=Q(post__is_deleted=False, post__is_archived=False), distinct=True
            ),
        )
        return (("Total categories", data["total"]), ("With visible posts", data["with_posts"]))


@admin.register(Post)
class PostAdmin(ForumOverviewAdmin, admin.ModelAdmin):
    overview_title = "Discussion posts"
    overview_description = "Review posts and their moderation state. Archive and soft-delete flags are separate from permanent deletion."
    list_display = (
        "post_identity", "author", "category", "visibility_status", "moderation_flags",
        "upvotes", "reply_count", "created_at",
    )
    list_display_links = ("post_identity",)
    list_filter = ("category", "is_deleted", "is_archived", "is_pinned", "is_locked", "created_at")
    search_fields = ("title", "content", "author__email", "author__username")
    search_help_text = "Search titles, content, author emails, or usernames."
    readonly_fields = ("created_at", "updated_at", "views")
    list_select_related = ("author", "category")
    ordering = ("-created_at",)
    fieldsets = (
        ("Discussion", {"fields": ("title", "content", "author", "category")}),
        ("Moderation controls", {
            "fields": ("is_pinned", "is_locked", "is_archived", "is_deleted"),
            "description": "Use archive or soft-delete to hide a post without permanently deleting its history."
        }),
        ("Activity", {"fields": ("upvotes", "reply_count", "views", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Discussion", ordering="title")
    def post_identity(self, obj):
        return format_html('<span class="edually-forum-primary">{}</span>', obj.title)

    @admin.display(description="Visibility")
    def visibility_status(self, obj):
        if obj.is_deleted:
            return _status_badge("Soft-deleted", "danger")
        if obj.is_archived:
            return _status_badge("Archived", "muted")
        return _status_badge("Visible", "positive")

    @admin.display(description="Controls")
    def moderation_flags(self, obj):
        flags = [label for active, label in ((obj.is_pinned, "Pinned"), (obj.is_locked, "Locked")) if active]
        return ", ".join(flags) if flags else "None"

    def get_overview_stats(self, request):
        data = Post.objects.aggregate(
            total=Count("pk"),
            visible=Count("pk", filter=Q(is_deleted=False, is_archived=False)),
            archived=Count("pk", filter=Q(is_archived=True, is_deleted=False)),
            deleted=Count("pk", filter=Q(is_deleted=True)),
        )
        return (("Total posts", data["total"]), ("Visible", data["visible"]),
                ("Archived", data["archived"]), ("Soft-deleted", data["deleted"]))


@admin.register(Reply)
class ReplyAdmin(ForumOverviewAdmin, admin.ModelAdmin):
    overview_title = "Discussion replies"
    overview_description = "Find replies, review answers, and inspect soft-deleted content."
    list_display = ("reply_identity", "post", "author", "reply_state", "best_answer_state", "upvotes", "created_at")
    list_display_links = ("reply_identity",)
    list_filter = ("is_deleted", "is_best_answer", "created_at")
    search_fields = ("content", "author__email", "author__username", "post__title")
    search_help_text = "Search reply text, author emails, or post titles."
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("author", "post")
    ordering = ("-created_at",)
    fieldsets = (
        ("Reply", {"fields": ("post", "author", "content")}),
        ("Moderation", {"fields": ("is_deleted", "is_best_answer"),
                       "description": "Soft-delete hides a reply while preserving its record. Saving updates the post reply count."}),
        ("Activity", {"fields": ("upvotes", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Reply")
    def reply_identity(self, obj):
        preview = " ".join(obj.content.split())[:95] or "Empty reply"
        return format_html('<span class="edually-forum-primary">{}</span>', preview)

    @admin.display(description="Visibility", ordering="is_deleted")
    def reply_state(self, obj):
        return _status_badge("Soft-deleted" if obj.is_deleted else "Visible", "danger" if obj.is_deleted else "positive")

    @admin.display(description="Best answer", ordering="is_best_answer")
    def best_answer_state(self, obj):
        return _status_badge("Best answer" if obj.is_best_answer else "No", "positive" if obj.is_best_answer else "muted")

    def get_overview_stats(self, request):
        data = Reply.objects.aggregate(
            total=Count("pk"),
            visible=Count("pk", filter=Q(is_deleted=False)),
            deleted=Count("pk", filter=Q(is_deleted=True)),
            best=Count("pk", filter=Q(is_best_answer=True, is_deleted=False)),
        )
        return (("Total replies", data["total"]), ("Visible", data["visible"]),
                ("Soft-deleted", data["deleted"]), ("Visible best answers", data["best"]))


@admin.register(PostUpvote)
class PostUpvoteAdmin(ForumOverviewAdmin, admin.ModelAdmin):
    overview_title = "Post upvotes"
    overview_description = "Review recorded post votes and the accounts that submitted them."
    list_display = ("user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__email", "post__title")
    readonly_fields = ("created_at",)
    list_select_related = ("user", "post")


@admin.register(ReplyUpvote)
class ReplyUpvoteAdmin(ForumOverviewAdmin, admin.ModelAdmin):
    overview_title = "Reply upvotes"
    overview_description = "Review recorded reply votes and the accounts that submitted them."
    list_display = ("user", "reply", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__email", "reply__post__title")
    readonly_fields = ("created_at",)
    list_select_related = ("user", "reply__post")


@admin.register(Report)
class ReportAdmin(ForumOverviewAdmin, admin.ModelAdmin):
    """Superuser review queue; teacher-facing moderation routes remain unchanged."""

    overview_title = "Reported content"
    overview_description = "Review flagged posts and replies. Dismissing a report does not hide its content."
    list_display = ("reported_content", "reporter", "reason", "report_status", "created_at")
    list_display_links = ("reported_content",)
    list_filter = ("is_resolved", "content_type", "reason", "created_at")
    search_fields = ("post__title", "reply__post__title", "description", "reporter__email", "reporter__username")
    search_help_text = "Search reported post titles, reporter emails, or report descriptions."
    readonly_fields = (
        "reporter", "content_type", "post", "reply", "reason", "description",
        "is_resolved", "action_taken", "created_at",
    )
    fields = readonly_fields
    list_select_related = ("reporter", "post", "reply__post")
    ordering = ("-created_at",)
    actions = ("dismiss_selected_reports",)
    change_form_template = "admin/forum/report/change_form.html"

    def has_module_permission(self, request):
        return request.user.is_superuser and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return False  # Reports originate from forum users, not administrators.

    def has_delete_permission(self, request, obj=None):
        return False  # Preserve the moderation audit trail.

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("reporter", "post", "reply__post")

    @admin.display(description="Reported content")
    def reported_content(self, obj):
        if obj.content_type == Report.POST and obj.post_id:
            label, kind = obj.post.title, "Post"
        elif obj.content_type == Report.REPLY and obj.reply_id:
            label, kind = f"Reply to {obj.reply.post.title}", "Reply"
        else:
            label, kind = "Unavailable content", "Unknown"
        return format_html(
            '<span class="edually-forum-primary">{}</span><span class="edually-forum-secondary">{}</span>',
            label, kind,
        )

    @admin.display(description="Review status", ordering="is_resolved")
    def report_status(self, obj):
        return _status_badge("Resolved" if obj.is_resolved else "Pending", "muted" if obj.is_resolved else "warning")

    def get_overview_stats(self, request):
        data = Report.objects.aggregate(
            total=Count("pk"),
            pending=Count("pk", filter=Q(is_resolved=False)),
            pending_posts=Count("pk", filter=Q(is_resolved=False, content_type=Report.POST)),
            pending_replies=Count("pk", filter=Q(is_resolved=False, content_type=Report.REPLY)),
        )
        return (("All reports", data["total"]), ("Pending", data["pending"]),
                ("Post reports pending", data["pending_posts"]), ("Reply reports pending", data["pending_replies"]))

    @admin.action(description="Dismiss selected reports (including other reports on the same content)")
    def dismiss_selected_reports(self, request, queryset):
        if not request.user.is_superuser:
            raise PermissionDenied
        unresolved = queryset.filter(is_resolved=False)
        post_ids = list(unresolved.filter(content_type=Report.POST).values_list("post_id", flat=True))
        reply_ids = list(unresolved.filter(content_type=Report.REPLY).values_list("reply_id", flat=True))
        targets = Q()
        if post_ids:
            targets |= Q(content_type=Report.POST, post_id__in=post_ids)
        if reply_ids:
            targets |= Q(content_type=Report.REPLY, reply_id__in=reply_ids)
        updated = 0
        if post_ids or reply_ids:
            updated = Report.objects.filter(is_resolved=False).filter(targets).update(
                is_resolved=True, action_taken="dismiss"
            )
        self.message_user(request, f"Dismissed {updated} report(s). Content remains unchanged.", messages.SUCCESS)
