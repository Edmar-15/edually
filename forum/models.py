from django.db import models
from django.conf import settings
from django.utils import timezone


class Category(models.Model):
    """Forum category for organizing discussions"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, default='fa-comments')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def post_count(self):
        return self.post_set.filter(is_deleted=False).count()
    
    @property
    def recent_posts(self):
        return self.post_set.filter(is_deleted=False).order_by('-created_at')[:5]


class Post(models.Model):
    """Main forum post/discussion"""
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=300)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    upvotes = models.PositiveIntegerField(default=0)
    reply_count = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['-upvotes']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def status(self):
        if self.is_locked:
            return 'locked'
        elif self.reply_count == 0:
            return 'unanswered'
        return 'answered'


class Reply(models.Model):
    """Reply to a forum post"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_replies')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    upvotes = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    is_best_answer = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_best_answer', '-upvotes', 'created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]
    
    def __str__(self):
        return f"Reply to {self.post.title}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Always update the post's reply count after saving
        self.post.reply_count = self.post.replies.filter(is_deleted=False).count()
        self.post.save(update_fields=['reply_count'])


class PostUpvote(models.Model):
    """Track user upvotes on posts"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_post_upvotes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='upvoters')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['post', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} upvoted {self.post.title}"


class ReplyUpvote(models.Model):
    """Track user upvotes on replies"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='forum_reply_upvotes')
    reply = models.ForeignKey(Reply, on_delete=models.CASCADE, related_name='upvoters')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'reply')
        indexes = [
            models.Index(fields=['reply', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} upvoted a reply"


class Report(models.Model):
    """A user's report of a forum post or reply."""
    POST = 'post'
    REPLY = 'reply'
    CONTENT_TYPE_CHOICES = [(POST, 'Post'), (REPLY, 'Reply')]
    REASON_CHOICES = (
        ('spam', 'Spam'),
        ('harassment', 'Harassment or bullying'),
        ('inappropriate', 'Inappropriate content'),
        ('misinformation', 'Misinformation'),
        ('other', 'Other'),
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_reports',
    )
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES)
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, null=True, blank=True, related_name='reports'
    )
    reply = models.ForeignKey(
        Reply, on_delete=models.CASCADE, null=True, blank=True, related_name='reports'
    )
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    action_taken = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(content_type='post', post__isnull=False, reply__isnull=True)
                    | models.Q(content_type='reply', post__isnull=True, reply__isnull=False)
                ),
                name='report_matches_content_type',
            ),
            models.UniqueConstraint(
                fields=['reporter', 'content_type', 'post', 'reply'],
                name='one_report_per_user_content',
            ),
        ]

    def __str__(self):
        return f"{self.reporter} reported {self.content_type}"

