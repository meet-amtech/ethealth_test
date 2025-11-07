from django.urls import path

from apps.appointment.views.template_views import AppointmentListView, AppointmentUpdateView, AppointmentDeleteView, AppointmentCreateView

app_name = "template_appointment"

urlpatterns = [
    path("", AppointmentListView.as_view(), name="appointments_list"),
    path('<uuid:pk>/update/', AppointmentUpdateView.as_view(), name='appointment_update'),
    path('<uuid:pk>/delete/', AppointmentDeleteView.as_view(), name='appointment_delete'),
    path('create/', AppointmentCreateView.as_view(), name='appointment_create'),
]
