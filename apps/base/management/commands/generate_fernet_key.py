from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generates a new Fernet key for encryption."

    def handle(self, *args, **options):
        key = Fernet.generate_key().decode('utf-8')
        self.stdout.write(f"FERNET_SECRET_KEY={key}")
        self.stdout.write(self.style.SUCCESS("Successfully generated a new Fernet key."))
