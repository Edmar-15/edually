# forum/views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from collections import defaultdict
from django.db.models import Q, Count, F
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import Category, Post, PostUpvote, Reply, ReplyUpvote, FlagReport
from .forms import PostForm, ReplyForm
from account.models import Notification

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def is_ajax(request):
    """Return True if the request is AJAX (X‑Requested‑With header)."""
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


# -------------------------------------------------------------------------
# Feed – list + search + pagination (now AJAX‑aware)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def feed(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("cat", "")
    show_unanswered = request.GET.get("unanswered", "").lower() in ["1", "true"]
    sort_by = request.GET.get("sort", "latest")      # latest, upvotes, replies

    posts_qs = (
        Post.objects.select_related("author", "category")
        .filter(is_deleted=False)
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

    # ----- unanswered ------------------------------------------------------
    if show_unanswered:
        posts_qs = posts_qs.filter(replies_cnt=0)

    # ----- sorting ---------------------------------------------------------
    if sort_by == "upvotes":
        posts_qs = posts_qs.order_by("-upvotes", "-created_at")
    elif sort_by == "replies":
        posts_qs = posts_qs.order_by("-replies_cnt", "-created_at")
    else:   # latest
        posts_qs = posts_qs.order_by("-created_at")

    # ----- pagination ------------------------------------------------------
    paginator = Paginator(posts_qs, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Up‑vote set for the logged‑in user (so the UI can show his votes)
    if request.user.is_authenticated:
        user_post_upvotes = set(
            PostUpvote.objects.filter(voter=request.user)
            .values_list("post_id", flat=True)
        )
    else:
        user_post_upvotes = set()

    categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__is_deleted=False))
    )

    # Exclude admin/staff users from the top contributors list
    top_users = request.user.__class__.objects.filter(is_active=True, is_superuser=False, is_staff=False).order_by("-karma")[:6]

    active_category_name = None
    if category_slug:
        active_category_name = categories.filter(slug=category_slug).values_list('name', flat=True).first()

    context = {
        "posts": page_obj,
        "categories": categories,
        "categories_count": Post.objects.filter(is_deleted=False).count(),
        "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40],
        "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6],
        "top_users": top_users,
        "search_query": query,
        "active_category": category_slug,
        "active_category_name": active_category_name,
        "show_unanswered": show_unanswered,
        "sort_by": sort_by,
        "paginator": paginator,
        "page_obj": page_obj,
        "user_post_upvotes": user_post_upvotes,
    }

    # ---------- AJAX response (only the list+pagination) --------------------
    if is_ajax(request):
        html = render_to_string(
            "forum/partials/post_list.html",
            {
                "posts": page_obj,
                "user_post_upvotes": user_post_upvotes,
                "request": request,
            },
            request=request,
        )
        return JsonResponse({"html": html})

    return render(request, "forum/feed.html", context)


# -------------------------------------------------------------------------
# Post Detail – show a single post + its replies + reply form (AJAX‑aware)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related("author", "category")
        .prefetch_related("replies__author"),
        pk=pk,
    )
    if post.is_deleted:
        raise Http404("This post has been deleted.")

    reply_form = ReplyForm()

    # -----------------------------------------------------------------
    # Process a new reply – always AJAX response
    # -----------------------------------------------------------------
    if request.method == "POST":
        reply_form = ReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.author = request.user
            reply.post = post
            reply.save()                     # signals bump replies_cnt

            if post.author != request.user:
                Notification.objects.create(
                    recipient=post.author,
                    actor=request.user,
                    verb="replied to your post",
                    target_post=post,
                    target_reply=reply,
                    url=reverse("forum:post_detail", args=[post.pk]) + f"#reply-{reply.pk}",
                )

            # Render the newly created reply item
            html = render_to_string(
                "forum/partials/reply_item.html",
                {"reply": reply,
                 "user_reply_upvotes": set(),
                 "request": request},
                request=request,
            )
            post.refresh_from_db()
            return JsonResponse(
                {"success": True, "html": html, "replies_cnt": post.replies_cnt},
                status=201,
            )
        else:
            # Return form errors inside the modal
            html = render_to_string(
                "forum/partials/post_detail.html",
                {
                    "post": post,
                    "replies": post.replies.filter(is_deleted=False),
                    "reply_form": reply_form,
                    "user_post_upvotes": set(),
                    "user_reply_upvotes": set(),
                },
                request=request,
            )
            return JsonResponse({"success": False, "html": html}, status=400)

    # -----------------------------------------------------------------
    # GET – return post‑detail fragment for modal
    # -----------------------------------------------------------------
    user_post_upvotes = set()
    user_reply_upvotes = set()
    if request.user.is_authenticated:
        user_post_upvotes = set(
            PostUpvote.objects.filter(voter=request.user).values_list("post_id", flat=True)
        )
        reply_ids = post.replies.filter(is_deleted=False).values_list("id", flat=True)
        user_reply_upvotes = set(
            ReplyUpvote.objects.filter(reply_id__in=reply_ids, voter=request.user)
            .values_list("reply_id", flat=True)
        )

    context = {
        "post": post,
        "replies": post.replies.filter(is_deleted=False),
        "reply_form": reply_form,
        "user_post_upvotes": user_post_upvotes,
        "user_reply_upvotes": user_reply_upvotes,
    }
    # If this is an AJAX modal request, render the fragment for the modal.
    context["in_modal"] = is_ajax(request)
    if context["in_modal"]:
        html = render_to_string("forum/partials/post_detail.html", context, request=request)
        return JsonResponse({"html": html})
    return render(request, "forum/post_detail_page.html", context)


# -------------------------------------------------------------------------
# Create a new post (AJAX‑aware)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def post_create(request):
    """
    AJAX‑only view – GET returns the empty post form, POST creates a post.
    """
    if request.method == "GET":
        form = PostForm()
        html = render_to_string("forum/partials/post_form.html", {"form": form}, request=request)
        return JsonResponse({"html": html})

    # POST – create a new post
    form = PostForm(request.POST)
    if form.is_valid():
        new_post = form.save(commit=False)
        new_post.author = request.user
        new_post.save()
        html = render_to_string(
            "forum/partials/post_item.html",
            {"post": new_post, "user_post_upvotes": set(), "request": request},
            request=request,
        )
        return JsonResponse({"success": True, "html": html}, status=201)

    # Form error – return the form markup with errors
    html = render_to_string("forum/partials/post_form.html", {"form": form}, request=request)
    return JsonResponse({"success": False, "html": html}, status=400)

# -------------------------------------------------------------------------
# Edit a post (standard page – works as a fallback for non‑AJAX)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def post_edit(request, pk):
    """
    AJAX view for editing a post.
    GET – returns the edit form (modal).
    POST – saves and returns the refreshed post‑detail fragment.
    """
    post = get_object_or_404(Post, pk=pk)
    if post.author != request.user:
        raise Http404("You can only edit your own posts.")

    if request.method == "GET":
        form = PostForm(instance=post)
        html = render_to_string("forum/partials/post_edit_form.html", {"form": form, "post": post}, request=request)
        return JsonResponse({"html": html})

    # POST – save changes
    form = PostForm(request.POST, instance=post)
    if form.is_valid():
        form.save()
        # Return the full post‑detail view so the modal can refresh
        reply_form = ReplyForm()
        user_post_upvotes = set(
            PostUpvote.objects.filter(voter=request.user).values_list("post_id", flat=True)
        )
        reply_ids = post.replies.filter(is_deleted=False).values_list("id", flat=True)
        user_reply_upvotes = set(
            ReplyUpvote.objects.filter(reply_id__in=reply_ids, voter=request.user)
            .values_list("reply_id", flat=True)
        )
        context = {
            "post": post,
            "replies": post.replies.filter(is_deleted=False),
            "reply_form": reply_form,
            "user_post_upvotes": user_post_upvotes,
            "user_reply_upvotes": user_reply_upvotes,
        }
        html = render_to_string("forum/partials/post_detail.html", context, request=request)
        return JsonResponse({"success": True, "html": html})

    # Form error – re‑render edit form with errors
    html = render_to_string("forum/partials/post_edit_form.html", {"form": form, "post": post}, request=request)
    return JsonResponse({"success": False, "html": html}, status=400)


# -------------------------------------------------------------------------
# Delete a post (soft delete – AJAX‑aware)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author != request.user:
        raise Http404("You can only delete your own posts.")

    if request.method == "POST":
        post.is_deleted = True
        post.save()
        if is_ajax(request):
            return JsonResponse({"success": True, "deleted_id": post.pk})
        return redirect("forum:feed")

    # GET – return confirmation modal content as JSON
    html = render_to_string(
        "forum/post_delete.html",
        {"post": post, "request": request},
        request=request,
    )
    return JsonResponse({"html": html})


@login_required(login_url="account:login")
@user_passes_test(lambda u: u.is_authenticated and u.is_teacher_member)
@require_http_methods(["POST"])
def verify_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.verified = True
    post.flagged = False
    post.flag_reason = ""
    post.save(update_fields=["verified", "flagged", "flag_reason"])

    FlagReport.objects.filter(resolved=False, post=post).update(
        resolved=True,
        action_taken="Verified by teacher",
    )

    if is_ajax(request):
        return JsonResponse({"success": True, "post_id": post.pk, "verified": True})
    return redirect(request.META.get("HTTP_REFERER", reverse("forum:post_detail", args=[post.pk])))


# -------------------------------------------------------------------------
# Edit a reply (standard page – fallback)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def reply_edit(request, reply_id):
    reply = get_object_or_404(Reply, pk=reply_id)
    if reply.author != request.user:
        raise Http404("You can only edit your own replies.")

    if request.method == "POST":
        form = ReplyForm(request.POST, instance=reply)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                html = render_to_string(
                    "forum/partials/reply_item.html",
                    {
                        "reply": reply,
                        "user_reply_upvotes": set(),
                        "request": request,
                    },
                    request=request,
                )
                return JsonResponse({"success": True, "html": html})
            return redirect(reverse("forum:post_detail", args=[reply.post.pk]) + f"#reply-{reply.pk}")
    else:
        form = ReplyForm(instance=reply)

    categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__is_deleted=False))
    )
    context = {
        "form": form,
        "reply": reply,
        "categories": categories,
        "categories_count": Post.objects.filter(is_deleted=False).count(),
        "recent_threads": Post.objects.filter(is_deleted=False).order_by('-created_at')[:40],
        "recent_posts": Post.objects.filter(is_deleted=False).order_by('-created_at')[:6],
        "top_users": request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6],
    }
    return render(request, "forum/reply_edit.html", context)


# -------------------------------------------------------------------------
# Delete a reply (soft delete – AJAX‑aware)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def reply_delete(request, reply_id):
    reply = get_object_or_404(Reply, pk=reply_id)
    if reply.author != request.user:
        raise Http404("You can only delete your own replies.")

    if request.method == "POST":
        reply.is_deleted = True
        reply.save()
        if is_ajax(request):
            return JsonResponse({"success": True, "deleted_id": reply.pk})
        return redirect("forum:post_detail", pk=reply.post.pk)

    # GET – return confirmation modal content as JSON
    html = render_to_string(
        "forum/reply_delete.html",
        {"reply": reply, "request": request},
        request=request,
    )
    return JsonResponse({"html": html})


# -------------------------------------------------------------------------
# Up‑vote – post (already AJAX; unchanged)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
@require_http_methods(["POST"])
def upvote(request, pk):
    post = get_object_or_404(Post, pk=pk)
    upvote, created = PostUpvote.objects.get_or_create(post=post, voter=request.user)
    if not created:
        upvote.delete()
        has_upvoted = False
    else:
        has_upvoted = True

    post.refresh_from_db()
    return JsonResponse({
        "success": True,
        "upvotes": post.upvotes,
        "has_upvoted": has_upvoted,
        "post_id": post.pk,
    })


# -------------------------------------------------------------------------
# Up‑vote – reply (already AJAX; unchanged)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
@require_http_methods(["POST"])
def reply_upvote(request, reply_id):
    reply = get_object_or_404(Reply, pk=reply_id)
    upvote, created = ReplyUpvote.objects.get_or_create(reply=reply, voter=request.user)
    if not created:
        upvote.delete()
        has_upvoted = False
    else:
        has_upvoted = True

    reply.refresh_from_db()
    return JsonResponse({
        "success": True,
        "upvotes": reply.upvotes,
        "has_upvoted": has_upvoted,
        "reply_id": reply.pk,
    })


# -------------------------------------------------------------------------
# Flag content (AJAX‑aware)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
def flag_content(request, content_type, content_id):
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

    if request.user.is_authenticated and request.user.is_teacher_member and content_type == "post":
        return HttpResponseForbidden("Teachers cannot report posts.")

    if request.method == "POST":
        reason = request.POST.get("reason")
        description = request.POST.get("description", "")
        if not reason:
            # Validation error – send back the form with an error message
            html = render_to_string(
                "forum/flag_content.html",
                {
                    "content_type": content_type,
                    "content": content,
                    "error": "Please select a reason.",
                    "reason_choices": FlagReport.REASON_CHOICES,
                    "request": request,
                },
                request=request,
            )
            return JsonResponse({"success": False, "html": html}, status=400)

        report, created = FlagReport.objects.get_or_create(
            reporter=request.user,
            content_type=content_type,
            post=post,
            reply=reply,
            defaults={"reason": reason, "description": description},
        )

        if content_type == "post" and post:
            post.flagged = True
            post.flag_reason = reason
            post.save(update_fields=["flagged", "flag_reason"])

        if is_ajax(request):
            html = render_to_string(
                "forum/flag_success_fragment.html",
                {"content": content, "request": request, "already_reported": not created},
                request=request,
            )
            return JsonResponse({"success": True, "html": html})

        # non‑AJAX fallback – render success page
        categories = Category.objects.annotate(
            post_count=Count('posts', filter=Q(posts__is_deleted=False))
        )
        return render(request, "forum/flag_success.html", {"content": content, "categories": categories, "already_reported": not created})

    # GET – just return the form fragment (for modal)
    html = render_to_string(
        "forum/flag_content.html",
        {
            "content_type": content_type,
            "content": content,
            "reason_choices": FlagReport.REASON_CHOICES,
            "request": request,
        },
        request=request,
    )
    return JsonResponse({"html": html})


# -------------------------------------------------------------------------
# Moderation Dashboard (staff only – unchanged)
# -------------------------------------------------------------------------
@login_required(login_url="account:login")
@user_passes_test(lambda u:  u.is_authenticated and u.is_teacher_member)
def moderation_dashboard(request):
    unresolved_reports = FlagReport.objects.filter(resolved=False).select_related("reporter", "post", "reply").order_by("-created_at")
    report_count = unresolved_reports.count()
    flagged_posts_count = unresolved_reports.filter(content_type="post").values("post").distinct().count()
    flagged_replies_count = unresolved_reports.filter(content_type="reply").values("reply").distinct().count()
    unverified_posts = Post.objects.filter(flag_reports__resolved=False).distinct()
    top_users = request.user.__class__.objects.filter(is_active=True).order_by("-karma")[:6]

    grouped = defaultdict(lambda: {
        "content_type": None,
        "post": None,
        "reply": None,
        "reports": [],
        "latest_report": None,
        "reasons": [],
        "reporters": [],
    })
    for report in unresolved_reports:
        key = (report.content_type, report.post_id or report.reply_id)
        item = grouped[key]
        if item["content_type"] is None:
            item["content_type"] = report.content_type
            item["post"] = report.post
            item["reply"] = report.reply
        item["reports"].append(report)
        item["latest_report"] = report
        reason_display = report.get_reason_display()
        if reason_display not in item["reasons"]:
            item["reasons"].append(reason_display)
        reporter_name = report.reporter.get_full_name() or report.reporter.email
        if reporter_name not in item["reporters"]:
            item["reporters"].append(reporter_name)

    reported_items = sorted(grouped.values(), key=lambda item: item["latest_report"].created_at if item["latest_report"] else None, reverse=True)

    context = {
        "report_count": report_count,
        "flagged_posts_count": flagged_posts_count,
        "flagged_replies_count": flagged_replies_count,
        "reported_items": reported_items,
        "unverified_posts": unverified_posts,
        "top_users": top_users,
    }
    return render(request, "forum/moderation_dashboard.html", context)


@login_required(login_url="account:login")
@user_passes_test(lambda u:  u.is_authenticated and u.is_teacher_member)
def moderation_deleted_history(request):
    deleted_posts = (
        Post.objects.filter(is_deleted=True)
        .select_related("author", "category")
        .order_by("-updated_at")
    )
    deleted_replies = (
        Reply.objects.filter(is_deleted=True)
        .select_related("author", "post__author", "post__category")
        .order_by("-updated_at")
    )

    context = {
        "deleted_posts": deleted_posts,
        "deleted_replies": deleted_replies,
        "deleted_posts_count": deleted_posts.count(),
        "deleted_replies_count": deleted_replies.count(),
    }
    return render(request, "forum/moderation_deleted_history.html", context)


@login_required(login_url="account:login")
@user_passes_test(lambda u:  u.is_authenticated and u.is_teacher_member)
def moderation_deleted_content_detail(request, content_type, pk):
    if content_type == "post":
        deleted_item = get_object_or_404(Post, pk=pk, is_deleted=True)
        related_reports = FlagReport.objects.filter(post=deleted_item).order_by("-created_at")
    elif content_type == "reply":
        deleted_item = get_object_or_404(Reply, pk=pk, is_deleted=True)
        related_reports = FlagReport.objects.filter(reply=deleted_item).order_by("-created_at")
    else:
        raise Http404("Invalid content type")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "restore":
            deleted_item.is_deleted = False
            deleted_item.save(update_fields=["is_deleted"])
            return redirect("forum:moderation_deleted_history")

    context = {
        "content_type": content_type,
        "deleted_item": deleted_item,
        "related_reports": related_reports,
    }
    return render(request, "forum/moderation_deleted_content_detail.html", context)


@login_required(login_url="account:login")
@user_passes_test(lambda u:  u.is_authenticated and u.is_teacher_member)
def resolve_report(request, report_id):
    report = get_object_or_404(FlagReport, pk=report_id)
    action = request.POST.get("action", "dismiss") if request.method == "POST" else "dismiss"
    content_type = report.content_type
    post = report.post
    reply = report.reply

    if content_type == "post":
        report_qs = FlagReport.objects.filter(resolved=False, post=post)
    else:
        report_qs = FlagReport.objects.filter(resolved=False, reply=reply)

    if request.method == "POST":
        if action == "delete":
            if content_type == "post" and post:
                post.is_deleted = True
                post.save(update_fields=["is_deleted"])
                action_taken = "Content removed by moderator"
            elif content_type == "reply" and reply:
                reply.is_deleted = True
                reply.save(update_fields=["is_deleted"])
                action_taken = "Reply removed by moderator"
            else:
                action_taken = "Reviewed by moderator"
        elif action == "verify" and content_type == "post" and post:
            post.verified = True
            post.flagged = False
            post.flag_reason = ""
            post.save(update_fields=["verified", "flagged", "flag_reason"])
            action_taken = "Post verified by moderator"
        else:
            action_taken = "Report dismissed by moderator"

        report_qs.update(resolved=True, action_taken=action_taken)
    else:
        report.resolved = True
        report.action_taken = "Reviewed by moderator"
        report.save(update_fields=["resolved", "action_taken"])

    if is_ajax(request):
        return JsonResponse({"success": True, "resolved_id": report.pk})
    return redirect("forum:moderation_dashboard")
