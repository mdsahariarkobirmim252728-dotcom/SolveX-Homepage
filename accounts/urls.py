from django.urls import path
from . import views

urlpatterns = [
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-new-password/', views.reset_new_password_view, name='reset_new_password'),
    path('', views.home_view, name='home'),
    path('browse/', views.browse_problems_view, name='browse_problems'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('post-problem/', views.post_problem_view, name='post_problem'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),

    path('problem/edit/<int:id>/', views.edit_problem_view, name='edit_problem'),
    path('problem/delete/<int:id>/', views.delete_problem_view, name='delete_problem'),
    path('problem/solve/<int:id>/', views.mark_solved_view, name='mark_solved'),
    # বিস্তারিত দেখার লিংক
    path('problem/<int:id>/', views.problem_detail_view, name='problem_detail'),

    # বিড সাবমিট করার লিংক (নতুন)
    path('problem/<int:problem_id>/bid/', views.submit_bid_view, name='submit_bid')
    
]
