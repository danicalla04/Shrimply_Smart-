from django.core.management.base import BaseCommand
import os
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Test Firebase Realtime DB write using FIREBASE_CREDENTIAL_PATH and FIREBASE_DB_URL'

    def handle(self, *args, **options):
        try:
            import firebase_admin
            from firebase_admin import credentials, db as firebase_db
        except Exception as e:
            self.stderr.write('firebase-admin is not installed. Run: pip install firebase-admin')
            return

        cred_path = os.getenv('FIREBASE_CREDENTIAL_PATH')
        db_url = os.getenv('FIREBASE_DB_URL')

        if not cred_path or not db_url:
            self.stderr.write('FIREBASE_CREDENTIAL_PATH and FIREBASE_DB_URL must be set in the environment or .env')
            return

        if not os.path.exists(cred_path):
            self.stderr.write(f'Credentials file not found: {cred_path}')
            return

        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {'databaseURL': db_url})
        except Exception as e:
            self.stderr.write(f'Failed to initialize firebase-admin: {e}')
            return

        try:
            ref_latest = firebase_db.reference('/sensors/latest')
            ref_readings = firebase_db.reference('/sensors/readings')

            payload = {
                'device_id': 'test-runner',
                'temperature': 25.5,
                'ph': 7.4,
                'oxygen': 7.8,
                'tds': 320,
                'test_at': datetime.utcnow().isoformat() + 'Z'
            }

            # Set latest and push historical reading
            ref_latest.set(payload)
            pushed = ref_readings.push(payload)

            self.stdout.write(self.style.SUCCESS('Firebase write successful'))
            self.stdout.write(f'Pushed key: {pushed.key}')
        except Exception as e:
            self.stderr.write(f'Firebase write failed: {e}')
            return
