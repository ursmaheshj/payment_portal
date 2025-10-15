from django.contrib import admin
from .models import Category, Service, Payment
from django.contrib.auth.models import User

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('amount_paid', 'payment_date', 'status')

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'due_amount', 'due_date', 'get_total_paid', 'get_remaining', 'get_status')
    list_filter = ('category', 'user')
    inlines = [PaymentInline]

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'category', 'amount_paid', 'payment_date', 'status')
    list_filter = ('status', 'category', 'service')
    search_fields = ('user__username', 'service__description')
    readonly_fields = ('status',)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

admin.site.register(Category, CategoryAdmin)
admin.site.register(Service, ServiceAdmin)
admin.site.register(Payment, PaymentAdmin)
