from django.shortcuts import render
from django.http import HttpResponse
from fpdf import FPDF
import pandas as pd
import requests
from io import BytesIO
import datetime
import logging

logger = logging.getLogger(__name__)

class DataFetcher:
    """Handles data fetching and processing from the API"""
    
    def __init__(self):
        self.today = datetime.datetime.now()
        self.yesterday = self.today - datetime.timedelta(days=1)
        self.date_format = "%d-%m-%Y"
        
    def fetch_data(self):
        """Fetch data from the API and return as DataFrame"""
        try:
            params = {
                'lngCompanyId': 1,
                'szITSfromPersol': 'persol',
                'strGroupBy': 'OMC',
                'strGroupBy1': 'VEROS PETROLEUM LIMITED',
                'strQuery1': '',
                'strQuery2': self.yesterday.strftime(self.date_format),
                'strQuery3': self.today.strftime(self.date_format),
                'strQuery4': '',
                'strPicHeight': 1,
                'strPicWeight': 1,
                'intPeriodID': -1,
                'iUserId': 123290,
                'iAppId': 4
            }

            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
            }

            response = requests.get(
                "https://iml.npa-enterprise.com/NPAAPILIVE/Home/ExportDailyOrderReport",
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            df = pd.read_excel(BytesIO(response.content))
            if df.empty:
                return None, "Received empty data from API"
            return df, None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return None, f"Failed to fetch data: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error fetching data: {str(e)}")
            return None, f"Unexpected error: {str(e)}"

    def process_data(self, df):
        """Process and clean the DataFrame"""
        try:
            if df is None or df.empty:
                return None, "No data to process"
                
            # Skip header rows
            df = df.iloc[7:]
            
            # Convert all columns to string and clean
            df = df.astype(str)
            df = df.replace('nan', '', regex=True)
            
            # Remove empty rows and columns
            df = df[~df.apply(lambda row: all(val.strip() == '' for val in row), axis=1)]
            df = df.loc[:, ~df.apply(lambda col: all(val.strip() == '' for val in col), axis=0)]
            
            # Filter for BOST-KUMASI records
            mask = df.apply(lambda row: any(
                "BOST-KUMASI" in val or "BOST - KUMASI" in val 
                for val in row
            ), axis=1)
            df = df[mask]
            
            if df.empty:
                return None, "No BOST-KUMASI records found"
            
            # Select and rename columns
            columns = {
                'Unnamed: 0': 'ORDER DATE',
                'Unnamed: 2': 'ORDER NUMBER',
                'Unnamed: 5': 'PRODUCTS',
                'Unnamed: 9': 'VOLUME',
                'Unnamed: 10': 'EX REF PRICE',
                'Unnamed: 12': 'BRV NUMBER',
                'Unnamed: 15': 'BDC'
            }
            
            # Keep only columns that exist in the DataFrame
            available_columns = [col for col in columns.keys() if col in df.columns]
            df = df[available_columns].rename(columns=columns)
            
            return df, None
            
        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            return None, f"Data processing error: {str(e)}"

class PDFGenerator:
    """Handles PDF generation from DataFrame"""
    
    def __init__(self):
        self.font = "Helvetica"  # Use built-in font to avoid warnings
        
    def generate(self, df, title):
        """Generate PDF from DataFrame"""
        try:
            if df is None or df.empty:
                return None, "No data available for PDF generation"
                
            pdf = FPDF(orientation='L')
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            # Title
            pdf.set_font(self.font, 'B', 16)
            pdf.cell(0, 10, title, ln=True, align='C')
            pdf.ln(10)
            
            # Calculate column widths
            pdf.set_font(self.font, size=10)
            col_widths = [
                min(
                    max(
                        pdf.get_string_width(str(col)) + 6,
                        df[col].astype(str).apply(pdf.get_string_width).max() + 6
                    ),
                    60  # Maximum column width
                ) for col in df.columns
            ]
            
            # Header
            pdf.set_font(self.font, 'B', 10)
            for col, width in zip(df.columns, col_widths):
                pdf.cell(width, 10, str(col), border=1, align='C')
            pdf.ln()
            
            # Rows
            pdf.set_font(self.font, size=10)
            for _, row in df.iterrows():
                if pdf.get_y() + 10 > pdf.h - 15:
                    self._add_header_page(pdf, df, col_widths)
                
                for col, width in zip(df.columns, col_widths):
                    pdf.cell(width, 10, str(row[col]), border=1)
                pdf.ln()
                
            return pdf.output(dest='S').encode('latin1'), None
            
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return None, f"PDF generation failed: {str(e)}"
            
    def _add_header_page(self, pdf, df, col_widths):
        """Add new page with headers"""
        pdf.add_page(orientation='L')
        pdf.set_font(self.font, 'B', 10)
        for col, width in zip(df.columns, col_widths):
            pdf.cell(width, 10, str(col), border=1, align='C')
        pdf.ln()
        pdf.set_font(self.font, size=10)

def home(request):
    return render(request, 'bostapp/index.html')

def export_csv(request):
    fetcher = DataFetcher()
    df, error = fetcher.fetch_data()
    
    if error:
        return HttpResponse(f"Error: {error}", status=500, content_type='text/plain')
        
    df, error = fetcher.process_data(df)
    
    if error:
        return HttpResponse(f"Error: {error}", status=404, content_type='text/plain')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="omc_report.csv"'
    df.to_csv(response, index=False)
    return response

def generate_pdf_response(request, disposition='inline'):
    fetcher = DataFetcher()
    generator = PDFGenerator()
    
    # Fetch data
    df, error = fetcher.fetch_data()
    if error:
        return HttpResponse(f"Error: {error}", status=500, content_type='text/plain')
        
    # Process data
    df, error = fetcher.process_data(df)
    if error:
        return HttpResponse(f"Error: {error}", status=404, content_type='text/plain')
    
    # Generate PDF
    pdf_content, error = generator.generate(df, "DEPOT: BOST - KUMASI")
    if error:
        return HttpResponse(f"Error: {error}", status=500, content_type='text/plain')
    
    # Return response
    response = HttpResponse(content_type='application/pdf')
    filename = "omc_report.pdf"
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response.write(pdf_content)
    return response

def preview_pdf(request):
    return generate_pdf_response(request, disposition='inline')

def download_pdf(request):
    return generate_pdf_response(request, disposition='attachment')