from django.contrib import admin
from .models import Category, Post, Reply, PostUpvote, ReplyUpvote


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'post_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'upvotes', 'reply_count', 'views', 'is_pinned', 'created_at')
    list_filter = ('category', 'created_at', 'is_deleted', 'is_pinned', 'is_locked')
    search_fields = ('title', 'content', 'author__username')
    readonly_fields = ('created_at', 'updated_at', 'views')


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('post', 'author', 'upvotes', 'is_best_answer', 'created_at')
    list_filter = ('created_at', 'is_deleted', 'is_best_answer')
    search_fields = ('content', 'author__username', 'post__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PostUpvote)
class PostUpvoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'post__title')
    readonly_fields = ('created_at',)


@admin.register(ReplyUpvote)
class ReplyUpvoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'reply', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'reply__post__title')
    readonly_fields = ('created_at',)

