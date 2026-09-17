from django.contrib.auth import get_user_model
User = get_user_model()
username = 'admin'
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, 'admin@example.com', 'admin123')
    print('created admin/admin123')
else:
    print('admin already exists')
