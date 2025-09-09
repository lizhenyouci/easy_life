from scipy.signal import savgol_filter
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import chardet
import pandas as pd
from typing import List

# create requirements.txt file
# & "C:\Users\zli0003\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\pipreqs.exe" . --encoding=utf8 --force

def get_excel_sheet_names(file_path):
    """Get all sheet names from an Excel file"""
    try:
        if file_path.name.endswith(('.xlsx', '.xls')):
            sheet_name = pd.ExcelFile(file_path).sheet_names
        else: 
            sheet_name = 0
        return sheet_name
    except Exception as e:
        raise Exception(f"Error reading Excel sheets: {e}")

def detect_skiprows_and_encoding(uploaded_file, comment_chars=('#', '!', '*', '//', '%'), delimiter=','):
    """
    Modified version for Streamlit UploadedFile objects
    
    Args:
        uploaded_file (UploadedFile): Streamlit file uploader object
        comment_chars (tuple): Characters that indicate comment lines
        delimiter (str): Column delimiter
        
    Returns:
        tuple: (skiprows, encoding) Number of rows to skip and detected encoding
    """
    # Read the file content directly from UploadedFile
    raw_content = uploaded_file.getvalue()
    
    # Detect encoding
    result = chardet.detect(raw_content)
    encoding = result['encoding']
    
    # Try reading with detected encoding and fallbacks
    try_encodings = [encoding, 'utf-8', 'latin1', 'gbk', 'gb2312', 'gb18030', 'cp1252']
    detected_encoding = None
    lines = None
    
    for enc in try_encodings:
        try:
            content = raw_content.decode(enc)
            lines = content.splitlines()
            detected_encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    
    if lines is None:
        raise UnicodeDecodeError(f"Failed to decode file with encodings: {try_encodings}")
    
    # Find header row (first non-comment row containing delimiter)
    skiprows = 0
    found_header = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:  # Empty line
            skiprows += 1
            continue
        if stripped.startswith(comment_chars):  # Comment line
            skiprows += 1
            continue
        if delimiter in stripped:  # Header or data row
            found_header = True
            break
    
    if not found_header:
        raise ValueError("No valid header row found")
    
    return skiprows, detected_encoding

def read_data_file(file_path, sheet_name=0, header_row=0):
    """
    Read data from an Excel file or CSV file.
    
    Parameters:
    file_path (str): Path to the Excel file
    sheet_name (str or int, optional): Sheet name or index, defaults to first sheet
    
    Returns:
    pd.DataFrame: Loaded data
    """
    try:
        if file_path.name.endswith('.csv'):
            data = pd.read_csv(file_path, header=header_row, engine='c',dtype_backend='pyarrow')
        else:
            sheet_name = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
            data = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row, engine='openpyxl', dtype_backend='pyarrow')
        return data
    except Exception as e:
        raise Exception(f"Error reading Excel file: {e}")


def find_header_row(file, file_type, sheet_name, preview_lines=10):

    try_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1', 'cp1252']
    best_encoding = None
    best_skiprows = 0
    max_non_empty = -1  # to track the best result

    for enc in try_encodings:
        for skiprows_candidate in range(0, preview_lines): 
            try:
                file.seek(0)  
                if file_type == 'excel':
                    df_try = pd.read_excel(
                        file, sheet_name=sheet_name, nrows=preview_lines, header=None, skiprows=skiprows_candidate
                    )
                elif file_type == 'csv':
                    df_try = pd.read_csv(
                        file, nrows=preview_lines, header=None, encoding=enc, skiprows=skiprows_candidate
                    )
                else:
                    raise ValueError("file_type must be 'excel' or 'csv'")

                # choose the one with the most non-empty cells
                non_empty_count = df_try.notna().sum().sum()
                num_rows, num_cols = df_try.shape

                if num_cols < 1:
                    continue  # No columns, skip

                if non_empty_count > max_non_empty:
                    max_non_empty = non_empty_count
                    best_encoding = enc
                    best_skiprows = skiprows_candidate

            except (UnicodeDecodeError, LookupError, ValueError, pd.errors.ParserError):
                # skip invalid encodings or parsing errors
                continue

    if best_encoding is None:
        raise ValueError("Failed to determine header row and encoding")

    return best_skiprows, best_encoding

def read_upload_files(uploaded_files: List, preview_rows:int) -> pd.DataFrame:
    """
    Process uploaded Excel/CSV files, allow header selection, show previews,
    and return a summary DataFrame of all processed files.
    """
    summary_data = []
    
    # Create settings for each file
    for file_idx, file in enumerate(uploaded_files):
        file_name = file.name
        st.markdown(f"**{file_name}**")

        try:
            # Read file based on type with user-specified header row
            if file_name.endswith(('.xlsx', '.xls')):
                excel_file = pd.ExcelFile(file)
                sheet_names = excel_file.sheet_names

                for sheet_idx, sheet_name in enumerate(sheet_names):
                    try:
                        skip, enc = find_header_row(file, file_type='excel', sheet_name=sheet_name, preview_lines=10)
                        file.seek(0)  # Reset file pointer
                        df = pd.read_excel(file, sheet_name=sheet_name, header=None,skiprows=skip)
                        st.write(f"Sheet: {sheet_name} - First {preview_rows} rows:")
                        st.dataframe(df.head(preview_rows))
                        # Allow user to specify header row if not already set
                        header_row = st.number_input(
                                    f"Header row for {file_name} - {sheet_name}",
                                    min_value=0,
                                    max_value=20,
                                    value=0,
                                    key=f"header_{file_idx}_{sheet_idx}"
                                )
                        # Allow user to select columns to display
                        select_cols = st.multiselect(
                                    f"Select columns to display for {file.name} - {sheet_name}",
                                    options=list(df.columns),
                                    default=list(df.columns)[:len(df.columns)],
                                    key=f"select_cols_{file_idx}"
                                )
                        # Re-read with user-selected header
                        file.seek(0)  # Reset file pointer
                        df_final_user_selected = pd.read_excel(file, sheet_name=sheet_name, header=header_row, skiprows=skip)
                        df_final = df_final_user_selected.iloc[:, select_cols] if select_cols else df_final_user_selected
                        # st.dataframe(df_final.head(preview_rows))
                        # Add to summary
                        summary_data.append({
                            'file_idx': file_idx,
                            'file_name': file_name,
                            'sheet_idx': sheet_idx,
                            'sheet_name': sheet_name,
                            'file_type': 'Excel',
                            'skiprows': skip,
                            'rows': len(df_final),
                            'header_row': header_row,
                            'select_cols': select_cols,
                            'columns': len(df_final.columns),
                            'column_names': list(df_final.columns),
                            'status': 'Success',
                            'dataframe': df_final
                        })

                    except Exception as e:
                        st.warning(f"Error processing {file.name} (sheet: {sheet_name}): {str(e)}")
                        continue
            elif file.name.endswith('.csv'):  # CSV files
                try:
                    skip, enc = find_header_row(file, file_type='csv', sheet_name=None, preview_lines=10)
                    print(f"Detected skiprows for {file.name}: {skip}, encoding: {enc}")
                    file.seek(0)  # Reset file pointer
                    df = pd.read_csv(file, header=None, skiprows=skip, encoding=enc)
                    sheet_idx = 0
                    sheet_name = 'N/A'
                    st.write(f"File: {file.name} - First {preview_rows} rows:")
                    st.dataframe(df.head(preview_rows))
                    # Allow user to specify header row if not already set
                    header_row = st.number_input(
                                    f"Header row for {file.name}",
                                    min_value=0,
                                    max_value=20,
                                    value=0,
                                    key=f"header_{file_idx}"
                                )
                    # Allow user to select columns to display
                    select_cols = st.multiselect(
                                    f"Select columns to display for {file.name}",
                                    options=list(df.columns),
                                    default=list(df.columns)[:len(df.columns)],
                                    key=f"select_cols_{file_idx}"
                                )
                    # Re-read with user-selected header
                    file.seek(0)  # Reset file pointer
                    df_final_user_selected = pd.read_csv(file, header=header_row, skiprows=skip, encoding=enc)
                    df_final = df_final_user_selected.iloc[:, select_cols] if select_cols else df_final_user_selected
                    # st.dataframe(df_final.head(preview_rows))
                    # print(df_final.head())
                    # Add to summary
                    summary_data.append({
                        'file_idx': file_idx,
                        'file_name': file_name,
                        'sheet_idx': sheet_idx,
                        'sheet_name': sheet_name,
                        'file_type': 'CSV',
                        'skiprows': skip,
                        'rows': len(df_final),
                        'header_row': header_row,
                        'select_cols': select_cols,
                        'columns': len(df_final.columns),
                        'column_names': list(df_final.columns),
                        'status': 'Success',
                        'dataframe': df_final
                    })
                    
                except Exception as e:
                    st.warning(f"Error processing {file.name}: {str(e)}")
                    summary_data.append({
                        'file_idx': file_idx,
                        'file_name': file_name,
                        'sheet_idx': 0,
                        'sheet_name': 'N/A',
                        'file_type': 'Error',
                        'skiprows': 0,
                        'rows': 0,
                        'header_row': 0,
                        'select_cols': [],
                        'columns': 0,
                        'column_names': [],
                        'status': f'Error: {str(e)}',
                        'dataframe': None
                    })
        
        except Exception as e:
            st.warning(f"Error opening {file.name}: {str(e)}")
            continue

    result_df = pd.DataFrame(summary_data)
    print(result_df)

    return result_df


def apply_savgol_filter(data, columns, window_length=21, polyorder=1, mode='nearest'):
    """
    Apply Savitzky-Golay smoothing filter
    
    Parameters:
    data (pd.DataFrame): Input data
    columns (list): List of column names to smooth
    window_length (int): Window length (must be odd)
    polyorder (int): Polynomial order
    mode (str): Boundary handling mode
    
    Returns:
    pd.DataFrame: Smoothed data
    """
    if not isinstance(data, pd.DataFrame):
        raise ValueError("Input data must be a pandas DataFrame")
    
    smoothed_data = data.copy()
    for column in columns:
        if column in smoothed_data.columns:
            if len(data) > 100000:
                chunks = np.array_split(data[column].values, len(data) // 50000)
                smoothed = np.concatenate([
                    savgol_filter(chunk, window_length=window_length, polyorder=polyorder, mode=mode)
                    for chunk in chunks
                ])
            else:
                smoothed = savgol_filter(data[column], 
                                          window_length=window_length, 
                                          polyorder=polyorder, 
                                          mode=mode)
            smoothed_column = f"{column}_smoothed"
            smoothed_data[smoothed_column] = smoothed
            
    return smoothed_data


def generate_interactive_plot(data, x_col, y1_cols, y2_col=None, 
                            x_label=None, y1_label=None, y2_label=None, 
                            title=None, height=600):
    """
    Generate interactive plot with Plotly
    
    Parameters:
    data (pd.DataFrame): Input data
    x_col (str): x-axis column name
    y1_cols (list): List of columns for left y-axis
    y2_col (str, optional): Column for right y-axis
    x_label (str, optional): x-axis label
    y1_label (str, optional): left y-axis label
    y2_label (str, optional): right y-axis label
    title (str, optional): Plot title
    height (int): Plot height in pixels
    
    Returns:
    plotly.graph_objects.Figure: Interactive plot figure
    """
    # Create figure with secondary y-axis if needed
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add traces for left y-axis
    for col in y1_cols:
        if col in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data[x_col],
                    y=data[col],
                    name=col,
                    mode='lines',
                    line=dict(width=2)
                ),
                secondary_y=False
            )
    
    # Add trace for right y-axis if specified
    if y2_col and y2_col in data.columns:
        fig.add_trace(
            go.Scatter(
                x=data[x_col],
                y=data[y2_col],
                name=y2_col,
                mode='lines',
                line=dict(width=2, color='purple')
            ),
            secondary_y=True
        )
    
    # Update layout
    fig.update_layout(
        title=title or "Interactive Plot",
        height=height,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50),
        xaxis=dict(title=x_label or x_col),
        yaxis=dict(title=y1_label or "Value"),
    )
    
    fig.update_yaxes(title_text=y2_label or y2_col, secondary_y=True)
    
    return fig

def extract_min_max_values(results_df):
    """
    Calculate min/max values for numeric columns in the processed DataFrames.
    
    Args:
        uploaded_files: List of uploaded files (for reference)
        results_df: DataFrame containing processed file information from read_upload_files
        file_settings: Optional dictionary of file settings (not needed if using results_df)
    
    Returns:
        DataFrame with min/max values for each numeric column
    """
    extreme_values = []
    
    # Iterate through each processed file in the results DataFrame
    if isinstance(results_df, pd.DataFrame):
        for _, row in results_df.iterrows():
            if row['status'] != 'Success' or row['dataframe'] is None:
                continue
                
            df = row['dataframe']
            
            # Calculate min/max for each column
            for col in df.columns:
                try:
                    # Convert to numeric if possible
                    numeric_series = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_series.isna().all():  # If at least some numeric values
                        min_val = numeric_series.min()
                        max_val = numeric_series.max()
                        extreme_values.append({
                            'Filename': row['file_name'],
                            'Sheet': row['sheet_name'],
                            'Column': str(col),
                            'Min Value': float(min_val) if pd.notna(min_val) else None,
                            'Max Value': float(max_val) if pd.notna(max_val) else None
                            # 'File Type': row['file_type'],
                            # 'Header Row': row['header_row'],
                            # 'Selected Columns': row['select_cols']
                        })
                except Exception:
                    continue
    else:
        # Process as list of dicts
        for result in results_df:
            if result['status'] != 'Success' or result['dataframe'] is None:
                continue
                
            df = result['dataframe']
            
            for col in df.columns:
                try:
                    numeric_series = pd.to_numeric(df[col], errors='coerce')
                    if not numeric_series.isna().all():
                        min_val = numeric_series.min()
                        max_val = numeric_series.max()
                        extreme_values.append({
                            'Filename': result['file_name'],
                            'Sheet': result['sheet_name'],
                            'Column': str(col),
                            'Min Value': float(min_val) if pd.notna(min_val) else None,
                            'Max Value': float(max_val) if pd.notna(max_val) else None
                            # 'File Type': result['file_type'],
                            # 'Header Row': result['header_row'],
                            # 'Selected Columns': result['select_cols']
                        })
                except Exception:
                    continue   
    if extreme_values:
        results_df_extreme = pd.DataFrame(extreme_values)
        
        # Convert all object columns to string for Arrow compatibility
        for col in results_df_extreme.select_dtypes(include=['object']).columns:
            results_df_extreme[col] = results_df_extreme[col].astype(str)
        return results_df_extreme
    else:
        return pd.DataFrame(columns=['Filename', 'Sheet', 'Column', 'Min Value', 'Max Value'
                                #    'File Type', 'Header Row', 'Selected Columns'
                                   ])
    
def get_min_max_values(uploaded_files, results, file_settings):
    for file in uploaded_files:
        try:
            # Read file based on type with user-specified header row
            if file.name.endswith(('.xlsx', '.xls')):
                excel_file = pd.ExcelFile(file)
                for sheet_name in excel_file.sheet_names:
                    header_row = file_settings.get((file.name, sheet_name), 0)
                    try:
                        df = pd.read_excel(file, 
                                            sheet_name=sheet_name, 
                                            header=header_row
                                            )
                        
                        # If header row was specified but didn't work, try again with header=None
                        if any('Unnamed' in col for col in df.columns):
                            df = pd.read_excel(file, 
                                                sheet_name=sheet_name, 
                                                header=None)
                            actual_header = header_row
                            df.columns = df.iloc[actual_header].astype(str)
                            df = df.iloc[actual_header+1:].reset_index(drop=True)
                        
                        # Calculate min/max for each column
                        for col in df.columns:
                            try:
                                # Convert to numeric if possible
                                numeric_series = pd.to_numeric(df[col], errors='coerce')
                                if not numeric_series.isna().all():  # If at least some numeric values
                                    min_val = numeric_series.min()
                                    max_val = numeric_series.max()
                                    results.append({
                                        'Filename': str(file.name),
                                        'Sheet': str(sheet_name),
                                        'Column': str(col),
                                        'Min Value': float(min_val) if pd.notna(min_val) else 'N/A',
                                        'Max Value': float(max_val) if pd.notna(max_val) else 'N/A'
                                    })
                            except Exception:
                                continue
                    except Exception as e:
                        st.warning(f"Error processing {file.name} (sheet: {sheet_name}): {str(e)}")
                        continue
            else:  # CSV files
                header_row = file_settings.get(file.name, 0)
                file.seek(0)
                try:
                    df = pd.read_csv(file, 
                                     header=header_row)
                    # If header row was specified but didn't work, try again with header=None
                    if any('Unnamed' in col for col in df.columns):
                        file.seek(0)
                        df = pd.read_csv(file, header=None)
                        actual_header = header_row
                        df.columns = df.iloc[actual_header].astype(str)
                        df = df.iloc[actual_header+1:].reset_index(drop=True)
                    
                    # Calculate min/max for each column
                    for col in df.columns:
                        try:
                            numeric_series = pd.to_numeric(df[col], errors='coerce')
                            if not numeric_series.isna().all():
                                min_val = numeric_series.min()
                                max_val = numeric_series.max()
                                results.append({
                                    'Filename': str(file.name),
                                    'Sheet': 'N/A',
                                    'Column': str(col),
                                    'Min Value': float(min_val) if pd.notna(min_val) else None,
                                    'Max Value': float(max_val) if pd.notna(max_val) else None
                                })
                        except Exception:
                            continue
                except Exception as e:
                    st.warning(f"Error processing {file.name}: {str(e)}")
                    continue
        
        except Exception as e:
            st.warning(f"Error opening {file.name}: {str(e)}")
            continue
    if results:
        results_df = pd.DataFrame(results)

        # Convert all object columns to string for Arrow compatibility
        for col in results_df.select_dtypes(include=['object']).columns:
            results_df[col] = results_df[col].astype(str)
        return results_df
    else:
        return pd.DataFrame(columns=['Filename', 'Sheet', 'Column', 'Min Value', 'Max Value'])

def get_integer_values(uploaded_files, results, file_settings):
    for file in uploaded_files:
        try:
            # Read file based on type with user-specified header row
            if file.name.endswith(('.xlsx', '.xls')):
                excel_file = pd.ExcelFile(file)
                for sheet_name in excel_file.sheet_names:
                    header_row = file_settings.get((file.name, sheet_name), 0)
                    try:
                        df = pd.read_excel(file, 
                                          sheet_name=sheet_name, 
                                          header=header_row)
                        
                        # If header row was specified but didn't work, try again with header=None
                        if any('Unnamed' in col for col in df.columns):
                            df = pd.read_excel(file, 
                                             sheet_name=sheet_name, 
                                             header=None)
                            actual_header = header_row
                            df.columns = df.iloc[actual_header].astype(str)
                            df = df.iloc[actual_header+1:].reset_index(drop=True)
                        
                        # Get integer values for each column
                        for col in df.columns:
                            try:
                                # Convert to numeric and filter integers
                                numeric_series = pd.to_numeric(df[col], errors='coerce')
                                integer_values = numeric_series.dropna()[numeric_series.dropna().apply(lambda x: x.is_integer())]
                                
                                if not integer_values.empty:
                                    for val in integer_values:
                                        results.append({
                                            'Filename': str(file.name),
                                            'Sheet': str(sheet_name),
                                            'Column': str(col),
                                            'Integer Value': int(val)
                                        })
                            except Exception:
                                continue
                    except Exception as e:
                        st.warning(f"Error processing {file.name} (sheet: {sheet_name}): {str(e)}")
                        continue
            else:  # CSV files
                file.seek(0)
                header_row = file_settings.get(file.name, 0)[0]
                encoding_ = file_settings.get(file.name, 0)[1]
                print(f"Processing CSV file: {file.name} with header row: {header_row}, encoding: {encoding_}")
                try:
                    df = pd.read_csv(file, skiprows=0, header=header_row, encoding=encoding_ )
                    print(df.head())
                    print(f"Columns in {file.name}: {df.columns.tolist()}")
                    
                    # If header row was specified but didn't work, try again with header=None
                    if any('Unnamed' in col for col in df.columns):
                        df = pd.read_csv(file, skiprows=0, header=None, encoding=encoding_ )
                        actual_header = header_row
                        print(f"Using header row: {actual_header} for {file.name}")
                        df.columns = df.iloc[actual_header].astype(str)
                        df = df.iloc[actual_header+1:].reset_index(drop=True)
                    print("3")
                    # Get integer values for each column
                    for col in df.columns:
                        try:
                            numeric_series = pd.to_numeric(df[col], errors='coerce')
                            print(f"Processing column: {col} in {file.name}")
                            integer_values = numeric_series.dropna()[numeric_series.dropna().apply(lambda x: x.is_integer())]
                            
                            if not integer_values.empty:
                                for val in integer_values:
                                    results.append({
                                        'Filename': str(file.name),
                                        # 'Sheet': 'N/A',
                                        'Column': str(col),
                                        'Integer Value': int(val)
                                    })
                        except Exception:
                            continue
                except Exception as e:
                    st.warning(f"Error processing {file.name}: {str(e)}")
                    continue
        
        except Exception as e:
            st.warning(f"Error opening {file.name}: {str(e)}")
            continue
    
    if results:
        results_df = pd.DataFrame(results)
        
        # Convert all object columns to string for Arrow compatibility
        for col in results_df.select_dtypes(include=['object']).columns:
            results_df[col] = results_df[col].astype(str)
        return results_df
    else:
        return pd.DataFrame(columns=['Filename', 'Sheet', 'Column', 'Integer Value'])

def generate_radar_chart(categories, values_dict, title="Radar Chart", height=600, radial_min=0):
    """
    Generate a radar chart using Plotly.
    """
    fig = go.Figure()
    
    # Define a color palette (you can customize these colors)
    color_palette = [
        '#1f77b4',  # muted blue
        '#ff7f0e',  # safety orange
        '#2ca02c',  # cooked asparagus green
        '#d62728',  # brick red
        '#9467bd',  # muted purple
        '#8c564b',  # chestnut brown
        '#e377c2',  # raspberry yogurt pink
        '#7f7f7f',  # middle gray
        '#bcbd22',  # curry yellow-green
        '#17becf'   # blue-teal
    ]

    max_value = max([max(vals) for vals in values_dict.values() if vals]) if values_dict else 1

    # Ensure all values are non-empty
    all_values = [val for sublist in values_dict.values() for val in sublist]
    max_val = max(all_values) if all_values else 1
    
    # Calculate radial axis minimum
    if radial_min is None:  
        if all_values:
            lower_percentile = np.percentile(all_values, 5)
            radial_min = lower_percentile * 0.9 if lower_percentile > max_val * 0.2 else 0
        else:
            radial_min = 0
    
    # Set radial axis range
    radial_max = max_val * 1.1

    # Add each series with a different color
    for i, (name, values) in enumerate(values_dict.items()):
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself' if len(values_dict) == 1 else None,  # Only fill if single series
            name=name,
            line=dict(color=color_palette[i % len(color_palette)], width=2),
            opacity=0.8
        ))
    label_interval = max(1, len(categories) // 18)  # Adjust label interval based on number of categories

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[radial_min, radial_max]
            ),
            angularaxis=dict(
                # Adjust category label display
                tickmode='array',
                direction="clockwise",
                tickvals=list(range(len(categories)))[::label_interval],  # Skip some labels
                ticktext=categories[::label_interval],  # Skip some labels
                tickangle=45,  # Rotate labels for better readability
                tickfont=dict(size=10)  # Smaller font for more labels
            )
        ),
        showlegend=True,
        title=dict(
            text=title,
            y=0.95,  # Adjust title position
            x=0.5,
            xanchor="center",
            yanchor="top"
        ),
        height=height,
        margin=dict(l=50, r=50, t=80, b=80),  # Adjust margins
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,  # Move legend below chart
            xanchor="center",
            x=0.5,
            font=dict(size=10)  # Smaller legend font
        )
    )
    
    return fig