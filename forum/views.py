# forum/views.py
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect

from .models import Category, Post, PostUpvote, Reply
from .forms import PostForm, ReplyForm


# -----------------------------------------------------------------------
# Feed – list + search + pagination (unchanged, only tiny comment)
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def feed(request):
    """
    Render the main forum page.

    * Supports keyword search (`?q=…`)
    * Supports category filtering (`?cat=…`)
    * Paginates 30 items per page
    """
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("cat", "")

    posts_qs = (
        Post.objects.select_related("author", "category")
        .order_by("-created_at")
    )

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

    # ----- pagination ------------------------------------------------------
    paginator = Paginator(posts_qs, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "posts": page_obj,
        "categories": Category.objects.all(),
        "search_query": query,
        "active_category": category_slug,
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

    context = {
        "post": post,
        "replies": post.replies.all(),
        "reply_form": reply_form,
        "categories": Category.objects.all(),
        "active_category": post.category.slug if post.category else "",
    }
    return render(request, "forum/post_detail.html", context)


# -----------------------------------------------------------------------
# Create – a simple page for “Ask a question”
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def post_create(request):
    form = PostForm()
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.author = request.user
            new_post.save()
            return redirect("forum:post_detail", pk=new_post.pk)

    context = {
        "form": form,
        "categories": Category.objects.all(),
    }
    return render(request, "forum/post_create.html", context)


# -----------------------------------------------------------------------
# Up‑vote – toggle (kept unchanged, just uses redirect back)
# -----------------------------------------------------------------------
@login_required(login_url="account:login")
def upvote(request, pk):
    post = get_object_or_404(Post, pk=pk)

    upvote, created = PostUpvote.objects.get_or_create(post=post, voter=request.user)
    if not created:                     # user already voted → remove it
        upvote.delete()
        post.upvotes = max(post.upvotes - 1, 0)
    else:                               # new vote
        post.upvotes = post.upvotes + 1
    post.save(update_fields=["upvotes"])

    # Return to the page the user came from (feed or detail)
    next_url = request.META.get("HTTP_REFERER", "/forum/feeds/")
    return redirect(next_url)
