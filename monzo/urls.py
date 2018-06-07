from django.urls import path

from . import views

app_name = 'monzo'


urlpatterns = [
    path('login/', views.login, name='login'),
    path('login-inbound/', views.login_callback, name='login_callback'),
    path('my-accounts/', views.my_accounts, name='my_accounts'),
    path('my-transactions/<str:account_id>/', views.my_transactions, name='my_transactions'),
    path('', views.home, name='home'),
]

