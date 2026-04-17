# accounts/models.py
from django.contrib.auth.models import User
from django.db import connection

# This will add a custom property to the default User model
def get_is_solver(self):
    with connection.cursor() as cursor:
        cursor.execute("SELECT is_solver FROM auth_user WHERE id = %s", [self.id])
        result = cursor.fetchone()
        return result[0] == 1 if result else False

User.add_to_class("is_solver", property(get_is_solver))
