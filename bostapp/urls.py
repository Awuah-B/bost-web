from django.urls import path
from .views import home, export_csv, preview_pdf, download_pdf

app_name = 'bostapp'  # This is crucial for namespace registration

urlpatterns = [
    path('', home, name='home'),
    path('export-csv/', export_csv, name='export_csv'),
    path('preview-pdf/', preview_pdf, name='preview_pdf'),
    path('download-pdf/', download_pdf, name='download_pdf'),
]