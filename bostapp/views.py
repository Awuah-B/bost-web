from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from fpdf import FPDF
import pandas as pd
import requests
from io import BytesIO
import datetime
import logging
import traceback

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
        self.font = "Arial"  # Use Arial which is more reliable
        
    def generate(self, df, title):
        """Generate PDF from DataFrame"""
        try:
            if df is None or df.empty:
                return None, "No data available for PDF generation"
                    
            pdf = FPDF(orientation='L', unit='mm', format='A4')
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
                
            # Title
            pdf.set_font(self.font, 'B', 16)
            pdf.cell(0, 10, title, ln=True, align='C')
            pdf.ln(10)
                
            # Calculate column widths
            pdf.set_font(self.font, size=8)
            page_width = pdf.w - 20  # Account for margins
            num_cols = len(df.columns)
            col_width = page_width / num_cols
            
            # Limit column width to reasonable size
            col_widths = [min(col_width, 40) for _ in df.columns]
                
            # Header
            pdf.set_font(self.font, 'B', 8)
            for col, width in zip(df.columns, col_widths):
                # Truncate long column names
                col_text = str(col)[:15] + "..." if len(str(col)) > 15 else str(col)
                pdf.cell(width, 8, col_text, border=1, align='C')
            pdf.ln()
                
            # Rows
            pdf.set_font(self.font, size=7)
            for _, row in df.iterrows():
                if pdf.get_y() + 8 > pdf.h - 15:
                    self._add_header_page(pdf, df, col_widths)
                    
                for col, width in zip(df.columns, col_widths):
                    # Truncate long cell values
                    cell_text = str(row[col])[:20] + "..." if len(str(row[col])) > 20 else str(row[col])
                    pdf.cell(width, 8, cell_text, border=1)
                pdf.ln()
                    
            # Use BytesIO to handle binary output properly
            pdf_output = BytesIO()
            pdf_string = pdf.output(dest='S')
            
            # Handle encoding properly
            if isinstance(pdf_string, str):
                pdf_output.write(pdf_string.encode('latin1'))
            else:
                pdf_output.write(pdf_string)
            
            pdf_output.seek(0)
            return pdf_output.getvalue(), None
                
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            logger.error(f"PDF generation traceback: {traceback.format_exc()}")
            return None, f"PDF generation failed: {str(e)}"
            
    def _add_header_page(self, pdf, df, col_widths):
        """Add new page with headers"""
        pdf.add_page()
        pdf.set_font(self.font, 'B', 8)
        for col, width in zip(df.columns, col_widths):
            col_text = str(col)[:15] + "..." if len(str(col)) > 15 else str(col)
            pdf.cell(width, 8, col_text, border=1, align='C')
        pdf.ln()
        pdf.set_font(self.font, size=7)

def home(request):
    """Home view with error handling"""
    try:
        return render(request, 'bostapp/index.html')
    except Exception as e:
        logger.error(f"Home view error: {str(e)}")
        logger.error(f"Home view traceback: {traceback.format_exc()}")
        return HttpResponse("Application temporarily unavailable. Please try again later.", 
                          status=500, content_type='text/plain')

def export_csv(request):
    """Export CSV with comprehensive error handling"""
    try:
        fetcher = DataFetcher()
        df, error = fetcher.fetch_data()
        
        if error:
            logger.error(f"CSV export fetch error: {error}")
            return HttpResponse(f"Error: {error}", status=500, content_type='text/plain')
            
        df, error = fetcher.process_data(df)
        
        if error:
            logger.error(f"CSV export process error: {error}")
            return HttpResponse(f"Error: {error}", status=404, content_type='text/plain')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="omc_report.csv"'
        df.to_csv(response, index=False)
        return response
        
    except Exception as e:
        logger.error(f"CSV export unexpected error: {str(e)}")
        logger.error(f"CSV export traceback: {traceback.format_exc()}")
        return HttpResponse(f"Unexpected error: {str(e)}", status=500, content_type='text/plain')

def generate_pdf_response(request, disposition='inline'):
    """Generate PDF response with comprehensive error handling"""
    try:
        fetcher = DataFetcher()
        generator = PDFGenerator()
        
        # Fetch data
        df, error = fetcher.fetch_data()
        if error:
            logger.error(f"PDF generation fetch error: {error}")
            return HttpResponse(f"Error: {error}", status=500, content_type='text/plain')
            
        # Process data
        df, error = fetcher.process_data(df)
        if error:
            logger.error(f"PDF generation process error: {error}")
            return HttpResponse(f"Error: {error}", status=404, content_type='text/plain')
        
        # Generate PDF
        pdf_content, error = generator.generate(df, "DEPOT: BOST - KUMASI")
        if error:
            logger.error(f"PDF generation error: {error}")
            return HttpResponse(f"Error: {error}", status=500, content_type='text/plain')
        
        # Return response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = "omc_report.pdf"
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f"PDF response unexpected error: {str(e)}")
        logger.error(f"PDF response traceback: {traceback.format_exc()}")
        return HttpResponse(f"Unexpected error: {str(e)}", status=500, content_type='text/plain')

def preview_pdf(request):
    """Preview PDF with error handling"""
    try:
        return generate_pdf_response(request, disposition='inline')
    except Exception as e:
        logger.error(f"PDF preview error: {str(e)}")
        return HttpResponse(f"PDF preview error: {str(e)}", status=500, content_type='text/plain')

def download_pdf(request):
    """Download PDF with error handling"""
    try:
        return generate_pdf_response(request, disposition='attachment')
    except Exception as e:
        logger.error(f"PDF download error: {str(e)}")
        return HttpResponse(f"PDF download error: {str(e)}", status=500, content_type='text/plain')

def health_check(request):
    """Health check endpoint for debugging"""
    try:
        return JsonResponse({
            'status': 'ok',
            'timestamp': datetime.datetime.now().isoformat(),
            'message': 'Application is running'
        })
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)