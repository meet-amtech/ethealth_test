import logging
import datetime

from cryptography.fernet import Fernet

from ethealth.settings import FERNET_SECRET_KEY

logger = logging.getLogger('root')

def get_date_difference_in_day(st_date,ed_date):
    day_count = (ed_date-st_date).days
    return f"{day_count} days" if day_count > 1 else f"{day_count} day"


def get_today_date_obj():
    """
    Get today's date as a date object.
    """
    return datetime.datetime.today()


def get_now_time_obj():
    """
    Get the current time as a time object.
    """
    return datetime.datetime.now().time()


def get_date_str(date_obj):
    """
    Convert a date object to a date string in the format DD-MM-YYYY.
    """
    return date_obj.strftime("%d/%m/%Y") if date_obj else None


def get_date_obj(date_str):
    """
    Convert a date string in the format DD-MM-YYYY to a date object.
    """
    return datetime.datetime.strptime(date_str, "%d/%m/%Y").date() if date_str else None


def get_time_str(time_obj, format="%I:%M %p"):
    """
    Convert a time object to a time string in the formate HH:MM AM/PM.
    """
    return time_obj.strftime(format) if time_obj else None


def get_time_obj(time_str, format="%I:%M %p"):
    """
    Convert a time string in the formate HH:MM AM/PM to a time object.
    """
    return datetime.datetime.strptime(time_str, format).time() if time_str else None


def add_minutes_to_time(time_obj, minutes=0):
    """
    Add minutes to a time object.
    """
    if not time_obj:
        return None
    return (datetime.datetime.combine(datetime.datetime.today(), time_obj) + datetime.timedelta(minutes=minutes)).time()


class EncryptionDecryption:
    def __init__(self, data):
        self.data = data
        logger.info(f"To encrypt the file we are using {FERNET_SECRET_KEY} as key.")

    def encryption(self):
        logger.info(f"Try to encrypt {self.data}")
        f = Fernet(FERNET_SECRET_KEY)
        enc_data = f.encrypt(str(self.data).encode("utf-8"))
        return enc_data.decode("utf-8")

    def decrypt(self):
        logger.info(f"try to decrypt the {self.data}")
        f = Fernet(FERNET_SECRET_KEY)
        dec_data = f.decrypt(self.data)
        return dec_data.decode("utf-8")


# def set_request_session_values(request, clinic_id=None):
#     if not clinic_id:
#         clinic_id = request.session.get('clinic_id')

#     from apps.clinic.models import ClinicUser
#     clinic_user = ClinicUser.objects.filter(clinic_id=clinic_id, user=request.user).first()
#     assert clinic_user, "Please pass valid clinic_id."

#     user_id = clinic_user.user.id
#     user_active_clinics = {}
#     user_clinics = ClinicUser.get_active_clinic_users(user_id=user_id)
#     for user_clinic in user_clinics:
#         user_active_clinics[str(user_clinic.clinic_id)] = {
#             'clinic_logo_url': user_clinic.clinic.light_logo.url,
#             'clinic_name': user_clinic.clinic.name
#         }

#     # Set clinic and clinic user details in session
#     request.session['clinic_id'] = str(clinic_user.clinic.id)
#     request.session['clinic_user_id'] = str(clinic_user.id)
#     request.session['clinic_user_role'] = str(clinic_user.role)
#     request.session['clinic_logo_url'] = str(clinic_user.clinic.light_logo.url)
#     request.session['clinic_favicon_url'] = str(clinic_user.clinic.favicon.url)
#     request.session['clinic_name'] = str(clinic_user.clinic.name)
#     request.session['is_clinic_admin'] = clinic_user.is_admin
#     request.session['user_active_clinics'] = user_active_clinics

#     # Serialize ClinicUserRole into session
#     from apps.clinic.models import ClinicUserRole
#     request.session['clinic_user_roles'] = {
#         'DOCTOR': ClinicUserRole.DOCTOR,
#         'STAFF': ClinicUserRole.STAFF,
#         'VISITING_DOCTOR': ClinicUserRole.VISITING_DOCTOR,
#     }
