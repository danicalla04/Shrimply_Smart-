import os
import sys
import firebase_admin
from firebase_admin import credentials, db

cred_path = os.environ.get('FIREBASE_CREDENTIAL_PATH') or r'C:\wamp64\www\Shrimply_Smart\shrimplysmart-firebase-adminsdk-fbsvc-53c8e6c60c.json'
db_url = os.environ.get('FIREBASE_DB_URL') or 'https://shrimplysmart-default-rtdb.firebaseio.com'

if not os.path.exists(cred_path):
    print('Credential file not found at:', cred_path)
    sys.exit(2)

cred = credentials.Certificate(cred_path)
try:
    firebase_admin.initialize_app(cred, {'databaseURL': db_url})
except Exception as e:
    # allow re-init when module already initialized in the same process
    print('initialize_app error (may be ok):', e)

try:
    ref = db.reference('/sensors/latest')
    val = ref.get()
    print('Value at /sensors/latest:')
    print(val)
except Exception as e:
    print('Error reading /sensors/latest:', e)
    sys.exit(3)
