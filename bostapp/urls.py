from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from bostapp import views

def simple_health_check(request):
    """Simple health check that doesn't depend on external services"""
    return HttpResponse("OK", status=200, content_type='text/plain')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('export-csv/', views.export_csv, name='export_csv'),
    path('preview-pdf/', views.preview_pdf, name='preview_pdf'),
    path('download-pdf/', views.download_pdf, name='download_pdf'),
    path('health/', views.health_check, name='health_check'),
    path('simple-health/', simple_health_check, name='simple_health'),
]