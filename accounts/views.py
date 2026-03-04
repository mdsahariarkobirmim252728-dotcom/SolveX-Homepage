from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import connection


# ---------------------------
# Home
# ---------------------------
def home_view(request):
    return render(request, "index.html")


# ---------------------------
# Browse Problems (MySQL table: problems)
# ---------------------------
def browse_problems_view(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, title, description, budget
            FROM problems
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()

    problems = []
    for r in rows:
        problems.append({
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "budget": r[3],
        })

    return render(request, "browse.html", {"problems": problems})


# ---------------------------
# Register
# ---------------------------
def register_view(request):
    if request.method == "POST":
        fullname = request.POST.get("fullname", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not fullname or not email or not password or not confirm_password:
            messages.error(request, "All fields are required.")
            return redirect("register")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        # আমরা username হিসেবে email ব্যবহার করছি
        if User.objects.filter(username=email).exists():
            messages.error(request, "This email is already registered.")
            return redirect("register")

        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = fullname
        user.save()

        messages.success(request, "Account created successfully! Please login.")
        return redirect("login")

    return render(request, "register.html")


# ---------------------------
# Login
# ---------------------------
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


# ---------------------------
# Logout
# ---------------------------
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("home")


@login_required(login_url="login")
def dashboard_view(request):
    with connection.cursor() as cursor:
        # লক্ষ্য করুন: is_solved যোগ করা হয়েছে
        cursor.execute("""
            SELECT id, title, description, budget, is_solved 
            FROM problems 
            WHERE user_id = %s 
            ORDER BY id DESC
        """, [request.user.id])
        rows = cursor.fetchall()

    my_problems = []
    for r in rows:
        my_problems.append({
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "budget": r[3],
            "is_solved": r[4], # 0 or 1
        })

    return render(request, "dashboard.html", {"my_problems": my_problems})
# ---------------------------
# Post a new problem (login required)
# MySQL table: problems
# ---------------------------
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
            budget_val = float(budget)
        except:
            messages.error(request, "Budget must be a number.")
            return redirect("post_problem")

        # এখানে ডাটাবেসে তথ্য পাঠানো হচ্ছে
        with connection.cursor() as cursor:
            # লক্ষ্য করুন: আমরা user_id কলামেও ডাটা দিচ্ছি
            cursor.execute(
                """
                INSERT INTO problems (title, description, budget, user_id) 
                VALUES (%s, %s, %s, %s)
                """,
                [title, description, budget_val, request.user.id] # request.user.id মানে বর্তমান ইউজারের আইডি
            )

        messages.success(request, "Problem posted successfully!")
        return redirect("browse_problems") # অথবা চাইলে dashboard এ রিডাইরেক্ট করতে পারেন

    return render(request, "post_problem.html")

# ---------------------------
# Profile (view + edit) (login required)
# ---------------------------
# ---------------------------
# Profile (Only Name Edit)
# ---------------------------
@login_required(login_url="login")
def profile_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()

        if not full_name:
            messages.error(request, "Name is required.")
            return redirect("profile")

        # আমরা এখানে ইমেইল আপডেট করছি না, কারণ সেটা Settings এ আছে
        request.user.first_name = full_name
        request.user.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("profile")

    return render(request, "profile.html")


# ---------------------------
# Settings (placeholder) (login required)
# ---------------------------
@login_required(login_url="login")
def settings_view(request):
    return render(request, "settings.html")
# ---------------------------
# Simple Forgot Password (Step 1: Check Email)
# ---------------------------
def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        
        # Check if user exists
        try:
            user = User.objects.get(username=email) # যেহেতু username = email
            # ইমেইল পাওয়া গেলে সেশনে ইউজার আইডি সেভ রাখি
            request.session['reset_user_id'] = user.id
            messages.success(request, "Email found! Please set a new password.")
            return redirect("reset_new_password")
        except User.DoesNotExist:
            messages.error(request, "This email is not registered.")
            return redirect("forgot_password")

    return render(request, "forgot_password.html")


# ---------------------------
# Simple Forgot Password (Step 2: Set New Password)
# ---------------------------
def reset_new_password_view(request):
    # চেক করি কেউ আগের স্টেপ (ইমেইল ভেরিফিকেশন) পার করে এসেছে কিনা
    user_id = request.session.get('reset_user_id')
    
    if not user_id:
        messages.error(request, "Please enter your email first.")
        return redirect("forgot_password")

    if request.method == "POST":
        new_password = request.POST.get("new_password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        # ১. পাসওয়ার্ড ফাঁকা কিনা চেক
        if not new_password or not confirm_password:
            messages.error(request, "Password fields cannot be empty.")
            return redirect("reset_new_password")

        # ✅ ২. এই লাইনটি নতুন যোগ করা হয়েছে (৬ অক্ষরের কম হলে এরর দিবে)
        if len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return redirect("reset_new_password")

        # ৩. দুই পাসওয়ার্ড মিলছে কিনা চেক
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("reset_new_password")

        # সব ঠিক থাকলে পাসওয়ার্ড আপডেট হবে
        try:
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()

            # সেশন ক্লিয়ার করা (সিকিউরিটির জন্য)
            del request.session['reset_user_id']

            messages.success(request, "Password reset successfully! Please login.")
            return redirect("login")
            
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("forgot_password")

    return render(request, "reset_new_password.html")
from django.contrib.auth import update_session_auth_hash # পাসওয়ার্ড চেঞ্জ হলে লগআউট যেন না হয়

from django.contrib.auth import update_session_auth_hash 

# ---------------------------
# All-in-One Settings View
# ---------------------------
@login_required(login_url="login")
def settings_view(request):
    if request.method == "POST":
        # ফর্ম থেকে hidden input ভ্যালু চেক করা হচ্ছে
        form_type = request.POST.get("form_type")

        # === ১. যদি ইমেইল চেঞ্জ করতে চায় ===
        if form_type == "change_email":
            new_email = request.POST.get("email", "").strip().lower()
            password = request.POST.get("password_for_email", "")

            # পাসওয়ার্ড চেক (সিকিউরিটি)
            if not request.user.check_password(password):
                messages.error(request, "Incorrect password. Email not updated.")
            
            # ইমেইল ইউনিক কিনা চেক
            elif User.objects.filter(username=new_email).exclude(id=request.user.id).exists():
                messages.error(request, "This email is already in use.")
            
            else:
                # সব ঠিক থাকলে আপডেট
                request.user.username = new_email
                request.user.email = new_email
                request.user.save()
                messages.success(request, "Email updated successfully!")
            
            return redirect("settings")

        # === ২. যদি পাসওয়ার্ড চেঞ্জ করতে চায় ===
        elif form_type == "change_password":
            old_password = request.POST.get("old_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            # পুরাতন পাসওয়ার্ড চেক
            if not request.user.check_password(old_password):
                messages.error(request, "Old password was incorrect.")
            
            # নতুন পাসওয়ার্ড লেন্থ চেক
            elif len(new_password) < 6:
                messages.error(request, "New password must be at least 6 characters.")
            
            # পাসওয়ার্ড ম্যাচিং চেক
            elif new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
            
            else:
                # সব ঠিক থাকলে পাসওয়ার্ড সেভ
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user) # লগআউট আটকানো
                messages.success(request, "Password changed successfully!")

            return redirect("settings")

    return render(request, "settings.html")
# ---------------------------
# 1. Mark as Solved
# ---------------------------
@login_required(login_url="login")
def mark_solved_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE problems 
            SET is_solved = 1 
            WHERE id = %s AND user_id = %s
        """, [id, request.user.id])
    
    messages.success(request, "Problem marked as solved!")
    return redirect("dashboard")

# ---------------------------
# 2. Delete Problem
# ---------------------------
@login_required(login_url="login")
def delete_problem_view(request, id):
    with connection.cursor() as cursor:
        cursor.execute("""
            DELETE FROM problems 
            WHERE id = %s AND user_id = %s
        """, [id, request.user.id])
    
    messages.success(request, "Problem deleted successfully.")
    return redirect("dashboard")

# ---------------------------
# 3. Edit Problem
# ---------------------------
@login_required(login_url="login")
def edit_problem_view(request, id):
    # প্রথমে ডাটা নিয়ে আসি
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT title, description, budget 
            FROM problems 
            WHERE id = %s AND user_id = %s
        """, [id, request.user.id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Problem not found or access denied.")
        return redirect("dashboard")

    problem_data = {"id": id, "title": row[0], "description": row[1], "budget": row[2]}

    # ফর্ম সাবমিট হলে আপডেট করব
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        budget = request.POST.get("budget", "").strip()

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE problems 
                SET title = %s, description = %s, budget = %s 
                WHERE id = %s AND user_id = %s
            """, [title, description, budget, id, request.user.id])

        messages.success(request, "Problem updated successfully!")
        return redirect("dashboard")

    return render(request, "edit_problem.html", {"problem": problem_data})
# ---------------------------
# Problem Detail Page (Show full details + Bid Form)
# ---------------------------
def problem_detail_view(request, id):
    
    # ১. সমস্যার বিস্তারিত তথ্য আনা (JOIN করে অথরের নামসহ)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.title, p.description, p.budget, u.first_name, u.email, u.id
            FROM problems p
            JOIN auth_user u ON p.user_id = u.id
            WHERE p.id = %s
        """, [id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Problem not found.")
        return redirect("browse_problems")

    # ডাটা ডিকশনারিতে সাজানো
    problem = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "budget": row[3],
        "author_name": row[4],
        "author_email": row[5],
        "author_id": row[6],  # এটা লাগবে লজিক চেক করার জন্য
    }

    # ২. বর্তমান ইউজার কি এই পোস্টের মালিক? (লজিক চেক)
    is_owner = False
    if request.user.is_authenticated and request.user.id == problem["author_id"]:
        is_owner = True

    return render(request, "problem_detail.html", {
        "problem": problem,
        "is_owner": is_owner
    })
# ---------------------------
# Submit a Bid (Apply for a problem)
# ---------------------------
@login_required(login_url="login")
def submit_bid_view(request, problem_id):
    if request.method == "POST":
        amount = request.POST.get("amount")
        proposal = request.POST.get("proposal", "").strip()

        # ১. চেক করা: ইউজার কি নিজের পোস্টেই বিড করছে? (এটা আটকাতে হবে)
        with connection.cursor() as cursor:
            cursor.execute("SELECT user_id FROM problems WHERE id = %s", [problem_id])
            row = cursor.fetchone()
            # যদি পোস্টের মালিক আর বর্তমান ইউজার একই হয়
            if row and row[0] == request.user.id:
                messages.error(request, "You cannot bid on your own problem.")
                return redirect("problem_detail", id=problem_id)

        # ২. বিড ডাটাবেসে সেভ করা (bids টেবিলে)
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO bids (problem_id, user_id, amount, proposal_text)
                    VALUES (%s, %s, %s, %s)
                """, [problem_id, request.user.id, amount, proposal])
            
            messages.success(request, "Bid placed successfully!")
        except Exception as e:
            # যদি bids টেবিল না থাকে বা অন্য কোনো এরর হয়
            messages.error(request, f"Error placing bid: {str(e)}")
            
        return redirect("problem_detail", id=problem_id)
        
    return redirect("browse_problems")