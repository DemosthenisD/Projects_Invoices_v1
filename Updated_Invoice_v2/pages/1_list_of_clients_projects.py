import streamlit as st
import pandas as pd
import os



st.sidebar.page_link('pages/0_generate_invoice_DD.py',     label="Generate Invoice",               icon="🏡")
st.sidebar.page_link('pages/1_list_of_clients_projects.py',label="List of Clients / Projects List",icon="📓")    
st.sidebar.page_link('pages/2_add_new_client_project.py',  label="Add New Client/Project record",  icon="✒️")  

#st.sidebar.page_link('pages/0_generate_invoice_DD.py',label="Generate Invoice")
#st.sidebar.page_link('pages/1_list_of_clients_projects.py',label="List of Clients / Projects List")    
#st.sidebar.page_link('pages/2_add_new_client_project.py',label="Add New Client/Project record")  


def load_dataframe(file_path, worksheet_name):
    try:
        df = pd.read_excel(file_path, sheet_name= worksheet_name)
        return df
    except FileNotFoundError:
        st.write(f"File {file_path} not found.")
        exit()

try:
    file_path = os.path.join(os.getcwd(), 'InvoiceLogTemplate_DD_28062024.xlsx')  # Full file path

    worksheet_name_1 = "InvoiceLogTemplate"
    df_1 = load_dataframe(file_path, worksheet_name_1)



    worksheet_client_list = "Client_List"
    df_client_list = load_dataframe(file_path, worksheet_client_list)


    worksheet_project_list = "Project_List"
    df_project_list = load_dataframe(file_path, worksheet_project_list)



    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        display_full_data = st.checkbox("Show DataFrame", value=True)
    with col2:    
        display_client_list = st.checkbox("Clients List")
    with col3:
        display_project_list = st.checkbox("Projects List")

    if display_full_data:
        st.dataframe(df_1)

    if display_client_list:
        st.dataframe(df_client_list)

    if display_project_list:
        st.dataframe(df_project_list)



except:
    pass
