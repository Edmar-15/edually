# forum/admin.py
from django.contrib import admin
from .models import Category, Post, Reply, PostUpvote, ReplyUpvote, FlagReport

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}

class ReplyInline(admin.TabularInline):
    model = Reply
    extra = 0
    readonly_fields = ("author", "created_at", "updated_at", "upvotes")
    fields = ("author", "created_at", "updated_at", "content", "upvotes", "is_deleted")

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "created_at", "verified", "upvotes", "replies_cnt", "is_deleted")
    list_filter = ("verified", "flagged", "is_deleted", "category", "created_at")
    search_fields = ("title", "content", "author__username")
    inlines = [ReplyInline]
    actions = ["mark_verified", "reset_verification", "mark_deleted", "restore_post"]
    readonly_fields = ("created_at", "updated_at", "upvotes", "replies_cnt")

    @admin.action(description="Mark selected as Teacher Verified")
    def mark_verified(self, request, queryset):
        queryset.update(verified=True)

    @admin.action(description="Reset verification")
    def reset_verification(self, request, queryset):
        queryset.update(verified=False)
    
    @admin.action(description="Mark selected as deleted")
    def mark_deleted(self, request, queryset):
        queryset.update(is_deleted=True)
    
    @admin.action(description="Restore selected posts")
    def restore_post(self, request, queryset):
        queryset.update(is_deleted=False)

@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post", "created_at", "upvotes", "is_deleted")
    list_filter = ("created_at", "is_deleted", "post")
    search_fields = ("content", "author__username", "post__title")
    readonly_fields = ("created_at", "updated_at", "upvotes")
    actions = ["mark_deleted", "restore_reply"]
    
    @admin.action(description="Mark selected as deleted")
    def mark_deleted(self, request, queryset):
        queryset.update(is_deleted=True)
    
    @admin.action(description="Restore selected replies")
    def restore_reply(self, request, queryset):
        queryset.update(is_deleted=False)

@admin.register(FlagReport)
class FlagReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "content_type", "reason", "created_at", "resolved")
    list_filter = ("reason", "content_type", "resolved", "created_at")
    search_fields = ("reporter__username", "description")
    readonly_fields = ("reporter", "created_at", "content_type", "post", "reply", "reason")
    actions = ["mark_resolved"]
    
    @admin.action(description="Mark selected reports as resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True)

admin.site.register(PostUpvote)
admin.site.register(ReplyUpvote)
