from django.urls import path
from . import views

app_name = 'bostapp'

urlpatterns = [
    path('', views.home, name='index'),
    path('export-pdf/', views.preview_pdf, name='export_pdf'),  # Use preview_pdf for export-pdf
    path('export-csv/', views.export_csv, name='export_csv'),
]