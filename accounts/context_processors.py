# accounts/context_processors.py

from django.db import connection

def unread_notifications(request):
    if request.user.is_authenticated:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0",
                [request.user.id],
            )
            count = cursor.fetchone()[0]
        return {"unread_notifications_count": count}
    return {"unread_notifications_count": 0}
