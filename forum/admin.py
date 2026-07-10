# forum/admin.py
from django.contrib import admin
from .models import Category, Post, Reply, PostUpvote

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}

class ReplyInline(admin.TabularInline):
    model = Reply
    extra = 0
    readonly_fields = ("author", "created_at")

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "created_at", "verified", "upvotes", "replies_cnt")
    list_filter = ("verified", "category", "created_at")
    search_fields = ("title", "content", "author__username")
    inlines = [ReplyInline]
    actions = ["mark_verified", "reset_verification"]

    @admin.action(description="Mark selected as Teacher Verified")
    def mark_verified(self, request, queryset):
        queryset.update(verified=True)

    @admin.action(description="Reset verification")
    def reset_verification(self, request, queryset):
        queryset.update(verified=False)

admin.site.register(Reply)
admin.site.register(PostUpvote)
