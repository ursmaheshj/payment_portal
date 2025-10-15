from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.exceptions import ValidationError
from datetime import datetime

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    def __str__(self):
        return self.name

class Service(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    year = models.PositiveIntegerField()  # New field for year
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('partial', 'Partial'), ('full', 'Full')], default='pending')
    
    def clean(self):
        current_year = datetime.now().year
        if self.year < 1900 or self.year > current_year + 1:
            raise ValidationError({'year': 'Year must be between 1900 and next year.'})
    
    def __str__(self):
        return f"{self.category.name} for {self.user.username} ({self.year}) (Due: {self.due_amount})"

    def get_total_paid(self):
        return Payment.objects.filter(service=self).aggregate(models.Sum('amount_paid'))['amount_paid__sum'] or 0

    def get_remaining(self):
        return max(self.due_amount - self.get_total_paid(), 0)

    def get_status(self):
        if self.get_remaining() == 0:
            return 'Full'
        elif self.get_total_paid() > 0:
            return 'Partial'
        else:
            return 'Pending'
    
    def update_status(self):
        total_paid = self.get_total_paid()
        if total_paid == 0:
            self.status = 'pending'
        elif total_paid < self.due_amount:
            self.status = 'partial'
        else:
            self.status = 'full'
        self.save(update_fields=['status'])

class Payment(models.Model):
    STATUS_CHOICES = [
        ('partial', 'Partial'),
        ('full', 'Full'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    def __str__(self):
        return f"{self.user.username} paid {self.amount_paid} for {self.category.name} ({self.status})"

    def save(self, *args, **kwargs):
        # Payment status: 'full' only if paid full amount in one go, else 'partial'
        if Decimal(str(self.amount_paid)) >= self.service.due_amount:
            self.status = 'full'
        else:
            self.status = 'partial'
        super().save(*args, **kwargs)
        # Update service status after saving payment
        self.service.update_status()
