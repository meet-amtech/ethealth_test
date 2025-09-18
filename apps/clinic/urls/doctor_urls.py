from django.urls import path
from ..views.doctor_views import DoctorAvailabilityView, DoctorAvailabilityUpdateView

app_name = 'doctor_availability'

urlpatterns = [
    path('schedule/', DoctorAvailabilityView.as_view(), name='doctor_schedule'),
    path('schedule/update/<uuid:pk>/', DoctorAvailabilityUpdateView.as_view(), name='update_doctor_schedule'),
]
