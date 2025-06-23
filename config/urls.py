from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('bostapp.urls', 'bostapp'), namespace='bostapp')),  # Note the tuple format
]