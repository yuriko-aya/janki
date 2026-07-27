from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('forgot-password/done/', views.ForgotPasswordDoneView.as_view(), name='forgot_password_done'),
    path('reset-password/<str:token>/', views.ResetPasswordView.as_view(), name='reset_password'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('verify-email/<str:token>/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('registration-pending/', views.RegistrationPendingView.as_view(), name='registration_pending'),
    path('contact/', views.ContactView.as_view(), name='contact'),
]