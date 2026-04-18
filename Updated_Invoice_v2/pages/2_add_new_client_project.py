import streamlit as st
import pandas as pd
import os

st.sidebar.page_link('pages/0_generate_invoice_DD.py',     label="Generate Invoice",               icon="🏡")
st.sidebar.page_link('pages/1_list_of_clients_projects.py',label="List of Clients / Projects List",icon="📓")    
st.sidebar.page_link('pages/2_add_new_client_project.py',  label="Add New Client/Project record",  icon="✒️")  


file_path = os.path.join(os.getcwd(), 'InvoiceLogTemplate_DD_28062024.xlsx')  # Full file path
worksheet_name = "Clients"

def load_dataframe(file_path, worksheet_name):
    try:
        df = pd.read_excel(file_path, sheet_name= worksheet_name)
        return df
    except FileNotFoundError:
        st.write(f"File {file_path} not found.")
        exit()

df = load_dataframe(file_path, worksheet_name)


tab1, tab2, tab3 = st.tabs(['Add New Client', 'Add Project', 'Add Address'])
with tab1:
    new_client  = st.text_input("Client",  key="new_client")
    new_project = st.text_input("Project", key="project_name")

with tab2:
    clients_drop_down_project   = df['Client'].unique()
    selected_client_project     = st.selectbox("Select Client", clients_drop_down_project, key="select_client_4_project")
    new_project_existing_client = st.text_input("Project", key="project_name_for_existing_client")

with tab3:
    clients_drop_down_address  = df['Client'].unique()
    selected_client_address    = st.selectbox("Select Client", clients_drop_down_address, key="select_client_4_address")
    address                    = st.text_input("Address", key="add_address")


col1, col2, col3 = st.columns([1,1,2])
with col1:
    save_records   = st.button("Create New Client/Project", key="update_record")
with col2:    
    display_record = st.button("Display Record")

try:
    if save_records:
        if not ((df['Client'] == new_client) & (df['Project'] == new_project)).any():
            if new_client or new_project: 
                add_new_record = {
                    'Client' : new_client,
                    'Project': new_project,
                }
                # Read existing data from the Excel file
                xl = pd.ExcelFile(file_path)
                # Load all sheets into a dictionary of DataFrames
                dfs = {sheet_name: xl.parse(sheet_name) for sheet_name in xl.sheet_names}
                # Update the specific sheet with the new record
                if worksheet_name in dfs:
                    df = dfs[worksheet_name]
                    df = pd.concat([df, pd.DataFrame([add_new_record])], ignore_index=True)
                    dfs[worksheet_name] = df
                else:
                    # Handle case where worksheet_name doesn't exist
                    dfs[worksheet_name] = pd.DataFrame([add_new_record])
                 
                # Write all sheets back to the Excel file
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    for sheet_name, df in dfs.items():
                        df.to_excel(writer, index=False, sheet_name=sheet_name)
                st.success("Record Saved Successfully")

            if selected_client_project and new_project_existing_client:
                add_new_record = {
                    'Client' : selected_client_project,
                    'Project': new_project_existing_client,
                }
                # Read existing data from the Excel file
                xl = pd.ExcelFile(file_path)
                # Load all sheets into a dictionary of DataFrames
                dfs = {sheet_name: xl.parse(sheet_name) for sheet_name in xl.sheet_names}
                # Check if the record already exists in any of the sheets
                record_exists = False
                for sheet_name, df in dfs.items():
                    if 'Client' in df.columns and 'Project' in df.columns:
                        if ((df['Client'] == selected_client_project) & (df['Project'] == new_project_existing_client)).any():
                            record_exists = True
                            st.warning("Record Already Exist")
                # If the record doesn't exist, add it
                if not record_exists:
                    if worksheet_name in dfs:
                        df = dfs[worksheet_name]
                        df = pd.concat([df, pd.DataFrame([add_new_record])], ignore_index=True)
                        dfs[worksheet_name] = df
                    else:
                        dfs[worksheet_name] = pd.DataFrame([add_new_record])
                    # Write all sheets back to the Excel file
                    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                        for sheet_name, df in dfs.items():
                            df.to_excel(writer, index=False, sheet_name=sheet_name)
                    st.success("Record saved successfully.")

            if selected_client_address and address:
                add_new_record = {
                    'Client' : selected_client_address,
                    'Address': address,
                }
                # Read existing data from the Excel file
                xl = pd.ExcelFile(file_path)
                # Load all sheets into a dictionary of DataFrames
                dfs = {sheet_name: xl.parse(sheet_name) for sheet_name in xl.sheet_names}
                # Check if the record already exists in any of the sheets
                record_exists = False
                for sheet_name, df in dfs.items():
                    if 'Client' in df.columns and 'Address' in df.columns:
                        if ((df['Client'] == selected_client_address) & (df['Address'] == address)).any():
                            record_exists = True
                            st.warning("Record Already Exist")
                # If the record doesn't exist, add it
                if not record_exists:
                    if worksheet_name in dfs:
                        df = dfs[worksheet_name]
                        df = pd.concat([df, pd.DataFrame([add_new_record])], ignore_index=True)
                        dfs[worksheet_name] = df
                    else:
                        dfs[worksheet_name] = pd.DataFrame([add_new_record])
                    # Write all sheets back to the Excel file
                    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                        for sheet_name, df in dfs.items():
                            df.to_excel(writer, index=False, sheet_name=sheet_name)
                    st.success("Record saved successfully.")

        else:
            st.warning("Record Already Exist")
except:
    pass

if display_record:
    st.dataframe(df)
