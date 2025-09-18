from django.urls import path

from apps.users.views.template_views import LoginView, OTPView, OTPVerifyView, LogoutView, UserProfileView, UserProfileUpdateView

app_name = "template_user"

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('otp/', OTPView.as_view(), name='otp'),
    path('otp/verify/', OTPVerifyView.as_view(), name='otp_verify'),
    path('logout/', LogoutView.as_view(), name='logout'),
]





urlpatterns += [
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='user_profile_update'),
]

