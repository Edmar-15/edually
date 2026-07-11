# forum/views.py
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.http import Http404

from .models import Category, Post, PostUpvote, Reply, ReplyUpvote, FlagReport
from .forms import PostForm, ReplyForm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json


# -----------------------------------------------------------------------
# Feed – list + search + pagination
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def feed(request):
    """
    Render the main forum page.

    * Supports keyword search (`?q=…`)
    * Supports category filtering (`?cat=…`)
    * Supports unanswered filter (`?unanswered=1`)
    * Supports sorting (`?sort=latest|upvotes|replies`)
    * Paginates 30 items per page
    """
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("cat", "")
    show_unanswered = request.GET.get("unanswered", "").lower() in ["1", "true"]
    sort_by = request.GET.get("sort", "latest")  # latest, upvotes, replies

    posts_qs = Post.objects.select_related("author", "category").filter(is_deleted=False)

    # ----- search ---------------------------------------------------------
    if query:
        posts_qs = posts_qs.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(author__username__icontains=query)
            | Q(category__name__icontains=query)
        )

    # ----- category -------------------------------------------------------
    if category_slug:
        posts_qs = posts_qs.filter(category__slug=category_slug)

    # ----- unanswered filter -----------------------------------------------
    if show_unanswered:
        posts_qs = posts_qs.filter(replies_cnt=0)

    # ----- sorting ---------------------------------------------------------
    if sort_by == "upvotes":
        posts_qs = posts_qs.order_by("-upvotes", "-created_at")
    elif sort_by == "replies":
        posts_qs = posts_qs.order_by("-replies_cnt", "-created_at")
    else:  # latest
        posts_qs = posts_qs.order_by("-created_at")

    # ----- pagination ------------------------------------------------------
    paginator = Paginator(posts_qs, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {
        "posts": page_obj,
        "categories": categories,
        "categories_count": Post.objects.filter(is_deleted=False).count(),
        "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40],
        "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6],
        "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6],
        "search_query": query,
        "active_category": category_slug,
        "show_unanswered": show_unanswered,
        "sort_by": sort_by,
        "paginator": paginator,
        "page_obj": page_obj,
    }
    return render(request, "forum/feed.html", context)


# -----------------------------------------------------------------------
# Detail – show a single post + its replies + reply form
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related("author", "category")
        .prefetch_related("replies__author"),
        pk=pk,
    )
    
    # Don't show deleted posts
    if post.is_deleted:
        raise Http404("This post has been deleted.")
    
    reply_form = ReplyForm()

    # Process a new reply submitted via POST
    if request.method == "POST":
        reply_form = ReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.author = request.user
            reply.post = post
            reply.save()                     # signals will bump replies_cnt
            return redirect("forum:post_detail", pk=post.pk)

    # Get user's upvotes for context (for UI indication)
    user_post_upvotes = set()
    user_reply_upvotes = set()
    if request.user.is_authenticated:
        user_post_upvotes = set(
            PostUpvote.objects.filter(post=post, voter=request.user)
            .values_list("post_id", flat=True)
        )
        reply_ids = post.replies.filter(is_deleted=False).values_list("id", flat=True)
        user_reply_upvotes = set(
            ReplyUpvote.objects.filter(reply_id__in=reply_ids, voter=request.user)
            .values_list("reply_id", flat=True)
        )

    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {
        "post": post,
        "replies": post.replies.filter(is_deleted=False),
        "reply_form": reply_form,
        "categories": categories,
        "categories_count": Post.objects.filter(is_deleted=False).count(),
        "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40],
        "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6],
        "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6],
        "active_category": post.category.slug if post.category else "",
        "user_post_upvotes": user_post_upvotes,
        "user_reply_upvotes": user_reply_upvotes,
    }
    return render(request, "forum/post_detail.html", context)





# -----------------------------------------------------------------------
# Up‑vote – post (AJAX endpoint returns JSON)
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
@require_http_methods(["POST"])
def upvote(request, pk):
    """Toggle upvote on a post and return JSON."""
    post = get_object_or_404(Post, pk=pk)

    upvote, created = PostUpvote.objects.get_or_create(post=post, voter=request.user)
    if not created:
        # User already voted → remove it
        upvote.delete()
        has_upvoted = False
    else:
        # New vote
        has_upvoted = True

    # Refresh from DB to get updated count
    post.refresh_from_db()

    return JsonResponse({
        "success": True,
        "upvotes": post.upvotes,
        "has_upvoted": has_upvoted,
        "post_id": post.pk,
    })


# -----------------------------------------------------------------------
# Up‑vote – reply (AJAX endpoint returns JSON)
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
@require_http_methods(["POST"])
def reply_upvote(request, reply_id):
    """Toggle upvote on a reply and return JSON."""
    reply = get_object_or_404(Reply, pk=reply_id)

    upvote, created = ReplyUpvote.objects.get_or_create(reply=reply, voter=request.user)
    if not created:
        # User already voted → remove it
        upvote.delete()
        has_upvoted = False
    else:
        # New vote
        has_upvoted = True

    # Refresh from DB to get updated count
    reply.refresh_from_db()

    return JsonResponse({
        "success": True,
        "upvotes": reply.upvotes,
        "has_upvoted": has_upvoted,
        "reply_id": reply.pk,
    })


# -----------------------------------------------------------------------
# Edit Post
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def post_edit(request, pk):
    """Edit a post (only by author)."""
    post = get_object_or_404(Post, pk=pk)
    
    if post.author != request.user:
        raise Http404("You can only edit your own posts.")
    
    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            return redirect("forum:post_detail", pk=post.pk)
    else:
        form = PostForm(instance=post)
    
    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {"form": form, "post": post, "categories": categories, "categories_count": Post.objects.filter(is_deleted=False).count(), "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]}
    return render(request, "forum/post_edit.html", context)


# -----------------------------------------------------------------------
# Delete Post (soft delete)
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def post_delete(request, pk):
    """Delete a post (soft delete - only by author)."""
    post = get_object_or_404(Post, pk=pk)
    
    if post.author != request.user:
        raise Http404("You can only delete your own posts.")
    
    if request.method == "POST":
        post.is_deleted = True
        post.save()
        return redirect("forum:feed")
    
    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {"post": post, "categories": categories, "categories_count": Post.objects.filter(is_deleted=False).count(), "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]}
    return render(request, "forum/post_delete.html", context)


# -----------------------------------------------------------------------
# Edit Reply
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def reply_edit(request, reply_id):
    """Edit a reply (only by author)."""
    reply = get_object_or_404(Reply, pk=reply_id)
    
    if reply.author != request.user:
        raise Http404("You can only edit your own replies.")
    
    if request.method == "POST":
        form = ReplyForm(request.POST, instance=reply)
        if form.is_valid():
            form.save()
            return redirect("forum:post_detail", pk=reply.post.pk)
    else:
        form = ReplyForm(instance=reply)
    
    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {"form": form, "reply": reply, "categories": categories, "categories_count": Post.objects.filter(is_deleted=False).count(), "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]}
    return render(request, "forum/reply_edit.html", context)


@login_required(login_url="account:login")
def reply_delete(request, reply_id):
    """Delete a reply (soft delete - only by author)."""
    reply = get_object_or_404(Reply, pk=reply_id)
    
    if reply.author != request.user:
        raise Http404("You can only delete your own replies.")
    
    post_pk = reply.post.pk
    
    if request.method == "POST":
        reply.is_deleted = True
        reply.save()
        return redirect("forum:post_detail", pk=post_pk)
    
    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {"reply": reply, "categories": categories, "categories_count": Post.objects.filter(is_deleted=False).count(), "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]}
    return render(request, "forum/reply_delete.html", context)


@login_required(login_url="account:login")
def post_create(request):
    """Create a new post (Ask a question)."""
    form = PostForm()
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.author = request.user
            new_post.save()
            return redirect("forum:post_detail", pk=new_post.pk)

    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {
        "form": form,
        "categories": categories,
        "categories_count": Post.objects.filter(is_deleted=False).count(),
        "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40],
        "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6],
        "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6],
    }
    return render(request, "forum/post_create.html", context)
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def flag_content(request, content_type, content_id):
    """Report inappropriate content (post or reply)."""
    if content_type == "post":
        content = get_object_or_404(Post, pk=content_id)
        post = content
        reply = None
    elif content_type == "reply":
        content = get_object_or_404(Reply, pk=content_id)
        reply = content
        post = None
    else:
        raise Http404("Invalid content type.")
    
    if request.method == "POST":
        reason = request.POST.get("reason")
        description = request.POST.get("description", "")
        
        if not reason:
            return render(request, "forum/flag_content.html", {"content_type": content_type, "content": content, "error": "Please select a reason.", "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]})
        
        # Check if already reported
        FlagReport.objects.get_or_create(
            reporter=request.user,
            content_type=content_type,
            post=post,
            reply=reply,
            defaults={"reason": reason, "description": description},
        )
        
        categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
        return render(request, "forum/flag_success.html", {"content": content, "categories": categories, "categories_count": Post.objects.filter(is_deleted=False).count(), "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]})
    
    categories = Category.objects.annotate(post_count=Count('posts', filter=Q(posts__is_deleted=False)))
    context = {"content_type": content_type, "content": content, "reason_choices": FlagReport.REASON_CHOICES, "categories": categories, "categories_count": Post.objects.filter(is_deleted=False).count(), "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40], "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6], "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]}
    return render(request, "forum/flag_content.html", context)


# -----------------------------------------------------------------------
# Moderation Dashboard (for staff only)
@login_required(login_url="account:login")
def moderation_dashboard(request):
    if not request.user.is_staff:
        raise Http404("Access denied.")

    unresolved_reports = FlagReport.objects.filter(resolved=False).select_related("reporter", "post", "reply")
    report_count = unresolved_reports.count()
    unverified_posts = Post.objects.filter(flag_reports__resolved=False).distinct()
    top_users = request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]

    context = {
        "report_count": report_count,
        "unresolved_reports": unresolved_reports,
        "unverified_posts": unverified_posts,
        "top_users": top_users,
    }
    return render(request, "forum/moderation_dashboard.html", context)


@login_required(login_url="account:login")
def resolve_report(request, report_id):
    if not request.user.is_staff:
        raise Http404("Access denied.")

    report = get_object_or_404(FlagReport, pk=report_id)
    report.resolved = True
    report.action_taken = "Reviewed by moderator"
    report.save(update_fields=["resolved", "action_taken"])

    return redirect("forum:moderation_dashboard")
# -----------------------------------------------------------------------
# Conversation map feature removed
