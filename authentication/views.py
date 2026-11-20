from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import UserRegistrationForm

# Create your views here.

# Signup view
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        reg_form = UserRegistrationForm(request.POST)

        if reg_form.is_valid():
            # Create user account and activate immediately without email verification
            user = reg_form.save(commit=False)
            user.is_active = True
            user.save()

            # Automatically log the newly registered user in
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Welcome to PreLoved, {user.username}! Your account has been created successfully.")

            next_url = request.GET.get('next') or request.POST.get('next') or 'home'
            if not url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                next_url = 'home'
            return redirect(next_url)
    else:
        reg_form = UserRegistrationForm()

    context = {
        'reg_form': reg_form,
    }
    return render(request, 'authentication/signup.html', context)

# Login view
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            redirect_url = request.GET.get('next', 'home')
            if not url_has_allowed_host_and_scheme(url=redirect_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                redirect_url = 'home'
            return redirect(redirect_url)
        else:
            messages.error(request, "Oops! Username or Password is invalid. Please try again.")

    reg_form = UserRegistrationForm()
    return render(request, 'authentication/login.html', {'reg_form': reg_form})

# Logout view
def logout_view(request):
    logout(request)
    return redirect('login')
