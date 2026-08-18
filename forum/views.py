from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.http import JsonResponse
from .models import Post, Category, Reply, PostUpvote, ReplyUpvote


def feed_redirect(request):
    """Backward-compatible alias for the legacy forum feed route."""
    return redirect('forum:list')


def notifications(request):
    """Temporary compatibility endpoint for legacy notifications links."""
    return redirect('forum:list')


def moderation_dashboard(request):
    """Legacy moderation dashboard route kept for template compatibility."""
    return redirect('forum:list')


def moderation_deleted_history(request):
    """Legacy deleted-history route kept for template compatibility."""
    return redirect('forum:list')


def moderation_deleted_content_detail(request, content_type, content_id):
    """Legacy detail route kept for template compatibility."""
    return redirect('forum:list')


def flag_content(request, content_type, content_id):
    """Legacy flag route kept for compatibility; redirect back to the parent thread."""
    if content_type == 'reply':
        reply = get_object_or_404(Reply, pk=content_id, is_deleted=False)
        return redirect('forum:post_detail', post_id=reply.post_id)
    post = get_object_or_404(Post, pk=content_id, is_deleted=False)
    return redirect('forum:post_detail', post_id=post.pk)


def post_edit(request, post_id):
    """Backward-compatible alias for older post edit links."""
    return redirect('forum:post_detail', post_id=post_id)


def post_archive(request, post_id):
    """Backward-compatible alias for older archive actions."""
    return redirect('forum:post_detail', post_id=post_id)


def verify_post(request, post_id):
    """Backward-compatible alias for older verification actions."""
    return redirect('forum:post_detail', post_id=post_id)


def reply_edit(request, reply_id):
    """Backward-compatible alias for older reply edit links."""
    reply = get_object_or_404(Reply, pk=reply_id, is_deleted=False)
    return redirect('forum:post_detail', post_id=reply.post_id)


def reply_delete(request, reply_id):
    """Backward-compatible alias for older reply deletion links."""
    reply = get_object_or_404(Reply, pk=reply_id, is_deleted=False)
    return redirect('forum:post_detail', post_id=reply.post_id)


def notification_goto(request, notification_id):
    """Legacy notification route kept for compatibility."""
    return redirect('forum:list')


def notification_mark_all_read(request):
    """Legacy notification route kept for compatibility."""
    return redirect('forum:list')


def resolve_report(request, report_id):
    """Legacy moderation report route kept for compatibility."""
    return redirect('forum:list')


def conversation_map_json(request, post_id):
    """Compatibility route for legacy conversation map data loads."""
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    return JsonResponse({'post_id': post.pk, 'title': post.title})


def forum_list(request):
    """List all forum posts with optional filtering"""
    posts = Post.objects.filter(is_deleted=False).prefetch_related('author', 'category')

    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        posts = posts.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query))

    # Category filtering
    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['-created_at', '-upvotes', '-reply_count', 'created_at']:
        posts = posts.order_by(sort_by)

    categories = Category.objects.all()
    user_post_upvotes = set()
    if request.user.is_authenticated:
        user_post_upvotes = set(
            PostUpvote.objects.filter(user=request.user).values_list('post_id', flat=True)
        )

    context = {
        'posts': posts,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_slug,
        'sort_by': sort_by,
        'user_post_upvotes': user_post_upvotes,
    }
    return render(request, 'forum/list.html', context)


def post_detail(request, post_id):
    """Show a single post with all replies"""
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    post.views += 1
    post.save(update_fields=['views'])
    
    replies = post.replies.filter(is_deleted=False).select_related('author')
    user_post_upvotes = set()
    user_reply_upvotes = set()
    
    if request.user.is_authenticated:
        user_post_upvotes = set(
            PostUpvote.objects.filter(user=request.user, post=post).values_list('post_id', flat=True)
        )
        user_reply_upvotes = set(
            ReplyUpvote.objects.filter(user=request.user, reply__post=post).values_list('reply_id', flat=True)
        )
    
    context = {
        'post': post,
        'replies': replies,
        'user_post_upvotes': user_post_upvotes,
        'user_reply_upvotes': user_reply_upvotes,
    }
    return render(request, 'forum/detail.html', context)


@login_required
def create_post(request):
    """Create a new forum post"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category_id = request.POST.get('category')
        
        if not title or not content:
            return render(request, 'forum/create.html', {
                'error': 'Title and content are required.',
                'categories': Category.objects.all(),
            })
        
        category = None
        if category_id:
            category = get_object_or_404(Category, pk=category_id)
        
        post = Post.objects.create(
            author=request.user,
            title=title,
            content=content,
            category=category,
        )
        
        return redirect('forum:post_detail', post_id=post.pk)
    
    categories = Category.objects.all()
    return render(request, 'forum/create.html', {'categories': categories})


@login_required
def create_reply(request, post_id):
    """Add a reply to a post"""
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if not content:
            replies = post.replies.filter(is_deleted=False).select_related('author')
            user_post_upvotes = set(
                PostUpvote.objects.filter(user=request.user, post=post).values_list('post_id', flat=True)
            )
            user_reply_upvotes = set(
                ReplyUpvote.objects.filter(user=request.user, reply__post=post).values_list('reply_id', flat=True)
            )
            return render(request, 'forum/detail.html', {
                'post': post,
                'replies': replies,
                'error': 'Reply content is required.',
                'user_post_upvotes': user_post_upvotes,
                'user_reply_upvotes': user_reply_upvotes,
            })
        
        reply = Reply.objects.create(
            post=post,
            author=request.user,
            content=content,
        )
        
        return redirect('forum:post_detail', post_id=post.pk)
    
    return redirect('forum:post_detail', post_id=post.pk)


@login_required
@require_http_methods(["POST"])
def upvote_post(request, post_id):
    """Upvote or un-upvote a forum post."""
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)

    upvote, created = PostUpvote.objects.get_or_create(user=request.user, post=post)

    if not created:
        upvote.delete()
        post.upvotes = max(0, post.upvotes - 1)
        has_upvoted = False
    else:
        post.upvotes += 1
        has_upvoted = True

    post.save(update_fields=['upvotes'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'upvotes': post.upvotes,
            'has_upvoted': has_upvoted,
        })

    return redirect('forum:post_detail', post_id=post.pk)


@login_required
@require_http_methods(["POST"])
def upvote_reply(request, reply_id):
    """Upvote or un-upvote a reply."""
    reply = get_object_or_404(Reply, pk=reply_id, is_deleted=False)

    upvote, created = ReplyUpvote.objects.get_or_create(user=request.user, reply=reply)

    if not created:
        upvote.delete()
        reply.upvotes = max(0, reply.upvotes - 1)
        has_upvoted = False
    else:
        reply.upvotes += 1
        has_upvoted = True

    reply.save(update_fields=['upvotes'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'upvotes': reply.upvotes,
            'has_upvoted': has_upvoted,
        })

    return redirect('forum:post_detail', post_id=reply.post.pk)

