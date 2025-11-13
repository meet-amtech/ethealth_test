from django.urls import path

from apps.appointment.views.template_views import (
    AppointmentListView,
    AppointmentCreateView,
    AppointmentUpdateView,
    AppointmentDeleteView
)

app_name = "template_appointment"

urlpatterns = [
    # Appointment URLs
    path('', AppointmentListView.as_view(), name='appointment_list'),
    path('create/', AppointmentCreateView.as_view(), name='appointment_create'),
    # This URL now handles both new appointments (from request) and updates to existing ones
    path('request/<uuid:pk>/', AppointmentUpdateView.as_view(), name='appointment_request_update'),
    path('<uuid:pk>/update/', AppointmentUpdateView.as_view(), name='appointment_update'),
    path('<uuid:pk>/delete/', AppointmentDeleteView.as_view(), name='appointment_delete'),
]
