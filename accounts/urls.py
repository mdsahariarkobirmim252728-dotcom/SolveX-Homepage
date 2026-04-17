from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("browse/", views.browse_problems_view, name="browse_problems"),

    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("reset-new-password/", views.reset_new_password_view, name="reset_new_password"),

    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("post-problem/", views.post_problem_view, name="post_problem"),
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),

    path("problem/edit/<int:id>/", views.edit_problem_view, name="edit_problem"),
    path("problem/delete/<int:id>/", views.delete_problem_view, name="delete_problem"),
    path("problem/solve/<int:id>/", views.mark_solved_view, name="mark_solved"),

    path("problem/<int:id>/", views.problem_detail_view, name="problem_detail"),
    path("problem/<int:problem_id>/bid/", views.submit_bid_view, name="submit_bid"),

    path("bid/<int:bid_id>/action/", views.bid_action_view, name="bid_action"),
    path("bid/<int:bid_id>/cancel/", views.cancel_bid_view, name="cancel_bid"),

    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/open/<int:id>/", views.open_notification_view, name="open_notification"),
    path("notifications/mark-all-read/", views.notifications_mark_all_read_view, name="notifications_mark_all_read"),
    path("notifications/clear/", views.notifications_clear_view, name="notifications_clear"),

    path("user/<int:user_id>/", views.public_profile_view, name="public_profile"),
    path("user/<int:user_id>/report/", views.report_user_view, name="report_user"),

    path("become-a-solver/", views.become_solver_view, name="become_solver"),

    # Contracts
    path("contract/<int:contract_id>/", views.contract_detail_view, name="contract_detail"),
    path("contract/problem/<int:problem_id>/", views.contract_for_problem_view, name="contract_for_problem"),
    path("contract/<int:contract_id>/submit/", views.contract_submit_work_view, name="contract_submit_work"),
    path("contract/<int:contract_id>/revision/", views.contract_request_revision_view, name="contract_request_revision"),
    path("contract/<int:contract_id>/approve/", views.contract_approve_view, name="contract_approve"),

    # Admin Reports (simple)
    path("reports/admin/", views.admin_reports_view, name="admin_reports"),
    path("reports/admin/<int:report_id>/<str:action>/", views.admin_report_action_view, name="admin_report_action"),
    path("contract/<int:contract_id>/confirm-payment/", views.contract_confirm_payment_view, name="contract_confirm_payment"),
    path("reports/withdraw/<int:report_id>/", views.withdraw_report_view, name="withdraw_report"),
]