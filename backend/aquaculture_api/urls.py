"""
URL configuration for aquaculture_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.http import JsonResponse
from api import views
from api.views import RegisterView

def api_root(request):
    """API root view showing available endpoints"""
    return JsonResponse({
        "message": "Smart Shrimp Pond API",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin/",
            "api": {
                "auth": {
                    "token": "/api/auth/token/",
                    "refresh": "/api/auth/token/refresh/"
                },
                "sensors": "/api/sensors/",
                "thresholds": "/api/thresholds/",
                "alerts": "/api/alerts/",
                "weather": "/api/weather/?city=CityName",
                "weather_complete": "/api/weather/complete/?city=CityName"
            }
        },
        "docs": "See README.md for detailed API documentation"
    })

urlpatterns = [
    path('', api_root, name='api_root'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/weather/complete/', views.weather_complete, name='weather_complete_direct'),
]
