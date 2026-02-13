from django.shortcuts import render

def home_view(request):
    return render(request, 'index.html')

def login_view(request):
    return render(request, 'login.html')

def register_view(request):
    return render(request, 'register.html')

def browse_problems_view(request):
    return render(request, 'browse.html')