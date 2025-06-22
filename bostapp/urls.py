from django.urls import path
from . import views

app_name = 'bostapp'

urlpatterns = [
    path('', views.home, name='index'),
    path('preview/', views.preview_pdf, name='preview_data'),
    path('export-excel/', views.export_csv, name='export_excel'),  # Placeholder, not implemented
    path('export-pdf/', views.preview_pdf, name='export_pdf'),
    path('export-csv/', views.export_csv, name='export_csv'),
]