from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Category, Service, Payment
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Q, Count
from datetime import date, datetime
from django.contrib.auth.decorators import login_required
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.urls import reverse

def home(request):
    return render(request, 'core/home.html')

def custom_login_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please login to access this page.')
            return redirect(f"{reverse('login')}?next={request.path}")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@custom_login_required
def dashboard(request):
    categories = Category.objects.all()
    years = sorted(Service.objects.filter(user=request.user).values_list('year', flat=True).distinct(), reverse=True)
    current_year = datetime.now().year
    selected_year = request.GET.get('year')
    selected_category_id = request.GET.get('category')
    services = Service.objects.filter(user=request.user)
    if selected_year and selected_year != '':
        services = services.filter(year=selected_year)
    if selected_category_id and selected_category_id != '':
        services = services.filter(category_id=selected_category_id)
    service_status = []
    for service in services:
        payments = Payment.objects.filter(service=service)
        total_paid = payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        remaining = max(service.due_amount - total_paid, 0)
        service_status.append({
            'service': service,
            'category': service.category,
            'due_amount': service.due_amount,
            'due_date': service.due_date,
            'year': service.year,
            'total_paid': total_paid,
            'remaining': remaining,
            'status': service.status,  # Use Service.status
            'payments': payments,
        })
    status_list = [
        {'key': 'pending', 'label': 'Pending', 'color': 'danger'},
        {'key': 'partial', 'label': 'Partial', 'color': 'warning text-dark'},
        {'key': 'full', 'label': 'Done', 'color': 'success'},
    ]
    return render(request, 'core/dashboard.html', {
        'categories': categories,
        'years': years,
        'selected_category_id': selected_category_id,
        'selected_year': selected_year,
        'service_status': service_status,
        'status_list': status_list,
    })

@custom_login_required
def make_payment(request):
    services = Service.objects.filter(user=request.user).exclude(status='full')
    selected_service_id = request.GET.get('service')
    selected_service = None
    if selected_service_id:
        selected_service = get_object_or_404(Service, id=selected_service_id, user=request.user)
        services = services.filter(id=selected_service_id)
    if request.method == 'POST':
        service_id = request.POST.get('service')
        amount = request.POST.get('amount')
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            messages.error(request, 'Please enter a valid payment amount.')
            return redirect(f'/make_payment/?service={service_id}')
        service = get_object_or_404(Service, id=service_id, user=request.user)
        total_paid = service.get_total_paid()
        remaining = max(service.due_amount - total_paid, 0)
        # Prevent payment for fully paid service
        if service.status == 'full':
            messages.warning(request, 'This service is already fully paid. No further payments allowed.')
            return redirect('dashboard')
        # Prevent negative or zero payments
        if amount <= 0:
            messages.error(request, 'Payment amount must be positive.')
            return redirect(f'/make_payment/?service={service.id}')
        # Prevent overpayment
        if amount > remaining:
            messages.error(request, f'Payment amount cannot exceed remaining due ({remaining}).')
            return redirect(f'/make_payment/?service={service.id}')
        # Prevent duplicate payments in quick succession (optional)
        from django.utils import timezone
        last_payment = Payment.objects.filter(service=service, user=request.user).order_by('-payment_date').first()
        if last_payment and (last_payment.amount_paid == amount and (timezone.now() - last_payment.payment_date).seconds < 10):
            messages.warning(request, 'Duplicate payment detected. Please wait before retrying.')
            return redirect('dashboard')
        payment = Payment.objects.create(
            user=request.user,
            service=service,
            category=service.category,
            amount_paid=amount,
        )
        messages.success(request, f'Payment of {amount} recorded!')
        return redirect('dashboard')
    return render(request, 'core/make_payment.html', {'services': services, 'selected_service': selected_service})

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # Analytics summary
    categories = Category.objects.all()
    analytics = []
    summary = {
        'total_users_with_pending': 0,
        'total_pending_payments': 0,
        'total_collected': 0,
        'total_remaining': 0,
        'category_stats': [],
    }
    users_with_pending = set()
    for category in categories:
        services = Service.objects.filter(category=category)
        cat_collected = 0
        cat_remaining = 0
        cat_pending_count = 0
        cat_users_with_pending = set()
        for service in services:
            payments = Payment.objects.filter(service=service)
            total_paid = payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
            remaining = max(service.due_amount - total_paid, 0)
            cat_collected += total_paid
            cat_remaining += remaining
            if remaining > 0:
                cat_pending_count += 1
                cat_users_with_pending.add(service.user.id)
                users_with_pending.add(service.user.id)
            analytics.append({
                'user': service.user,
                'category': category,
                'service': service,
                'due_amount': service.due_amount,
                'total_paid': total_paid,
                'remaining': remaining,
                'status': service.get_status(),
            })
        summary['category_stats'].append({
            'category': category,
            'pending_count': cat_pending_count,
            'collected': cat_collected,
            'remaining': cat_remaining,
            'users_with_pending': len(cat_users_with_pending),
        })
        summary['total_collected'] += cat_collected
        summary['total_remaining'] += cat_remaining
        summary['total_pending_payments'] += cat_pending_count
    summary['total_users_with_pending'] = len(users_with_pending)
    return render(request, 'core/admin_dashboard.html', {'analytics': analytics, 'summary': summary})

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return redirect('register')
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'core/register.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
            return redirect('login')
    return render(request, 'core/login.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('home')

def update_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        user.username = request.POST.get('username', user.username)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'User details updated.')
        return redirect('admin_dashboard')
    return render(request, 'core/update_user.html', {'user': user})
