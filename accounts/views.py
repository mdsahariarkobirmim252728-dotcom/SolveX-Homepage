from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST


# ----------------------------
# Helpers
# ----------------------------
def is_solver_user(user_id: int) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM solver_profiles WHERE user_id=%s LIMIT 1",
            [user_id],
        )
        return cursor.fetchone() is not None


def get_solver_profile(user_id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT professional_title, phone_number, skills, address, interested_in, experience, bio
            FROM solver_profiles
            WHERE user_id=%s
            LIMIT 1
            """,
            [user_id],
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "professional_title": row[0] or "",
        "phone_number": row[1] or "",
        "skills": row[2] or "",
        "address": row[3] or "",
        "interested_in": row[4] or "",
        "experience": row[5] or "",
        "bio": row[6] or "",
    }


# ============================================================
# Home
# ============================================================
def home_view(request):
    return render(request, "index.html")


# ============================================================
# Browse Problems
# ============================================================
def browse_problems_view(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title, description, budget, is_solved
            FROM problems
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()

    problems = [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "budget": r[3],
            "is_solved": r[4],
        }
        for r in rows
    ]
    return render(request, "browse.html", {"problems": problems})


# ============================================================
# Register
# ============================================================
def register_view(request):
    if request.method == "POST":
        full_name = request.POST.get("fullname", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        is_solver_checked = request.POST.get("is_solver") == "on"

        if not all([full_name, email, password, confirm_password]):
            messages.error(request, "Full Name, Email, and Password fields are required.")
            return redirect("register")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username=email).exists():
            messages.error(request, "This email is already registered.")
            return redirect("register")

        solver_payload = None
        if is_solver_checked:
            title = request.POST.get("professional_title", "").strip()
            phone = request.POST.get("phone_number", "").strip()
            skills = request.POST.get("skills", "").strip()
            address = request.POST.get("address", "").strip()
            interested_in = request.POST.get("interested_in", "").strip()
            experience = request.POST.get("experience", "").strip()
            bio = request.POST.get("bio", "").strip()

            if not all([title, phone, skills, address]):
                messages.error(request, "Title, Phone, Skills, and Address are required for Solvers.")
                return redirect("register")

            solver_payload = (title, phone, skills, address, interested_in, experience, bio)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=full_name,
                )

                if solver_payload:
                    title, phone, skills, address, interested_in, experience, bio = solver_payload
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO solver_profiles
                                (user_id, professional_title, phone_number, skills, address, interested_in, experience, bio)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                user.id,
                                title,
                                phone,
                                skills,
                                address,
                                interested_in or None,
                                experience or None,
                                bio or None,
                            ],
                        )

            messages.success(request, "Account created successfully! Please login.")
            return redirect("login")
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect("register")

    return render(request, "register.html")


# ============================================================
# Login
# ============================================================
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        user = authenticate(request, username=email, password=password)
        if user is None:
            messages.error(request, "Invalid email or password.")
            return redirect("login")

        login(request, user)
        messages.success(request, "Login successful!")
        return redirect("home")

    return render(request, "login.html")


# ============================================================
# Logout
# ============================================================
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("home")


# ============================================================
# Dashboard
# ============================================================
@login_required(login_url="login")
def dashboard_view(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                p.id, p.title, p.description, p.budget, p.is_solved,
                (SELECT COUNT(*) FROM bids b WHERE b.problem_id = p.id) AS total_bids,
                (SELECT COUNT(*) FROM bids b WHERE b.problem_id = p.id AND (b.status='Pending' OR b.status IS NULL)) AS pending_bids
            FROM problems p
            WHERE p.user_id = %s
            ORDER BY p.id DESC
            """,
            [request.user.id],
        )
        rows = cursor.fetchall()

    my_problems = [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "budget": r[3],
            "is_solved": r[4],
            "total_bids": r[5],
            "pending_bids": r[6],
        }
        for r in rows
    ]
    return render(request, "dashboard.html", {"my_problems": my_problems})


# ============================================================
# Post Problem
# ============================================================
@login_required(login_url="login")
def post_problem_view(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        budget = request.POST.get("budget", "").strip()

        if not title or not description or not budget:
            messages.error(request, "All fields are required.")
            return redirect("post_problem")

        try:
            budget_val = Decimal(budget)
        except (InvalidOperation, TypeError):
            messages.error(request, "Budget must be a valid number.")
            return redirect("post_problem")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO problems (title, description, budget, user_id)
                VALUES (%s, %s, %s, %s)
                """,
                [title, description, budget_val, request.user.id],
            )

        messages.success(request, "Problem posted successfully!")
        return redirect("browse_problems")

    return render(request, "post_problem.html")


# ============================================================
# Profile (update name)
# ============================================================
@login_required(login_url="login")
def profile_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()

        if not full_name:
            messages.error(request, "Name is required.")
            return redirect("profile")

        request.user.first_name = full_name
        request.user.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("profile")

    return render(request, "profile.html")


# ============================================================
# Forgot Password (session-based)
# ============================================================
def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            messages.error(request, "This email is not registered.")
            return redirect("forgot_password")

        request.session["reset_user_id"] = user.id
        messages.success(request, "Email found! Please set a new password.")
        return redirect("reset_new_password")

    return render(request, "forgot_password.html")


def reset_new_password_view(request):
    user_id = request.session.get("reset_user_id")
    if not user_id:
        messages.error(request, "Please enter your email first.")
        return redirect("forgot_password")

    if request.method == "POST":
        new_password = request.POST.get("new_password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        if not new_password or not confirm_password:
            messages.error(request, "Password fields cannot be empty.")
            return redirect("reset_new_password")

        if len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return redirect("reset_new_password")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("reset_new_password")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("forgot_password")

        user.set_password(new_password)
        user.save()
        request.session.pop("reset_user_id", None)

        messages.success(request, "Password reset successfully! Please login.")
        return redirect("login")

    return render(request, "reset_new_password.html")


# ============================================================
# Settings
# ============================================================
@login_required(login_url="login")
def settings_view(request):
    is_solver = is_solver_user(request.user.id)
    solver_profile = get_solver_profile(request.user.id)

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "change_email":
            new_email = request.POST.get("email", "").strip().lower()
            password = request.POST.get("password_for_email", "")

            if not new_email:
                messages.error(request, "Email is required.")
                return redirect("settings")

            if not request.user.check_password(password):
                messages.error(request, "Incorrect password. Email not updated.")
                return redirect("settings")

            if User.objects.filter(username=new_email).exclude(id=request.user.id).exists():
                messages.error(request, "This email is already in use.")
                return redirect("settings")

            request.user.username = new_email
            request.user.email = new_email
            request.user.save()
            messages.success(request, "Email updated successfully!")
            return redirect("settings")

        if form_type == "change_password":
            old_password = request.POST.get("old_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            if not request.user.check_password(old_password):
                messages.error(request, "Old password was incorrect.")
                return redirect("settings")

            if len(new_password) < 6:
                messages.error(request, "New password must be at least 6 characters.")
                return redirect("settings")

            if new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
                return redirect("settings")

            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully!")
            return redirect("settings")

        if form_type == "solver_profile":
            title = request.POST.get("professional_title", "").strip()
            phone = request.POST.get("phone_number", "").strip()
            skills = request.POST.get("skills", "").strip()
            address = request.POST.get("address", "").strip()
            interested_in = request.POST.get("interested_in", "").strip()
            experience = request.POST.get("experience", "").strip()
            bio = request.POST.get("bio", "").strip()

            if not all([title, phone, skills, address]):
                messages.error(request, "Title, Phone, Skills, and Address are required.")
                return redirect("settings")

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT 1 FROM solver_profiles WHERE user_id=%s LIMIT 1",
                            [request.user.id],
                        )
                        exists = cursor.fetchone() is not None

                        if exists:
                            cursor.execute(
                                """
                                UPDATE solver_profiles
                                SET professional_title=%s,
                                    phone_number=%s,
                                    skills=%s,
                                    address=%s,
                                    interested_in=%s,
                                    experience=%s,
                                    bio=%s
                                WHERE user_id=%s
                                """,
                                [
                                    title,
                                    phone,
                                    skills,
                                    address,
                                    interested_in or None,
                                    experience or None,
                                    bio or None,
                                    request.user.id,
                                ],
                            )
                            messages.success(request, "Solver profile updated successfully!")
                        else:
                            cursor.execute(
                                """
                                INSERT INTO solver_profiles
                                    (user_id, professional_title, phone_number, skills, address, interested_in, experience, bio)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                [
                                    request.user.id,
                                    title,
                                    phone,
                                    skills,
                                    address,
                                    interested_in or None,
                                    experience or None,
                                    bio or None,
                                ],
                            )
                            messages.success(request, "You are now registered as a Solver!")
            except Exception as e:
                messages.error(request, f"Failed to save solver profile: {str(e)}")

            return redirect("settings")

        messages.error(request, "Invalid form submission.")
        return redirect("settings")

    return render(
        request,
        "settings.html",
        {"is_solver": is_solver, "solver_profile": solver_profile},
    )


# ============================================================
# Mark Solved
# ============================================================
@login_required(login_url="login")
@require_POST
def mark_solved_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE problems
            SET is_solved = 1
            WHERE id = %s AND user_id = %s
            """,
            [id, request.user.id],
        )

    messages.success(request, "Problem marked as solved!")
    return redirect("dashboard")


# ============================================================
# Delete Problem
# ============================================================
@login_required(login_url="login")
@require_POST
def delete_problem_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM problems
            WHERE id = %s AND user_id = %s
            """,
            [id, request.user.id],
        )

    messages.success(request, "Problem deleted successfully.")
    return redirect("dashboard")


# ============================================================
# Edit Problem
# ============================================================
@login_required(login_url="login")
def edit_problem_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT title, description, budget
            FROM problems
            WHERE id = %s AND user_id = %s
            """,
            [id, request.user.id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Problem not found or access denied.")
        return redirect("dashboard")

    problem_data = {"id": id, "title": row[0], "description": row[1], "budget": row[2]}

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        budget = request.POST.get("budget", "").strip()

        if not title or not description or not budget:
            messages.error(request, "All fields are required.")
            return redirect("edit_problem", id=id)

        try:
            budget_val = Decimal(budget)
        except (InvalidOperation, TypeError):
            messages.error(request, "Budget must be a valid number.")
            return redirect("edit_problem", id=id)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE problems
                SET title = %s, description = %s, budget = %s
                WHERE id = %s AND user_id = %s
                """,
                [title, description, budget_val, id, request.user.id],
            )

        messages.success(request, "Problem updated successfully!")
        return redirect("dashboard")

    return render(request, "edit_problem.html", {"problem": problem_data})


# ============================================================
# Problem Detail (Owner bids + solver applied state)
# ============================================================
def problem_detail_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.id, p.title, p.description, p.budget, p.is_solved,
                   u.first_name, u.email, u.id,
                   p.accepted_bid_id
            FROM problems p
            JOIN auth_user u ON p.user_id = u.id
            WHERE p.id = %s
            """,
            [id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Problem not found.")
        return redirect("browse_problems")

    problem = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "budget": row[3],
        "is_solved": row[4],
        "author_name": row[5],
        "author_email": row[6],
        "author_id": row[7],
        "accepted_bid_id": row[8],
    }

    is_owner = request.user.is_authenticated and request.user.id == problem["author_id"]
    is_solver = request.user.is_authenticated and is_solver_user(request.user.id)

    bids = []
    if is_owner:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    b.id, b.amount, b.proposal_text, b.created_at,
                    COALESCE(b.status, 'Pending') AS status,
                    u.first_name, u.email, u.id,
                    sp.professional_title, sp.phone_number, sp.skills, sp.address,
                    sp.interested_in, sp.experience, sp.bio
                FROM bids b
                JOIN auth_user u ON b.user_id = u.id
                LEFT JOIN solver_profiles sp ON sp.user_id = u.id
                WHERE b.problem_id = %s
                ORDER BY b.id DESC
                """,
                [id],
            )
            rows = cursor.fetchall()

        bids = [
            {
                "id": r[0],
                "amount": r[1],
                "proposal_text": r[2],
                "created_at": r[3],
                "status": r[4],
                "bidder_name": r[5],
                "bidder_email": r[6],
                "bidder_id": r[7],
                "solver_title": r[8] or "",
                "solver_phone": r[9] or "",
                "solver_skills": r[10] or "",
                "solver_address": r[11] or "",
                "solver_interested_in": r[12] or "",
                "solver_experience": r[13] or "",
                "solver_bio": r[14] or "",
                "is_solver": True if r[8] is not None else False,
            }
            for r in rows
        ]

    my_bid = None
    if request.user.is_authenticated and not is_owner:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, amount, proposal_text, created_at, COALESCE(status,'Pending')
                FROM bids
                WHERE problem_id=%s AND user_id=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                [id, request.user.id],
            )
            r = cursor.fetchone()

        if r:
            my_bid = {
                "id": r[0],
                "amount": r[1],
                "proposal_text": r[2],
                "created_at": r[3],
                "status": r[4],
            }

    return render(
        request,
        "problem_detail.html",
        {
            "problem": problem,
            "is_owner": is_owner,
            "is_solver": is_solver,
            "bids": bids,
            "my_bid": my_bid,
        },
    )


# ============================================================
# Submit Bid (prevent duplicates, allow reapply after reject)
# ============================================================
@login_required(login_url="login")
@require_POST
def submit_bid_view(request, problem_id):
    if not is_solver_user(request.user.id):
        messages.error(request, "Only registered Problem Solvers can place a bid.")
        return redirect("problem_detail", id=problem_id)

    amount_raw = request.POST.get("amount", "").strip()
    proposal = request.POST.get("proposal", "").strip()

    if not all([amount_raw, proposal]):
        messages.error(request, "Amount and proposal are required.")
        return redirect("problem_detail", id=problem_id)

    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, TypeError):
        messages.error(request, "Amount must be a valid number.")
        return redirect("problem_detail", id=problem_id)

    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id, title, is_solved FROM problems WHERE id = %s", [problem_id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Problem not found.")
        return redirect("browse_problems")

    owner_id, problem_title, is_solved = row

    if int(is_solved) == 1:
        messages.error(request, "Bidding is closed for this problem.")
        return redirect("problem_detail", id=problem_id)

    if owner_id == request.user.id:
        messages.error(request, "You cannot bid on your own problem.")
        return redirect("problem_detail", id=problem_id)

    # Check existing bid
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, COALESCE(status,'Pending')
            FROM bids
            WHERE problem_id=%s AND user_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            [problem_id, request.user.id],
        )
        existing = cursor.fetchone()

    if existing:
        existing_bid_id, existing_status = existing

        if existing_status == "Pending":
            messages.info(request, "You already applied for this problem.")
            return redirect("problem_detail", id=problem_id)

        if existing_status == "Accepted":
            messages.info(request, "Your bid has already been accepted for this problem.")
            return redirect("problem_detail", id=problem_id)

        if existing_status == "Rejected":
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE bids
                            SET amount=%s, proposal_text=%s, status='Pending', created_at=CURRENT_TIMESTAMP
                            WHERE id=%s AND user_id=%s
                            """,
                            [amount, proposal, existing_bid_id, request.user.id],
                        )
                        cursor.execute(
                            """
                            INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            [
                                owner_id,
                                request.user.id,
                                problem_id,
                                existing_bid_id,
                                f"New bid received on: {problem_title}",
                            ],
                        )

                messages.success(request, "Applied again successfully!")
            except Exception as e:
                messages.error(request, f"Error placing bid: {str(e)}")

            return redirect("problem_detail", id=problem_id)

    # No existing bid -> insert new
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO bids (problem_id, user_id, amount, proposal_text, status)
                    VALUES (%s, %s, %s, %s, 'Pending')
                    """,
                    [problem_id, request.user.id, amount, proposal],
                )
                bid_id = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        owner_id,
                        request.user.id,
                        problem_id,
                        bid_id,
                        f"New bid received on: {problem_title}",
                    ],
                )

        messages.success(request, "Bid placed successfully!")
    except Exception as e:
        messages.error(request, f"Error placing bid: {str(e)}")

    return redirect("problem_detail", id=problem_id)


# ============================================================
# Cancel Bid (Pending only)
# ============================================================
@login_required(login_url="login")
@require_POST
def cancel_bid_view(request, bid_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT b.problem_id,
                   b.user_id AS bidder_id,
                   COALESCE(b.status,'Pending') AS status_now,
                   p.is_solved,
                   p.user_id AS owner_id,
                   p.title
            FROM bids b
            JOIN problems p ON b.problem_id = p.id
            WHERE b.id = %s
            """,
            [bid_id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Bid not found.")
        return redirect("dashboard")

    problem_id, bidder_id, status_now, is_solved, owner_id, problem_title = row

    if bidder_id != request.user.id:
        messages.error(request, "Access denied.")
        return redirect("problem_detail", id=problem_id)

    if int(is_solved) == 1:
        messages.error(request, "Bidding is closed for this problem.")
        return redirect("problem_detail", id=problem_id)

    if status_now != "Pending":
        messages.info(request, "You can only cancel a pending application.")
        return redirect("problem_detail", id=problem_id)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM bids
                    WHERE id=%s AND user_id=%s AND (status='Pending' OR status IS NULL)
                    """,
                    [bid_id, request.user.id],
                )
                cursor.execute("DELETE FROM notifications WHERE bid_id=%s", [bid_id])

                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        owner_id,
                        request.user.id,
                        problem_id,
                        None,
                        f"An application was withdrawn for: {problem_title}",
                    ],
                )

        messages.success(request, "Application canceled successfully.")
    except Exception as e:
        messages.error(request, f"Cancel failed: {str(e)}")

    return redirect("problem_detail", id=problem_id)


# ============================================================
# Bid Action (Accept/Reject/Cancel Acceptance)
# ============================================================

@login_required(login_url="login")
@require_POST
def bid_action_view(request, bid_id):
    action = request.POST.get("action")
    if action not in ("accept", "reject", "cancel"):
        messages.error(request, "Invalid action.")
        return redirect("dashboard")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                b.problem_id,
                p.user_id AS owner_id,
                b.user_id AS bidder_id,
                p.title,
                COALESCE(b.status, 'Pending') AS status_now,
                b.amount
            FROM bids b
            JOIN problems p ON b.problem_id = p.id
            WHERE b.id = %s
            """,
            [bid_id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Bid not found.")
        return redirect("dashboard")

    problem_id, owner_id, bidder_id, problem_title, status_now, bid_amount = row

    if owner_id != request.user.id:
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                if action == "accept":
                    if status_now != "Pending":
                        messages.info(request, "This bid is not pending.")
                        return redirect("problem_detail", id=problem_id)

                    # Accept selected bid
                    cursor.execute("UPDATE bids SET status='Accepted' WHERE id=%s", [bid_id])

                    # Reject other pending bids
                    cursor.execute(
                        """
                        UPDATE bids
                        SET status='Rejected'
                        WHERE problem_id=%s AND id<>%s AND (status='Pending' OR status IS NULL)
                        """,
                        [problem_id, bid_id],
                    )

                    # Close bidding
                    cursor.execute(
                        "UPDATE problems SET is_solved=1, accepted_bid_id=%s WHERE id=%s",
                        [bid_id, problem_id],
                    )

                    # Create contract (idempotent: do not create duplicates)
                    cursor.execute(
                        """
                        SELECT id
                        FROM contracts
                        WHERE problem_id=%s AND status<>'Canceled'
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        [problem_id],
                    )
                    existing_contract = cursor.fetchone()

                    if not existing_contract:
                        cursor.execute(
                            """
                            INSERT INTO contracts
                                (problem_id, owner_id, solver_id, accepted_bid_id, agreed_amount, status, payment_status)
                            VALUES
                                (%s, %s, %s, %s, %s, 'Active', 'Pending')
                            """,
                            [problem_id, owner_id, bidder_id, bid_id, bid_amount],
                        )

                    # Notify accepted solver
                    cursor.execute(
                        """
                        INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            bidder_id,
                            request.user.id,
                            problem_id,
                            bid_id,
                            f"Your bid was ACCEPTED for: {problem_title}. A contract has been started.",
                        ],
                    )

                    messages.success(request, "Bid accepted! Contract started and bidding closed.")
                    return redirect("problem_detail", id=problem_id)

                if action == "reject":
                    if status_now != "Pending":
                        messages.info(request, "This bid is not pending.")
                        return redirect("problem_detail", id=problem_id)

                    cursor.execute("UPDATE bids SET status='Rejected' WHERE id=%s", [bid_id])

                    cursor.execute(
                        """
                        INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            bidder_id,
                            request.user.id,
                            problem_id,
                            bid_id,
                            f"Your bid was REJECTED for: {problem_title}",
                        ],
                    )

                    messages.success(request, "Bid rejected.")
                    return redirect("problem_detail", id=problem_id)

                if action == "cancel":
                    if status_now != "Accepted":
                        messages.info(request, "This bid is not in Accepted state.")
                        return redirect("problem_detail", id=problem_id)

                    cursor.execute("UPDATE bids SET status='Pending' WHERE id=%s", [bid_id])
                    cursor.execute("UPDATE problems SET is_solved=0, accepted_bid_id=NULL WHERE id=%s", [problem_id])

                    cursor.execute(
                        "UPDATE bids SET status='Pending' WHERE problem_id=%s AND status='Rejected'",
                        [problem_id],
                    )

                    cursor.execute(
                        """
                        INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            bidder_id,
                            request.user.id,
                            problem_id,
                            bid_id,
                            f"Your accepted bid was CANCELED for: {problem_title}",
                        ],
                    )

                    messages.success(request, "Accepted bid canceled. Bidding is now open again.")
                    return redirect("problem_detail", id=problem_id)

    except Exception as e:
        messages.error(request, f"Action failed: {str(e)}")

    return redirect("problem_detail", id=problem_id)


# ============================================================
# Notifications list
# ============================================================
@login_required(login_url="login")
@require_POST
def report_user_view(request, user_id):
    if request.user.id == user_id:
        messages.error(request, "You cannot report yourself.")
        return redirect("public_profile", user_id=user_id)

    reason = request.POST.get("reason", "").strip()
    contract_id_raw = request.POST.get("contract_id", "").strip()

    if not reason:
        messages.error(request, "Report reason is required.")
        return redirect("public_profile", user_id=user_id)

    contract_id = None
    if contract_id_raw.isdigit():
        contract_id = int(contract_id_raw)

        # Optional safety: only allow attaching contract_id if reporter is part of that contract
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT owner_id, solver_id FROM contracts WHERE id=%s",
                [contract_id],
            )
            cr = cursor.fetchone()
        if not cr or request.user.id not in (cr[0], cr[1]):
            contract_id = None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM user_reports
            WHERE reported_user_id=%s AND reporter_user_id=%s AND status='Open'
            LIMIT 1
            """,
            [user_id, request.user.id],
        )
        exists = cursor.fetchone() is not None

    if exists:
        messages.info(request, "You already reported this user. It is under review.")
        return redirect("public_profile", user_id=user_id)

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_reports (reported_user_id, reporter_user_id, contract_id, reason, status)
                VALUES (%s, %s, %s, %s, 'Open')
                """,
                [user_id, request.user.id, contract_id, reason],
            )
        messages.success(request, "Report submitted successfully.")
    except Exception as e:
        messages.error(request, f"Failed to submit report: {str(e)}")

    return redirect("public_profile", user_id=user_id)


@login_required(login_url="login")
def contract_for_problem_view(request, problem_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, owner_id, solver_id
            FROM contracts
            WHERE problem_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            [problem_id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Contract not found.")
        return redirect("problem_detail", id=problem_id)

    contract_id, owner_id, solver_id = row

    if request.user.id not in (owner_id, solver_id):
        messages.error(request, "Access denied.")
        return redirect("problem_detail", id=problem_id)

    return redirect("contract_detail", contract_id=contract_id)

#=================================================
#contract_detail_view
#==========================================
@login_required(login_url="login")
def contract_detail_view(request, contract_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                c.id, c.problem_id, c.owner_id, c.solver_id, c.accepted_bid_id,
                c.agreed_amount, c.status, c.revision_count, c.max_revisions,
                c.payment_status, c.solution_text, c.owner_feedback,
                c.created_at, c.updated_at,
                p.title, p.description,
                ou.first_name, ou.email,
                su.first_name, su.email
            FROM contracts c
            JOIN problems p ON c.problem_id = p.id
            JOIN auth_user ou ON c.owner_id = ou.id
            JOIN auth_user su ON c.solver_id = su.id
            WHERE c.id = %s
            """,
            [contract_id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Contract not found.")
        return redirect("dashboard")

    contract = {
        "id": row[0],
        "problem_id": row[1],
        "owner_id": row[2],
        "solver_id": row[3],
        "accepted_bid_id": row[4],
        "agreed_amount": row[5],
        "status": row[6],
        "revision_count": row[7],
        "max_revisions": row[8],
        "payment_status": row[9],
        "solution_text": row[10] or "",
        "owner_feedback": row[11] or "",
        "created_at": row[12],
        "updated_at": row[13],
    }

    problem = {"id": row[1], "title": row[14], "description": row[15]}
    owner = {"name": row[16] or "Owner", "email": row[17] or "", "id": contract["owner_id"]}
    solver = {"name": row[18] or "Solver", "email": row[19] or "", "id": contract["solver_id"]}

    if request.user.id not in (contract["owner_id"], contract["solver_id"]):
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    is_owner = request.user.id == contract["owner_id"]

    return render(
        request,
        "contract_detail.html",
        {"contract": contract, "problem": problem, "owner": owner, "solver": solver, "is_owner": is_owner},
    )
#===================================
#contract_submit_work_view)
#==============================
@login_required(login_url="login")
@require_POST
def contract_submit_work_view(request, contract_id):
    solution_text = request.POST.get("solution_text", "").strip()
    if not solution_text:
        messages.error(request, "Submission text/link is required.")
        return redirect("contract_detail", contract_id=contract_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, problem_id, owner_id, solver_id, status
            FROM contracts
            WHERE id=%s
            """,
            [contract_id],
        )
        c = cursor.fetchone()

    if not c:
        messages.error(request, "Contract not found.")
        return redirect("dashboard")

    _cid, problem_id, owner_id, solver_id, status_now = c

    if request.user.id != solver_id:
        messages.error(request, "Only the solver can submit work.")
        return redirect("contract_detail", contract_id=contract_id)

    if status_now in ("Completed", "Canceled"):
        messages.error(request, "This contract is closed.")
        return redirect("contract_detail", contract_id=contract_id)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE contracts
                    SET solution_text=%s, status='Submitted'
                    WHERE id=%s AND solver_id=%s
                    """,
                    [solution_text, contract_id, request.user.id],
                )

                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [owner_id, request.user.id, problem_id, None, "Work submitted for your problem."],
                )

        messages.success(request, "Work submitted successfully.")
    except Exception as e:
        messages.error(request, f"Submit failed: {str(e)}")

    return redirect("contract_detail", contract_id=contract_id)
#======================================================
#contract_request_revision_view
#==================================================
@login_required(login_url="login")
@require_POST
def contract_request_revision_view(request, contract_id):
    feedback = request.POST.get("owner_feedback", "").strip()
    if not feedback:
        messages.error(request, "Feedback is required to request a revision.")
        return redirect("contract_detail", contract_id=contract_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT problem_id, owner_id, solver_id, accepted_bid_id,
                   revision_count, max_revisions, status
            FROM contracts
            WHERE id=%s
            """,
            [contract_id],
        )
        c = cursor.fetchone()

    if not c:
        messages.error(request, "Contract not found.")
        return redirect("dashboard")

    problem_id, owner_id, solver_id, accepted_bid_id, revision_count, max_revisions, status_now = c

    if request.user.id != owner_id:
        messages.error(request, "Only the owner can request revisions.")
        return redirect("contract_detail", contract_id=contract_id)

    if status_now in ("Completed", "Canceled"):
        messages.error(request, "This contract is closed.")
        return redirect("contract_detail", contract_id=contract_id)

    new_count = int(revision_count) + 1
    max_rev = int(max_revisions)
    will_cancel = new_count >= max_rev

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                if will_cancel:
                    cursor.execute(
                        """
                        UPDATE contracts
                        SET owner_feedback=%s,
                            revision_count=%s,
                            status='Canceled'
                        WHERE id=%s
                        """,
                        [feedback, new_count, contract_id],
                    )

                    # Re-open problem for bidding
                    cursor.execute(
                        "UPDATE problems SET is_solved=0, accepted_bid_id=NULL WHERE id=%s",
                        [problem_id],
                    )

                    # Optional: mark accepted bid as rejected
                    if accepted_bid_id:
                        cursor.execute("UPDATE bids SET status='Rejected' WHERE id=%s", [accepted_bid_id])

                    # Notify solver with feedback snippet
                    cursor.execute(
                        """
                        INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            solver_id,
                            request.user.id,
                            problem_id,
                            None,
                            f"Contract canceled after max revisions. Last feedback: {feedback[:180]}",
                        ],
                    )

                    messages.success(request, "Max revisions reached. Contract canceled and bidding reopened.")
                else:
                    cursor.execute(
                        """
                        UPDATE contracts
                        SET owner_feedback=%s,
                            revision_count=%s,
                            status='RevisionRequested'
                        WHERE id=%s
                        """,
                        [feedback, new_count, contract_id],
                    )

                    # Notify solver with feedback snippet
                    cursor.execute(
                        """
                        INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            solver_id,
                            request.user.id,
                            problem_id,
                            None,
                            f"Revision requested ({new_count}/{max_rev}): {feedback[:180]}",
                        ],
                    )

                    messages.success(request, "Revision requested.")
    except Exception as e:
        messages.error(request, f"Revision failed: {str(e)}")

    return redirect("contract_detail", contract_id=contract_id)
#==============================================================================
#contract_approve_view
#=============================================================================
@login_required(login_url="login")
@require_POST
def contract_approve_view(request, contract_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, problem_id, owner_id, solver_id, status, payment_status
            FROM contracts
            WHERE id=%s
            """,
            [contract_id],
        )
        c = cursor.fetchone()

    if not c:
        messages.error(request, "Contract not found.")
        return redirect("dashboard")

    _cid, problem_id, owner_id, solver_id, status_now, payment_status = c

    if request.user.id != owner_id:
        messages.error(request, "Only the owner can approve.")
        return redirect("contract_detail", contract_id=contract_id)

    if status_now in ("Canceled",):
        messages.error(request, "This contract is closed.")
        return redirect("contract_detail", contract_id=contract_id)

    # Idempotent: if already done, do nothing
    if payment_status == "Done":
        messages.info(request, "Payment is already confirmed as Done.")
        return redirect("contract_detail", contract_id=contract_id)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE contracts
                    SET status='Completed', payment_status='AwaitingConfirmation'
                    WHERE id=%s
                    """,
                    [contract_id],
                )

                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        solver_id,
                        request.user.id,
                        problem_id,
                        None,
                        "Owner marked the work as completed and marked payment as sent. Please confirm payment receipt.",
                    ],
                )

        messages.success(request, "Approved. Waiting for solver to confirm payment receipt.")
    except Exception as e:
        messages.error(request, f"Approve failed: {str(e)}")

    return redirect("contract_detail", contract_id=contract_id)
#=========================================================================
@login_required(login_url="login")
def admin_reports_view(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                r.id, r.reason, r.status, r.created_at,
                r.reported_user_id, ru.first_name, ru.email,
                r.reporter_user_id, au.first_name, au.email,
                r.contract_id
            FROM user_reports r
            JOIN auth_user ru ON r.reported_user_id = ru.id
            JOIN auth_user au ON r.reporter_user_id = au.id
            WHERE r.status='Open'
            ORDER BY r.id DESC
            """
        )
        rows = cursor.fetchall()

    reports = [
        {
            "id": x[0],
            "reason": x[1],
            "status": x[2],
            "created_at": x[3],
            "reported_id": x[4],
            "reported_name": x[5] or "User",
            "reported_email": x[6] or "",
            "reporter_id": x[7],
            "reporter_name": x[8] or "User",
            "reporter_email": x[9] or "",
            "contract_id": x[10],
        }
        for x in rows
    ]

    return render(request, "admin_reports.html", {"reports": reports})


@login_required(login_url="login")
@require_POST
def admin_report_action_view(request, report_id, action):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    if action not in ("resolve", "dismiss"):
        messages.error(request, "Invalid action.")
        return redirect("admin_reports")

    new_status = "Resolved" if action == "resolve" else "Dismissed"

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE user_reports SET status=%s WHERE id=%s",
            [new_status, report_id],
        )

    messages.success(request, f"Report marked as {new_status}.")
    return redirect("admin_reports")
#=========================================================================
@login_required(login_url="login")
def contract_for_problem_view(request, problem_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, owner_id, solver_id
            FROM contracts
            WHERE problem_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            [problem_id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Contract not found.")
        return redirect("problem_detail", id=problem_id)

    contract_id, owner_id, solver_id = row

    if request.user.id not in (owner_id, solver_id):
        messages.error(request, "Access denied.")
        return redirect("problem_detail", id=problem_id)

    return redirect("contract_detail", contract_id=contract_id)

#========================================================
#contract_detail_view
#===================================================
@login_required(login_url="login")
def contract_detail_view(request, contract_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                c.id, c.problem_id, c.owner_id, c.solver_id, c.accepted_bid_id,
                c.agreed_amount, c.status, c.revision_count, c.max_revisions,
                c.payment_status, c.solution_text, c.owner_feedback,
                c.created_at, c.updated_at,
                p.title, p.description,
                ou.first_name, ou.email,
                su.first_name, su.email
            FROM contracts c
            JOIN problems p ON c.problem_id = p.id
            JOIN auth_user ou ON c.owner_id = ou.id
            JOIN auth_user su ON c.solver_id = su.id
            WHERE c.id = %s
            """,
            [contract_id],
        )
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Contract not found.")
        return redirect("dashboard")

    contract = {
        "id": row[0],
        "problem_id": row[1],
        "owner_id": row[2],
        "solver_id": row[3],
        "accepted_bid_id": row[4],
        "agreed_amount": row[5],
        "status": row[6],
        "revision_count": row[7],
        "max_revisions": row[8],
        "payment_status": row[9],
        "solution_text": row[10] or "",
        "owner_feedback": row[11] or "",
        "created_at": row[12],
        "updated_at": row[13],
    }

    problem = {"id": row[1], "title": row[14], "description": row[15]}
    owner = {"name": row[16] or "Owner", "email": row[17] or "", "id": contract["owner_id"]}
    solver = {"name": row[18] or "Solver", "email": row[19] or "", "id": contract["solver_id"]}

    if request.user.id not in (contract["owner_id"], contract["solver_id"]):
        messages.error(request, "Access denied.")
        return redirect("dashboard")

    is_owner = request.user.id == contract["owner_id"]

    return render(
        request,
        "contract_detail.html",
        {"contract": contract, "problem": problem, "owner": owner, "solver": solver, "is_owner": is_owner},
    )

#===========================================================================================================
@login_required(login_url="login")
def notifications_view(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT n.id, n.message, n.is_read, n.created_at,
                   n.problem_id,
                   u.first_name, u.email
            FROM notifications n
            LEFT JOIN auth_user u ON n.actor_id = u.id
            WHERE n.user_id = %s
            ORDER BY n.id DESC
            """,
            [request.user.id],
        )
        rows = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0",
            [request.user.id],
        )
        unread_count = cursor.fetchone()[0]

    notifications = [
        {
            "id": r[0],
            "message": r[1],
            "is_read": r[2],
            "created_at": r[3],
            "problem_id": r[4],
            "actor_name": r[5],
            "actor_email": r[6],
        }
        for r in rows
    ]

    return render(
        request,
        "notifications.html",
        {"notifications": notifications, "unread_count": unread_count},
    )


# ============================================================
# Open notification
# ============================================================
@login_required(login_url="login")
def open_notification_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT problem_id FROM notifications WHERE id=%s AND user_id=%s",
            [id, request.user.id],
        )
        row = cursor.fetchone()

        if not row:
            messages.error(request, "Notification not found or access denied.")
            return redirect("notifications")

        problem_id = row[0]

        cursor.execute(
            "UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s",
            [id, request.user.id],
        )

    return redirect("problem_detail", id=problem_id)


# ============================================================
# Mark all notifications read
# ============================================================
@login_required(login_url="login")
@require_POST
def notifications_mark_all_read_view(request):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", [request.user.id])
    messages.success(request, "All notifications marked as read.")
    return redirect("notifications")


# ============================================================
# Clear notifications
# ============================================================
@login_required(login_url="login")
@require_POST
def notifications_clear_view(request):
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM notifications WHERE user_id=%s", [request.user.id])
    messages.success(request, "All notifications cleared.")
    return redirect("notifications")


# ============================================================
# Public Profile View
# ============================================================
def public_profile_view(request, user_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, first_name, email FROM auth_user WHERE id=%s",
            [user_id],
        )
        user_row = cursor.fetchone()

        if not user_row:
            messages.error(request, "User not found.")
            return redirect("browse_problems")

        profile_user = {
            "id": user_row[0],
            "name": user_row[1] or "User",
            "email": user_row[2] or "",
        }

        cursor.execute(
            """
            SELECT professional_title, phone_number, skills, address, interested_in, experience, bio
            FROM solver_profiles
            WHERE user_id=%s
            LIMIT 1
            """,
            [user_id],
        )
        sp = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) FROM user_reports WHERE reported_user_id=%s AND status='Open'",
            [user_id],
        )
        open_reports_count = cursor.fetchone()[0]

        already_reported = False
        my_open_report_id = None
        can_report = False

        if request.user.is_authenticated and request.user.id != user_id:
            cursor.execute(
                """
                SELECT id
                FROM user_reports
                WHERE reported_user_id=%s AND reporter_user_id=%s AND status='Open'
                LIMIT 1
                """,
                [user_id, request.user.id],
            )
            r = cursor.fetchone()
            if r:
                already_reported = True
                my_open_report_id = r[0]
                can_report = False
            else:
                already_reported = False
                my_open_report_id = None
                can_report = True

    solver_details = None
    if sp:
        solver_details = {
            "professional_title": sp[0] or "",
            "phone_number": sp[1] or "",
            "skills": sp[2] or "",
            "address": sp[3] or "",
            "interested_in": sp[4] or "",
            "experience": sp[5] or "",
            "bio": sp[6] or "",
        }

    return render(
        request,
        "public_profile.html",
        {
            "profile_user": profile_user,
            "solver_details": solver_details,
            "is_solver": solver_details is not None,
            "open_reports_count": open_reports_count,
            "can_report": can_report,
            "already_reported": already_reported,
            "my_open_report_id": my_open_report_id,
        },
    )

# ============================================================
# Become Solver
# ============================================================
@login_required(login_url="login")
def become_solver_view(request):
    if is_solver_user(request.user.id):
        messages.info(request, "You are already registered as a Solver.")
        return redirect("dashboard")

    if request.method == "POST":
        title = request.POST.get("professional_title", "").strip()
        phone = request.POST.get("phone_number", "").strip()
        skills = request.POST.get("skills", "").strip()
        address = request.POST.get("address", "").strip()
        interested_in = request.POST.get("interested_in", "").strip()
        experience = request.POST.get("experience", "").strip()
        bio = request.POST.get("bio", "").strip()

        if not all([title, phone, skills, address]):
            messages.error(request, "Title, Phone, Skills, and Address are required to become a Solver.")
            return redirect("become_solver")

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO solver_profiles
                        (user_id, professional_title, phone_number, skills, address, interested_in, experience, bio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        request.user.id,
                        title,
                        phone,
                        skills,
                        address,
                        interested_in or None,
                        experience or None,
                        bio or None,
                    ],
                )
            messages.success(request, "Congratulations! You are now a Problem Solver.")
            return redirect("dashboard")
        except Exception as e:
            messages.error(request, f"Failed to become solver: {str(e)}")
            return redirect("become_solver")

    return render(request, "become_solver.html")
#======================================================
#contract_confirm_payment_view
#====================================================
@login_required(login_url="login")
@require_POST
def contract_confirm_payment_view(request, contract_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, problem_id, owner_id, solver_id, status, payment_status
            FROM contracts
            WHERE id=%s
            """,
            [contract_id],
        )
        c = cursor.fetchone()

    if not c:
        messages.error(request, "Contract not found.")
        return redirect("dashboard")

    _cid, problem_id, owner_id, solver_id, status_now, payment_status = c

    if request.user.id != solver_id:
        messages.error(request, "Only the solver can confirm payment.")
        return redirect("contract_detail", contract_id=contract_id)

    if status_now != "Completed":
        messages.error(request, "Payment can be confirmed only after completion.")
        return redirect("contract_detail", contract_id=contract_id)

    if payment_status == "Done":
        messages.info(request, "Payment is already confirmed.")
        return redirect("contract_detail", contract_id=contract_id)

    if payment_status != "AwaitingConfirmation":
        messages.error(request, "Payment is not marked as sent by the owner yet.")
        return redirect("contract_detail", contract_id=contract_id)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE contracts
                    SET payment_status='Done'
                    WHERE id=%s AND solver_id=%s
                    """,
                    [contract_id, request.user.id],
                )

                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, actor_id, problem_id, bid_id, message)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        owner_id,
                        request.user.id,
                        problem_id,
                        None,
                        "Solver confirmed payment receipt. Payment status is now Done.",
                    ],
                )

        messages.success(request, "Payment confirmed successfully.")
    except Exception as e:
        messages.error(request, f"Confirmation failed: {str(e)}")

    return redirect("contract_detail", contract_id=contract_id)
#==========================================================================
#withdrow view
#====================================================
@login_required(login_url="login")
@require_POST
def withdraw_report_view(request, report_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_reports
                SET status='Withdrawn'
                WHERE id=%s AND reporter_user_id=%s AND status='Open'
                """,
                [report_id, request.user.id],
            )
            updated = cursor.rowcount

        if updated == 0:
            messages.error(request, "Report not found or already closed.")
            return redirect("dashboard")

        messages.success(request, "Report withdrawn successfully.")
        return redirect("dashboard")
    except Exception as e:
        messages.error(request, f"Withdraw failed: {str(e)}")
        return redirect("dashboard")