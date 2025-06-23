from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('bostapp.urls', namespace='bostapp')),  # Include with namespace
]