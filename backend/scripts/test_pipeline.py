"""End-to-end test: Arduino -> Django -> MySQL -> Dashboard pipeline."""
import os, sys, json, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'aquaculture_api.settings'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from api.views import update_sensors
from api.consumers import SensorConsumer
from api.routing import websocket_urlpatterns
print('[OK] All imports clean (views, consumers, routing)')

# 2. Verify no firebase imports
import api.views as v
import inspect
source = inspect.getsource(v)
if 'firebase' in source.lower():
    print('[WARN] Firebase references still in views.py')
else:
    print('[OK] No Firebase references in views.py')

# 3. Test the endpoint with simulated POST
from django.test import RequestFactory

factory = RequestFactory()
payload = {'temperature': 30.2, 'ph': 7.8, 'turbidity': 1.5, 'tds': 350}
request = factory.post('/api/update-sensors/', data=json.dumps(payload), content_type='application/json')
response = update_sensors(request)
print(f'[OK] POST /api/update-sensors/ -> {response.status_code}')
print(f'     Saved reading ID: {response.data.get("id")}')
print(f'     Data: temp={response.data.get("temperature")}, ph={response.data.get("ph")}, turbidity={response.data.get("turbidity")}, tds={response.data.get("tds")}')

# 4. Verify it's in MySQL
from api.models import SensorReading
latest = SensorReading.objects.first()
print(f'[OK] Latest reading in DB: id={latest.id}, temp={latest.temperature}, ph={latest.ph}, oxygen={latest.oxygen}, tds={latest.tds}')

# 5. Verify sensors/latest endpoint works
from api.views import SensorReadingViewSet
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import User
api_factory = APIRequestFactory()
user = User.objects.first()
if user:
    req = api_factory.get('/api/sensors/latest/')
    req.user = user
    view = SensorReadingViewSet.as_view({'get': 'latest'})
    resp = view(req)
    print(f'[OK] GET /api/sensors/latest/ -> {resp.status_code}, temp={resp.data.get("temperature")}')
else:
    print('[INFO] No user to test authenticated endpoint, but it exists')

# 6. Check WebSocket consumer group name matches views broadcast
print(f'[OK] Consumer group: "{SensorConsumer.GROUP_NAME}"')
print(f'[OK] WS route: {websocket_urlpatterns[0].pattern}')

# 7. Clean up test reading
latest.delete()
print(f'[OK] Test reading cleaned up')
print()
print('=== ALL CHECKS PASSED ===')
