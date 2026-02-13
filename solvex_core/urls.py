from django.contrib import admin
from django.urls import path, include # include যোগ করুন

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')), # এই লাইনটি যোগ করুন
]