import datetime
import logging

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from apps.appointment.models import AppointmentRequest
from apps.clinic.models import Clinic




logger = logging.getLogger(__name__)


class AppointmentRequestSerializer(serializers.ModelSerializer):
    request_token = serializers.IntegerField(required=False)

    class Meta:
        model = AppointmentRequest
        fields = ['id', 'name', 'phone', 'age', 'gender', 'clinic', 'request_token', 'appointment_request_status', 'source', 'confirmed_at', 'expired_at']
        read_only_fields = ['request_token', 'clinic']

    def create(self, validated_data):
        clinic_id = validated_data.pop('clinic_id', None)
        validated_data['clinic'] = get_object_or_404(Clinic,id=clinic_id,is_deleted=False,is_active=True,is_accepting_requests=True)

        appointment_request = self.Meta.model.objects.filter(clinic=clinic_id).order_by('-created_at').first()

        request_token = 1
        if appointment_request:
            try:
                request_token = appointment_request.generate_next_request_token()
            except Exception as e:
                logger.error(f"Error generating request token: {e}")
                raise serializers.ValidationError(f"Error generating request token: {e}")
        validated_data['request_token'] = request_token
        appointment_request = super().create(validated_data)
        if request_token == 1 and appointment_request.clinic:
            appointment_request.clinic.reset_token = False
            appointment_request.clinic.save()

        return appointment_request
