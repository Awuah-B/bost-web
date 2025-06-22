from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
import csv
import json
import datetime
import os
import pandas as pd
from io import BytesIO
import requests
from fpdf import FPDF
import tempfile


class RequestSeek:
    def __init__(self):
        dt = datetime.datetime.now()
        delta = dt - datetime.timedelta(days=1)
        self.date = delta.strftime("%d-%m-%Y")
        self.date2 = dt.strftime("%d-%m-%Y")
        
        self.url = "https://iml.npa-enterprise.com/NPAAPILIVE/Home/ExportDailyOrderReport"
        
    def parameter(self):
        # Set headers and parameters as URL arguments
        params = {
            'lngCompanyId': 1,
            'szITSfromPersol': 'persol',
            'strGroupBy': 'OMC',
            'strGroupBy1': 'VEROS PETROLEUM LIMITED',
            'strQuery1': '',
            'strQuery2': f'{self.date}',
            'strQuery3': f'{self.date2}',
            'strQuery4': '',
            'strPicHeight': 1,
            'strPicWeight': 1,
            'intPeriodID': -1,
            'iUserId': 123290,
            'iAppId': 4
        }

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'cookie': '__AntiXsrfToken=b3cae1df4114418b97b6b2a5d8805a52; ASP.NET_SessionId=vrjjsrvdikxtrlz3opizx3m1; __zlcmid=1PnnKcYx1PvlGXh',
            'priority': 'u=0, i',
            'referer': 'https://iml.npa-enterprise.com/uppf-bdc-live/reports',
            'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
        }

        try:
            response = requests.get(self.url, headers=headers, params=params)
            response.raise_for_status()
            return BytesIO(response.content)
        except requests.RequestException as e:
            print(f"Error making request: {e}")
            return None

    def process_content(self):
        try:
            xls_data = self.parameter()
            if xls_data is None:
                return None
                
            df = pd.read_excel(xls_data)
            df = df.iloc[7:]
            
            # Convert all column values to string
            for col in df.columns:
                df[col] = df[col].astype(str)
            
            # Remove completely empty rows
            df = df[~df.apply(lambda row: all(val.lower() in ['nan', 'none', ''] or val.isspace() for val in row), axis=1)]
            
            # Remove completely empty columns
            empty_cols = [col for col in df.columns if df[col].apply(
                lambda val: val.lower() in ['nan', 'none', ''] or val.isspace()
            ).all()]
            df = df.drop(columns=empty_cols)

            # Delete rows which contain #Total
            df = df[~df.apply(lambda row: any('Total #' in str(val) for val in row), axis=1)]

            # Replace "nan" with empty string
            df = df.replace('nan', '', regex=True)

            # Get the updated last column
            last_column_name = df.columns[-1]

            # Flag rows with "BOST-KUMASI" or "BOST - KUMASI"
            bost_kumasi_mask = df.apply(
                lambda row: any("BOST-KUMASI" in str(val) or "BOST - KUMASI" in str(val) for val in row), 
                axis=1
            )
                
            # Flag rows with empty last column
            empty_last_col_mask = df[last_column_name].str.strip().eq('')
                
            # Combine masks to get rows meeting either condition
            combined_mask = bost_kumasi_mask | empty_last_col_mask
            df = df[combined_mask]
            
            return df
            
        except Exception as e:
            print(f"Error processing DataFrame: {e}")
            return None

    def custom_formatting(self):
        df = self.process_content()
        if df is None:
            return None

        # Drop column if exists
        if 'Unnamed: 6' in df.columns:
            df = df.drop(columns=['Unnamed: 6'])

        # Merge columns if they exist
        if 'Unnamed: 19' in df.columns and 'Unnamed: 20' in df.columns:
            df = df.drop(columns=['Unnamed: 19', 'Unnamed: 20'])

        # Handle rows where only first column has values
        first_col = df.columns[0]
        mask = df.apply(lambda row: (row != '').sum() == 1 and row[first_col] != '', axis=1)
        if mask.any():
            # Get rows where only first column has value
            special_rows = df[mask].copy()
            # Keep only first occurrence of each value in the first column
            special_rows = special_rows.drop_duplicates(subset=[first_col], keep='first')
            # Update the main dataframe
            df = pd.concat([df[~mask], special_rows]).sort_index()

        # Rename columns
        rename_map = {
            'Unnamed: 0': 'ORDER DATE',
            'Unnamed: 2': 'ORDER NUMBER',
            'Unnamed: 5': 'PRODUCTS',
            'Unnamed: 9': 'VOLUME',
            'Unnamed: 10': 'EX REF PRICE',
            'Unnamed: 12': 'BRV NUMBER',
            'Unnamed: 15': 'BDC',
        }
        df = df.rename(columns=rename_map)
        
        return df

def home(request):
    return render(request, 'bostapp/index.html')

def export_csv(request):
    download = RequestSeek()
    df = download.custom_formatting()
    
    if df is None or df.empty:
        return HttpResponse("No data available for export", status=404)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="omc_report.csv"'
    
    df.to_csv(response, index=False)
    return response

def preview_pdf(request):
    download = RequestSeek()
    df = download.custom_formatting()
    
    if df is None or df.empty:
        return HttpResponse("No data available for PDF", status=404)
    
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=8)
        
        # Add title
        pdf.cell(200, 10, txt="DEPOT: BOST - KUMASI", ln=True, align='C')

        # Calculate dynamic column width
        col_width = pdf.w / len(df.columns)
        row_height = 10

        # Add column headers
        for col in df.columns:
            pdf.cell(col_width, row_height, txt=str(col), align="C")
        pdf.ln(row_height)

        # Add rows
        for _, row in df.iterrows():
            if pdf.get_y() + row_height > pdf.h - 15:
                pdf.add_page()
                for col in df.columns:
                    pdf.cell(col_width, row_height, txt=str(col), align="C")
                pdf.ln(row_height)
            
            for col in df.columns:
                cell_content = str(row[col])
                pdf.cell(col_width, row_height, txt=cell_content, align="L")
            pdf.ln(row_height)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="omc_preview.pdf"'
        response.write(pdf.output(dest='S').encode('latin1'))
        return response
        
    except Exception as e:
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)