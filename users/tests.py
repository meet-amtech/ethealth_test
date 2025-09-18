Sure, here's the contents for the file: /users/users/tests.py

from django.test import TestCase
from django.urls import reverse
from .models import User, Clinic, ClinicUser

class UserProfileAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='1234567890', password='testpassword')
        self.clinic = Clinic.objects.create(name='Test Clinic', phone_number='1234567890', address={})
        self.clinic_user = ClinicUser.objects.create(user=self.user, clinic=self.clinic, role='staff')

    def test_list_user_profiles(self):
        response = self.client.get(reverse('user-profile-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.phone_number)

    def test_update_user_profile(self):
        response = self.client.patch(reverse('user-profile-detail', kwargs={'pk': self.user.pk}), 
                                     {'phone_number': '0987654321'}, 
                                     content_type='application/json')
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.phone_number, '0987654321')