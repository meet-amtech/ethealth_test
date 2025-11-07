from django.urls import path

from apps.appointment.views.template_views import (
    # AppointmentRequestListView,
    # AppointmentRequestCreateView,
    # AppointmentRequestDeleteView,
    AppointmentListView,
    AppointmentCreateView,
    AppointmentUpdateView,
    AppointmentDeleteView
)

app_name = "template_appointment"

urlpatterns = [
    # Appointment Request URLs
    # path('requests/', AppointmentRequestListView.as_view(), name='appointment_request_list'),
    # path('requests/create/', AppointmentRequestCreateView.as_view(), name='appointment_request_create'),
    # path('requests/<uuid:pk>/delete/', AppointmentRequestDeleteView.as_view(), name='appointment_request_delete'),
    
    # Appointment URLs
    path('', AppointmentListView.as_view(), name='appointment_list'),
    path('create/', AppointmentCreateView.as_view(), name='appointment_create'),
    path('<uuid:pk>/update/', AppointmentUpdateView.as_view(), name='appointment_update'),
    path('<uuid:pk>/delete/', AppointmentDeleteView.as_view(), name='appointment_delete'),
]
