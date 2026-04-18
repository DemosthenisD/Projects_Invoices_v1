import streamlit as st
import pandas as pd
from docx import Document
import time
import base64
import os
from base64 import b64encode
from streamlit_extras.switch_page_button import switch_page
import convertapi
from streamlit_free_text_select import st_free_text_select

# Sidebar navigation
st.sidebar.page_link('pages/0_generate_invoice_DD.py',     label="Generate Invoice",               icon="🏡")
st.sidebar.page_link('pages/1_list_of_clients_projects.py',label="List of Clients / Projects List",icon="📓")    
st.sidebar.page_link('pages/2_add_new_client_project.py',  label="Add New Client/Project record",  icon="✒️")  

#st.sidebar.page_link('pages/0_generate_invoice_DD.py',     label="Generate Invoice")
#st.sidebar.page_link('pages/1_list_of_clients_projects.py',label="List of Clients / Projects List")    
#st.sidebar.page_link('pages/2_add_new_client_project.py',  label="Add New Client/Project record")  

# if st.sidebar.button("Generate Invoice", icon=":house:"): --> previous code (up to 3-11-2024). 
# Next row is the updated code of row above, removed icon
#if st.sidebar.button("Generate Invoice", icon=":house:"):

#if st.sidebar.button("Generate Invoice"):
    #switch_page("0_generate_invoice_DD")
#    switch_page("0_generate_invoice_DD")

#if st.sidebar.button("List of Clients / Projects List", icon="📓"):
#if st.sidebar.button("List of Clients / Projects List", icon=":notebook:"):

#if st.sidebar.button("List of Clients / Projects List"):
#    switch_page("1_list_of_clients_projects")

#if st.sidebar.button("Add New Client/Project record", icon="✒️"):
#if st.sidebar.button("Add New Client/Project record", icon=":black_nib:"):

#if st.sidebar.button("Add New Client/Project record"):
#    switch_page("2_add_new_client_project")

# Initialize invoices in session state
if 'invoices' not in st.session_state:
    st.session_state.invoices = []

# Set your ConvertAPI secret key
convertapi.api_secret = 'WNkNerQr6LJX6JUw'  # Replace with your actual API key

# Custom CSS for the success message and animation
st.markdown("""
    <style>
    .hidden {
        display: none;
    }
    .success-message {
        font-size: 1.5rem;
        color: green;
        opacity: 0;
        transition: opacity 1s ease-in-out;
    }
    .success-message.show {
        opacity: 1;
    }
    </style>
    """, unsafe_allow_html=True)

# JavaScript to show the success message
st.markdown("""
    <script>
    function showSuccessMessage() {
        var successMessage = document.getElementById("successMessage");
        successMessage.classList.add("show");
    }
    </script>
    """, unsafe_allow_html=True)


def fill_placeholders(doc, data):
    for p in doc.paragraphs:
        for key, value in data.items():
            if key in p.text:
                inline = p.runs
                for i in range(len(inline)):
                    if key in inline[i].text:
                        text = inline[i].text.replace(key, str(value))
                        inline[i].text = text

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for key, value in data.items():
                        if key in p.text:
                            inline = p.runs
                            for i in range(len(inline)):
                                if key in inline[i].text:
                                    text = inline[i].text.replace(key, str(value))
                                    inline[i].text = text

def load_dataframe(file_path, worksheet_name):
    try:
        df = pd.read_excel(file_path, sheet_name=worksheet_name)
        return df
    except FileNotFoundError:
        st.write(f"File {file_path} not found.")
        st.stop()

def download_link_pdf(file_path, text, label):
    with open(file_path, 'rb') as f:
        data = f.read()
    href = f'<a href="data:application/octet-stream;base64,{b64encode(data).decode()}" download="{file_path}">{label}</a>'
    return href

def download_link_docx(doc, year, invoice_no, client, filename, text):
    root_dir = os.getcwd()  # Get the current working directory (root directory)
    save_file_name = f"{year}/{invoice_no} {client} Invoice"
    doc.save(os.path.join(root_dir , filename))  # Save the docx file to the root directory
    with open(os.path.join(root_dir, filename), 'rb') as f:
        doc_bytes = f.read()
    href = f'<a href="data:application/octet-stream;base64,{base64.b64encode(doc_bytes).decode()}" download="{save_file_name}.docx">{text}</a>'
    return href

def convert_docx_to_pdf(file_path):
    result = convertapi.convert('pdf', {
        'File': file_path
    }, from_format='docx')
    pdf_file_path = 'converted.pdf'
    result.save_files(pdf_file_path)
    with open(pdf_file_path, 'rb') as f:
        pdf_file = f.read()
    os.remove(pdf_file_path)
    return pdf_file

def remove_document_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

def convert_to_number(input_text):
    """
    Converts the input text to a number (int or float). Returns None if invalid.
    """
    if not input_text:  # Handle empty or None input
        return None
    try:
        # Attempt to convert to float (handles integers as well)
        number = float(input_text)
        return number
    except ValueError:
        return None  # Return None if conversion fails


#def convert_to_number(input_text):
#    try:
#        number = int(input_text)
#        return number
#    except ValueError:
#        try:
#            number = float(input_text)
#            return number
#        except ValueError:
#            return None

def main():
    if 'username' in st.session_state:
        file_path = os.path.join(os.getcwd(), 'InvoiceLogTemplate_DD_28062024.xlsx')
        worksheet_project_list = "Project_List"
        df_project_list = load_dataframe(file_path, worksheet_project_list)
        worksheet_client_list = "Client_List"
        df_client_list = load_dataframe(file_path, worksheet_client_list)
        clients = df_project_list['Client'].unique()
        df_Invoice_List = load_dataframe(file_path, "InvoiceLogTemplate")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            client = st.selectbox("Select Client", clients)
            Client_Name_For_Invoice = df_project_list[df_project_list['Client'] == client]['Client Name (for Invoices)'].unique()
        with col2:
            filtered_address = df_client_list[df_client_list['Client'] == client]['Address'].unique()
            address = st_free_text_select(label="Address", options=filtered_address, format_func=lambda x: x.lower(), placeholder="Select or Type Address", disabled=False, delay=300,)
        with col3:
            vat_number = "0.19" 
            #df_project_list[df_project_list['Client'] == client]['VAT_No'].unique()
            vat_no = st_free_text_select(label="VAT No", options=vat_number, placeholder="Select or Type VAT Number", disabled=False, delay=300,)

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            date = st.date_input("Date")
            year = date.year
        with col3:
            amount = st.number_input("Amount", step=1)
        with col1:
            Pre_invoice_no = len(df_Invoice_List[df_Invoice_List['Year'] == year]) + 1
            invoice_no = st.text_input(label="invoice No", value=Pre_invoice_no)

        filtered_vat = df_project_list[df_project_list['Client'] == client]['VAT %'].unique()
        vat = st_free_text_select(label="VAT %", options=str(filtered_vat), placeholder="Select or Type VAT %-age", disabled=False, delay=300,)
        #vat = st.text_input("VAT %", placeholder="Enter VAT percentage")
        #if not vat.isdigit():
        #    st.error("Please enter a valid numeric VAT percentage.")
        #else:
        #    vat_number = float(vat)
        #    VAT_Amount = (amount * vat_number) / 100
        #    st.write(f"VAT Amount: {VAT_Amount}")

        # Convert VAT input to a number
        vat_number = convert_to_number(vat)

        if vat_number is None:
            st.error("Invalid VAT value. Please enter a valid number.")
        else:
            # Calculate VAT amount (ensure 'amount' is valid too)
            VAT_Amount = (amount * vat_number) / 100
            st.write(f"VAT Amount: {VAT_Amount}")

        filtered_client_code = df_project_list[df_project_list['Client'] == client]['client_code'].unique()
        filtered_projects = df_project_list[df_project_list['Client'] == client]['Project'].unique()
        project = st_free_text_select(label="Select Project", options=filtered_projects, format_func=lambda x: x.lower(), placeholder="Select or Enter a project", disabled=False, delay=300,)

        filtered_description = df_project_list[df_project_list['Client'] == client]['description'].unique()
        description = st_free_text_select(label="Description", options=filtered_description, format_func=lambda x: x.lower(), placeholder="Select or Enter a description", disabled=False, delay=300,)

        with st.expander("Select Invoice Template and Format"):
            col1, col2 = st.columns([1, 1])
            with col1:
                Filtered_Invoice_Template = df_project_list[df_project_list['Client'] == client]['Invoice Template'].unique()
                options_for_templates = df_project_list['Invoice Template'].unique()
                index_Selected = list(options_for_templates).index(Filtered_Invoice_Template[0])
                invoice_template = st.radio("Select Template for Invoice", options_for_templates, index=index_Selected, key="invoice_template")
            with col2:
                format_option = st.radio("Select download format", ["DOCX", "PDF"], key="format_option")

        VAT_Amount = (amount * convert_to_number(vat)) / 100
        Expenses_Net_Amount = 0
        Expenses_VAT_Amount = 0

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            generate_invoice = st.button('Generate Invoice', key="generate")
        with col2:
            save_record_button = st.button("Save Record", key="save_record")

        if save_record_button:
            add_new_record = {
                'Year': year,
                'Invoice No': invoice_no,
                'Date': date,
                'Client': client,
                'Client Name (for Invoices)': Client_Name_For_Invoice[0],
                'Address': address,
                'VAT_No': vat_no,
                'Amount': amount,
                'VAT %': vat,
                'Project': project,
                'description': description,
                'Invoice Template': invoice_template,
                'VAT Amount': VAT_Amount,
                'Expenses Net Amount': Expenses_Net_Amount,
                'Expenses VAT Amount': Expenses_VAT_Amount,
                'client_code': filtered_client_code[0],
                'Converted': 'YES',
                'Invoice Record Updated': 'YES'
            }
            df_Invoice_List = df_Invoice_List.append(add_new_record, ignore_index=True)
            df_Invoice_List.to_excel(file_path, sheet_name="InvoiceLogTemplate", index=False)
            st.success("Record saved successfully.")

        if generate_invoice:
            if None in [invoice_no, amount, date]:
                st.error("Please fill all required fields.")
            else:
                st.session_state.invoices.append({
                    'client': client,
                    'invoice_no': invoice_no,
                    'date': date,
                    'amount': amount,
                    'vat': vat,
                    'project': project,
                    'description': description
                })

                st.markdown('<div id="successMessage" class="success-message hidden">Generating Invoice...</div>', unsafe_allow_html=True)
                st.markdown('<script>showSuccessMessage();</script>', unsafe_allow_html=True)
                time.sleep(1)  # Simulate some processing time
                st.markdown('<script>document.getElementById("successMessage").classList.remove("hidden");</script>', unsafe_allow_html=True)

                template_path = f"./{invoice_template}.docx"
                if os.path.exists(template_path):
                    doc = Document(template_path)
                    fill_placeholders(doc, {
                        "Client_Name_For_Invoice": Client_Name_For_Invoice[0],
                        "Date": date,
                        "Invoice No": invoice_no,
                        "Address": address,
                        "VAT_No": vat_no,
                        "Amount": amount,
                        "VAT": vat,
                        "VAT_Amount": VAT_Amount,
                        "Project": project,
                        "description": description
                    })
                    file_path = f"{invoice_no}_{client}_Invoice.docx"
                    doc.save(file_path)
                    st.markdown(download_link_docx(doc, year, invoice_no, client, file_path, 'Download Invoice'), unsafe_allow_html=True)
                    remove_document_file(file_path)
                else:
                    st.error(f"Template {invoice_template} not found.")

                if format_option == "PDF":
                    st.markdown(download_link_pdf(file_path, 'Download Invoice as PDF', 'Download PDF'), unsafe_allow_html=True)
                    pdf_file = convert_docx_to_pdf(file_path)
                    st.download_button(label='Download Invoice as PDF', data=pdf_file, file_name='invoice.pdf', mime='application/pdf')
                    remove_document_file(file_path)

if __name__ == "__main__":
    main()
