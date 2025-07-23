import streamlit as st
from functions_st import get_excel_sheet_names, read_data_file, apply_savgol_filter, generate_interactive_plot, get_min_max_values
import pandas as pd
from io import BytesIO
# C:\Users\zli0003\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\streamlit.exe run c:/Users/zli0003/PycharmProjects/ML_algorithm/streamlit/app.py

def main():
    st.set_page_config(page_title="Data Smoothing & Visualization", page_icon= "📊", 
                    layout="wide")
    st.sidebar.title("Function Selector")
    option = st.sidebar.selectbox("Select", ("Data Smoothing", "Min-Max Values Calculation"))
    this_moment = pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S')

    if option == "Data Smoothing":
        st.title("Data Smoothing & Visualization Tool")

        # Initialize session state for storing smoothed data
        if 'smoothed_data' not in st.session_state:
            st.session_state.smoothed_data = None

        # File upload section
        st.sidebar.header("Data Upload")
        uploaded_file = st.sidebar.file_uploader("Upload Excel/CSV File", type=["xlsx", "xls", "csv"])

        if uploaded_file is not None:
            # Read Excel file
            try:
                # File reading options
                st.sidebar.subheader("File Reading Options")
                # Only show sheet selection for Excel files
                if uploaded_file.name.endswith(('.xlsx', '.xls')):
                    try:
                        sheet_names = get_excel_sheet_names(uploaded_file)
                        sheet_name = st.sidebar.selectbox(
                                "Select Sheet",
                                sheet_names,
                                index=0,
                                help="Select which sheet to load from the Excel/CSV file"
                            )
                    except Exception as e:
                        st.error(f"Error reading sheet names: {str(e)}")
                        st.stop()
                    # sheet_name = st.sidebar.text_input("Sheet Name/Number (optional)", value="0")
                else:
                    sheet_name = 0  # Not used for CSV files
                # Header row selection
                header_row = st.sidebar.number_input("Header Row (0-based)", 
                                            min_value=0, 
                                            max_value=10, 
                                            value=0,
                                            help="Row number (starting from 0) that contains column headers")
                # Read data from the uploaded file
                try:
                    data = read_data_file(uploaded_file, sheet_name=sheet_name, header_row=header_row)
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
                    st.stop()
                
                # Display raw data preview
                st.subheader("Raw Data Preview")
                preview_rows = st.slider("Number of preview rows", 1, 20, 5)

                # Convert object columns to string for Arrow compatibility
                for col in data.select_dtypes(include=['object']).columns:
                    data[col] = data[col].astype(str)
                st.dataframe(data.head(preview_rows))
                
                # Check if the data looks correct
                if st.checkbox("Show full data structure"):
                    st.write("Columns:", data.columns.tolist())
                    if isinstance(data, pd.DataFrame):
                        st.write("Data types:", data.dtypes.astype(str))
                    else:
                        st.dataframe(pd.DataFrame({'Column': data.columns, 'Type': [str(dtype) for dtype in data.schema]}))
                    # st.write("Data types:", data.dtypes)

                # Column selection
                st.sidebar.header("Smoothing Settings")
                all_columns = data.columns.tolist()

                if not all_columns:
                    st.error("No columns found. Please check your header row selection.")
                    st.stop()

                time_column = st.sidebar.selectbox("Select Time Column", all_columns, index=0)
                
                # Select columns to smooth
                columns_to_smooth = st.sidebar.multiselect(
                    "Select Columns to Smooth", 
                    [col for col in all_columns if col != time_column],
                    default=[col for col in ['D1', 'D2', 'D3', 'D4', 'P1', 'Pressure (mbar)'] if col in all_columns]
                )
                
                # Smoothing parameters
                st.sidebar.subheader("Smoothing Parameters")
                window_length = st.sidebar.slider("Window Length (odd)", 3, 101, 21, 2)
                polyorder = st.sidebar.slider("Polynomial Order", 1, 5, 1)
                mode = st.sidebar.selectbox("Boundary Mode", ['nearest', 'mirror', 'constant', 'interp', 'wrap'])
                
                # Apply smoothing
                if st.sidebar.button("Apply Smoothing"):
                    if not columns_to_smooth:
                        st.error("Please select at least one column to smooth.")
                        st.stop()
                    with st.spinner('Processing data...'):
                        st.session_state.smoothed_data = apply_savgol_filter(
                            data, 
                            columns_to_smooth, 
                            window_length=window_length, 
                            polyorder=polyorder, 
                            mode=mode
                        )
                    st.success(f"Data smoothing completed! {this_moment}")

                # If we have smoothed data, show it and allow visualization
                if st.session_state.smoothed_data is not None:
                    # Display smoothed data
                    st.subheader("Smoothed Data")
                    st.dataframe(st.session_state.smoothed_data.head(preview_rows))
                    

                    # Visualization settings in an expandable section
                    with st.sidebar.expander("Visualization Settings", expanded=True):
                        plot_title = st.text_input("Plot Title", "Data Plot")
                        y1_label = st.text_input("Left Y-Axis Label", "Value")
                        y2_label = st.text_input("Right Y-Axis Label", "Value")
                        
                        left_axis_cols_candidates = [col for col in columns_to_smooth if col != time_column]
                        if len(left_axis_cols_candidates) == 1:
                            left_axis_col_initial = left_axis_cols_candidates
                            right_axis_col_initial = [] # No right axis column if only one left axis column
                        elif len(left_axis_cols_candidates) > 1:
                            left_axis_col_initial = left_axis_cols_candidates[:-1]  # Default to all but the last column
                            right_axis_col_initial = left_axis_cols_candidates[-1:]  # Default to the last column
                        else:
                            left_axis_col_initial = []
                            right_axis_col_initial = []

                        print(f"Left Axis Columns: {left_axis_col_initial}, Right Axis Column: {right_axis_col_initial}")

                        # Select columns for left axis
                        left_axis_cols = st.multiselect(
                            "Left Axis Columns", 
                            # from the smoothed data, excluding the time column and select the first column
                            [col for col in columns_to_smooth if col != time_column],
                            default=left_axis_col_initial if left_axis_col_initial else None,
                        )
                        
                        right_axis_options = [col for col in all_columns if col != time_column and col not in left_axis_cols]
                        if right_axis_col_initial and right_axis_col_initial[0] in right_axis_options:
                            default_index = right_axis_options.index(right_axis_col_initial[0])
                        else:
                            default_index = 0

                        # Select column for right axis
                        right_axis_col = st.selectbox(
                            "Right Axis Column", 
                            [col for col in all_columns if col != time_column and col not in left_axis_cols],
                            index=default_index
                        )
                        plot_height = st.slider("Plot Height", 400, 1000, 600)
                        # Button to regenerate plot
                        if st.button("Update Plot"):
                            with st.spinner('Generating plot...'):
                                raw_fig = generate_interactive_plot(
                                    st.session_state.smoothed_data,
                                    x_col=time_column,
                                    y1_cols=left_axis_cols,
                                    y2_col=right_axis_col,
                                    x_label=time_column,
                                    y1_label=y1_label,
                                    y2_label=y2_label,
                                    title=f"{plot_title} - Raw Data",
                                    height=plot_height
                                )
                                # Ensure right_axis_col is a single column name, not a list
                                if isinstance(right_axis_col, list):
                                    right_axis_col = right_axis_col[0] if right_axis_col else None
                                # Handle right axis column name for smoothed data
                                if right_axis_col:
                                    y2_col_smoothed = (f"{right_axis_col}_smoothed" 
                                                    if right_axis_col in columns_to_smooth 
                                                    else right_axis_col)
                                else:
                                    y2_col_smoothed = None

                                smoothed_fig = generate_interactive_plot(
                                    st.session_state.smoothed_data,
                                    x_col=time_column,
                                    y1_cols=[f"{col}_smoothed" for col in left_axis_cols],
                                    y2_col=y2_col_smoothed if y2_col_smoothed and y2_col_smoothed in st.session_state.smoothed_data.columns else right_axis_col,
                                    x_label=time_column,
                                    y1_label=y1_label,
                                    y2_label=y2_label,
                                    title=f"{plot_title} - Smoothed Data",
                                    height=plot_height
                                )
                                st.session_state.raw_fig = raw_fig
                                st.session_state.smoothed_fig = smoothed_fig
                    


                    # Display the plot (either initial or updated)
                    if 'raw_fig' in st.session_state and 'smoothed_fig' in st.session_state:
                        st.plotly_chart(st.session_state.raw_fig, use_container_width=True)
                        st.plotly_chart(st.session_state.smoothed_fig, use_container_width=True)
                    elif st.session_state.smoothed_data is not None:
                        # Generate initial plot if none exists yet
                        with st.spinner('Generating initial plot...'):
                            raw_fig = generate_interactive_plot(
                                data,
                                x_col=time_column,
                                y1_cols=left_axis_col_initial,
                                y2_col=right_axis_col_initial[0] if right_axis_col_initial else None,
                                x_label=time_column,
                                y1_label="Value",
                                y2_label="Value",
                                title="Raw Data",
                                height=600
                            )
                            y2_col_smtd = (f"{right_axis_col_initial[0]}_smoothed"
                                    if right_axis_col_initial and f"{right_axis_col_initial[0]}_smoothed" in st.session_state.smoothed_data.columns
                                    else (right_axis_col_initial[0] if right_axis_col_initial else None)
                                    )
                            smoothed_fig = generate_interactive_plot(
                                st.session_state.smoothed_data,
                                x_col=time_column,
                                y1_cols=[f"{col}_smoothed" for col in left_axis_col_initial 
                                        if f"{col}_smoothed" in st.session_state.smoothed_data.columns],
                                y2_col=y2_col_smtd,
                                x_label=time_column,
                                y1_label="Value",
                                y2_label="Value",
                                title="Smoothed Data",
                                height=600
                            )
                            st.session_state.raw_fig = raw_fig
                            st.session_state.smoothed_fig = smoothed_fig

                            st.plotly_chart(raw_fig, use_container_width=True)
                            st.plotly_chart(smoothed_fig, use_container_width=True)
                    
                    # Data export
                    st.sidebar.header("Data Export")
                    if st.sidebar.button("Generate Smoothed Data"):
                        if st.session_state.smoothed_data is None:
                            st.sidebar.error("No smoothed data available to download")
                        else:
                            output = BytesIO()
                            try:
                                # Fall back to openpyxl
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    st.session_state.smoothed_data.to_excel(writer, index=False)
                            except ImportError:
                                st.sidebar.error("Openpyxl is installed. Please install one of them.")
                                st.stop()
                            st.sidebar.success("Smoothed data is ready, click below to download.")
                            st.sidebar.download_button(
                                label="Click to Download Excel File",
                                data=output.getvalue(),
                                file_name=f"{sheet_name}_smoothed_data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
            
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
        else:
            st.info("Please upload an Excel/CSV file to begin")

    if option == "Min-Max Values Calculation":
        st.title("Min-Max Values Calculation Tool")
        # Files upload section
        st.sidebar.header("File Upload")
        uploaded_files = st.sidebar.file_uploader("Upload Excel/CSV Files", 
                                                type=["xlsx", "xls", "csv"],
                                                accept_multiple_files=True,
                                                help="Select multiple files for min-max calculation")
        preview_rows = st.slider("Number of preview rows", 1, 20, 5, 
                                help="Select number of preview rows.")
        if uploaded_files:
            # Initialize results dataframe
            # results = []
            file_settings = {}  # Store header row settings for each file
            
            # Create a form for header row settings
            with st.form("header_settings"):
                st.subheader("Header Row Configuration")
                
                # Create settings for each file
                for file_idx, file in enumerate(uploaded_files):
                    st.markdown(f"**{file.name}**")
                    
                    # Different settings for Excel vs CSV
                    if file.name.endswith(('.xlsx', '.xls')):
                        try:
                            excel_file = pd.ExcelFile(file)
                            sheet_names = excel_file.sheet_names
                            
                            for sheet_idx, sheet_name in enumerate(sheet_names):
                                # Preview first few rows to help user decide
                                df_preview = pd.read_excel(file, sheet_name=sheet_name, header=None)
                                df_preview = df_preview.astype(str)
                                st.write(f"Sheet: {sheet_name} - First {preview_rows} rows:")
                                st.dataframe(df_preview.head(preview_rows))
                                
                                header_row = st.number_input(
                                    f"Header row for {file.name} - {sheet_name}",
                                    min_value=0,
                                    max_value=20,
                                    value=0,
                                    key=f"header_{file_idx}_{sheet_idx}"
                                )
                                file_settings[(file.name, sheet_name)] = header_row

                                if header_row > 0:
                                    # Read with specified header row
                                    warning_container.warning("⚠️ Warning: Header row is not set to 0. "
                                        "Make sure you're selecting the correct row containing column headers.")
                        except Exception as e:
                            st.error(f"Error previewing {file.name}: {str(e)}")
                    else:  # CSV files
                        # Preview first few rows to help user decide
                        df_preview = pd.read_csv(file, header=None)
                        df_preview = df_preview.astype(str)
                        st.write(f"File: {file.name} - First {preview_rows} rows:")
                        st.dataframe(df_preview.head(preview_rows))
                        
                        header_row = st.number_input(
                            f"Header row for {file.name}",
                            min_value=0,
                            max_value=20,
                            value=0,
                            key=f"header_{file_idx}"
                        )
                        file_settings[file.name] = header_row
                
                # Submit button for the form
                submitted = st.form_submit_button("Apply Settings and Process Files")
            
            if submitted:
                with st.spinner('Processing files...'):
                    try:
                        # Read and process each file with the specified header row
                        results = []
                        results_df = get_min_max_values(uploaded_files, results, file_settings)
                        # Store results in session state
                        st.session_state.results_df = results_df
                        # Display results
                        st.subheader("Min-Max Results")
                        st.dataframe(results_df)
                        # Add success message
                        st.success("Files processed successfully!")
                    except Exception as e:
                        st.error(f"Error processing files: {str(e)}")

            # Export to Excel
            st.sidebar.header("Export Results")
            if st.sidebar.button("Generate Min-Max Report"):
                print(f"Generating report at {this_moment}")
                if 'results_df' not in st.session_state or st.session_state.results_df.empty:
                    st.sidebar.warning("No data available to generate report.")
                else:
                    try:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            st.session_state.results_df.to_excel(writer, index=False, sheet_name='Min-Max Results')
                        output.seek(0)  # Reset the BytesIO object to the beginning
                        st.sidebar.success("Report generated successfully!")
                        st.sidebar.download_button(
                            label="Download Min-Max Report",
                            data=output,
                            file_name=f"min_max_report_{this_moment}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.sidebar.error(f"Error generating report: {str(e)}")
        else:
            st.info("Please upload Excel/CSV files to begin")

if __name__ == '__main__':
    main()