from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from .forms import PostForm, ReplyForm
from .models import Post, Category, Reply, PostUpvote, ReplyUpvote, Report


REPORT_REASONS = (
    ('spam', 'Spam'),
    ('harassment', 'Harassment or bullying'),
    ('inappropriate', 'Inappropriate content'),
    ('misinformation', 'Misinformation'),
    ('other', 'Other'),
)


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


@login_required
def flag_content(request, content_type, content_id):
    """Display and save a report for a post or reply."""
    if content_type == 'reply':
        reply = get_object_or_404(Reply, pk=content_id, is_deleted=False)
        content = reply
        post = reply.post
    elif content_type == 'post':
        post = get_object_or_404(Post, pk=content_id, is_deleted=False)
        content = post
    else:
        return redirect('forum:list')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not any(value == reason for value, _ in REPORT_REASONS):
            context = {
                'content': content,
                'content_type': content_type,
                'reason_choices': REPORT_REASONS,
                'error': 'Please select a report category.',
            }
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'html': render_to_string('forum/flag_content.html', context, request=request),
                })
            return render(request, 'forum/flag_content.html', context)

        lookup = {'reporter': request.user, 'content_type': content_type}
        lookup['reply' if content_type == 'reply' else 'post'] = content
        report, created = Report.objects.get_or_create(
            **lookup,
            defaults={
                'reason': reason,
                'description': request.POST.get('description', '').strip(),
            },
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'redirect': redirect('forum:post_detail', post_id=post.pk).url,
                'message': 'Report submitted successfully.' if created else 'This content was already reported.',
            })
        return render(request, 'forum/flag_success.html', {'already_reported': not created})

    context = {
        'content': content,
        'content_type': content_type,
        'reason_choices': REPORT_REASONS,
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'html': render_to_string('forum/flag_content.html', context, request=request),
        })
    return render(request, 'forum/flag_content.html', context)


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id, author=request.user, is_deleted=False)
    form = PostForm(request.POST or None, instance=post)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'redirect': redirect('forum:post_detail', post_id=post.pk).url,
            })
        return redirect('forum:post_detail', post_id=post.pk)

    context = {'post': post, 'form': form}
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'html': render_to_string('forum/partials/post_edit_form.html', context, request=request),
        })
    return render(request, 'forum/partials/post_edit_form.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def post_archive(request, post_id):
    post = get_object_or_404(Post, pk=post_id, author=request.user, is_deleted=False)
    if request.method == 'POST':
        post.is_archived = True
        post.save(update_fields=['is_archived', 'updated_at'])
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'redirect': redirect('forum:list').url,
            })
        return redirect('forum:list')

    html = render_to_string('forum/post_archive.html', {'post': post}, request=request)
    return JsonResponse({'html': html})


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
    posts = Post.objects.filter(
        is_deleted=False,
        is_archived=False,
    ).prefetch_related('author', 'category')

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
    post = get_object_or_404(Post, pk=post_id, is_deleted=False, is_archived=False)

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
        'reply_form': ReplyForm(),
    }
    return render(request, 'forum/detail.html', context)


@login_required
def create_post(request):
    """Create a new forum post"""
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category_id = request.POST.get('category')
        
        if not title or not content:
            context = {
                'error': 'Title and content are required.',
                'categories': Category.objects.all(),
                'title': title,
                'content': content,
                'selected_category': category_id,
            }
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'html': render_to_string('forum/partials/create_post_modal.html', context, request=request),
                })
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
        
        if is_ajax:
            return JsonResponse({
                'success': True,
                'redirect': redirect('forum:post_detail', post_id=post.pk).url,
                'message': 'Discussion posted successfully.',
            })
        return redirect('forum:post_detail', post_id=post.pk)
    
    if is_ajax:
        return JsonResponse({
            'html': render_to_string('forum/partials/create_post_modal.html', {
                'categories': Category.objects.all(),
            }, request=request),
        })

    categories = Category.objects.all()
    return render(request, 'forum/create.html', {'categories': categories})


@login_required
def create_reply(request, post_id):
    """Add a reply to a post"""
    post = get_object_or_404(Post, pk=post_id, is_deleted=False, is_archived=False)
    
    if request.method == 'POST':
        form = ReplyForm(request.POST)
        if not form.is_valid():
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'html': '<div class="form-error-message">Reply content is required.</div>',
                })
            return redirect('forum:post_detail', post_id=post.pk)

        reply = form.save(commit=False)
        reply.post = post
        reply.author = request.user
        reply.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'html': render_to_string('forum/partials/reply_item.html', {
                    'reply': reply,
                    'user_reply_upvotes': set(),
                }, request=request),
                'replies_cnt': post.reply_count,
            })
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

