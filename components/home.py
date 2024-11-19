import time
import uuid
import streamlit as st
from datetime import datetime
import pytz
from fuzzywuzzy import fuzz, process
from typing import List
from components.chat import chat_suppliers
from components.supplier import (
    supplier_display, 
    supplier_obtain_esg_data, 
)
from utils.db import db
from utils.supplier_data import (
    Supplier, 
    ESGData,
    DataSummary,
    AgentSupplier,
)
import pandas as pd
from io import BytesIO


# Function to perform fuzzy search on company names and return results with ids
def fuzzy_search(search: str, suppliers: List[Supplier], threshold: int = 70):
    # Return search score of companies sorted alphabetically
    supplier_names = [supplier.name for supplier in suppliers]
    results = process.extract(search, supplier_names, scorer=fuzz.token_set_ratio)
    results = sorted(results, key=lambda pair: pair[0])

    # Match results to dataset
    num_suppliers = len(suppliers)
    matches = []
    for i in range(num_suppliers):
        score = results[i][1]
        supplier = suppliers[i]
        if score >= threshold:
            matches.append(supplier)
    return matches


@st.dialog(title="Processing New Supplier...", width="large")
def processing_dialog(name: str, website: str = None, description: str = None, notes: str = None):
    task_prefix = f"""
    Given the following info about a company:
        Name - {name}
        Website - {website}
        Description - {description}
        Notes - {notes}
    """
    esg_score = 0

    task_basic_info = task_prefix + """
    \nUse the web to find a URL to the company's website and come up with your best description on what this company does.
    """
    data_basic_info = supplier_obtain_esg_data(label="Basic Information", task=task_basic_info, response_format=AgentSupplier)

    task_scope_1 = task_prefix + """
    \nPlease find any data on THEIR OWN scope 1 emissions calculations.
    Scope 1 emissions are direct emissions from sources owned or controlled by a company.
    These include things like: on-site energy, fleet vehicles, process emissions, or accidental emissions.
    ONLY INCLUDE EXPLICIT MENTIONS OF "SCOPE 1" DATA.
    """
    data_scope_1 = supplier_obtain_esg_data(label="Scope 1 Emissions", task=task_scope_1, response_format=DataSummary)
    esg_score += 1 if data_scope_1.available else 0

    task_scope_2 = task_prefix + f"""
    Please find any data on THEIR OWN scope 2 emissions calculations.
    Scope 2 emissions are indirect greenhouse gas (GHG) emissions that result from the generation of energy that an organization purchases and uses.
    These include things like the purchase of electricity from: steam, heat, cooling, etc.
    ONLY INCLUDE EXPLICIT MENTIONS OF "SCOPE 2" DATA.
    """
    data_scope_2 = supplier_obtain_esg_data(label="Scope 2 Emissions", task=task_scope_2, response_format=DataSummary)
    esg_score += 1 if data_scope_2.available else 0

    task_scope_3 = task_prefix + """
    Please find any data on THEIR OWN scope 3 emissions calculations.
    Scope 3 emissions are greenhouse gas (GHG) emissions that are a result of activities that a company indirectly affects as part of its value chain, but that are not owned or controlled by the company.
    These include things like: supply chain emissions, use of sold products, waste disposal, employee travel, contracted waste disposal, etc.
    ONLY INCLUDE EXPLICIT MENTIONS OF "SCOPE 3" DATA.
    """
    data_scope_3 = supplier_obtain_esg_data(label="Scope 3 Emissions", task=task_scope_3, response_format=DataSummary)
    esg_score += 1 if data_scope_3.available else 0

    task_ecovadis = task_prefix + "\nPlease find if this company has a publicly available Ecovadis score."
    data_ecovadis = supplier_obtain_esg_data(label="Ecovadis Score", task=task_ecovadis, response_format=DataSummary)
    esg_score += 1 if data_ecovadis.available else 0

    task_reduction_targets = task_prefix + "\nPlease find if this company has set any carbon emissions reduction targets."
    data_reduction_targets = supplier_obtain_esg_data(label="Reduction Targets", task=task_reduction_targets, response_format=DataSummary)
    esg_score += 1 if data_reduction_targets.available else 0

    task_iso_14001 = task_prefix + "\nPlease find if this company has an ISO 14001 certification."
    data_iso_14001 = supplier_obtain_esg_data(label="ISO 14001 Certification", task=task_iso_14001, response_format=DataSummary)
    esg_score += 1 if data_iso_14001.available else 0

    task_product_lca = task_prefix + "\nPlease find if this company has any products undergoing a Life Cycle Assessment, or LCA."
    data_product_lca = supplier_obtain_esg_data(label="Product LCAs", task=task_product_lca, response_format=DataSummary)
    esg_score += 1 if data_product_lca.available else 0

    if esg_score <= 2:
        segment = "Low"
    elif esg_score <= 5:
        segment = "Medium"
    else:
        segment = "High"
    processed_supplier = Supplier(
        id=str(uuid.uuid4()),
        name=data_basic_info.name,
        website=data_basic_info.website,
        description=data_basic_info.description,
        esg=ESGData(
            scope_1=data_scope_1,
            scope_2=data_scope_2,
            scope_3=data_scope_3,
            ecovadis=data_ecovadis,
            reduction_targets=data_reduction_targets,
            iso_14001=data_iso_14001,
            product_lca=data_product_lca,
            segment=segment,
            updated=datetime.now(pytz.timezone('Europe/London')),
        )
    )
    org_id = st.session_state["page"]["data"]["session_data"]["org_id"]
    db.insert_supplier(supplier=processed_supplier, org_id=org_id)
    st.session_state["page"] = {
        "name": "Supplier Details", 
        "data": {
            "supplier": processed_supplier,
            "session_data": st.session_state["page"]["data"]["session_data"],
        },
    }
    st.success(body=f"Successfully added {name} as a supplier!")
    time.sleep(2)
    st.rerun()


@st.dialog(title="Add New Supplier", width="large")
def add_dialog():
    tab1, tab2, tab3 = st.tabs(["Individual Upload", "Bulk Upload", "View Upload Tasks"])
    with tab1:
        with st.form(key="supplier_form", border=False):
            # Input fields for the supplier details
            name = st.text_input(label="Company Name:red[*]", help="Required field.")
            website = st.text_input(label="Website", help="If empty, will be auto-populated using AI.")
            description = st.text_area(label="Description", help="If empty, will be auto-populated using AI.")
            notes = st.text_area(label="Notes")
            
            # Submit button
            submit = st.form_submit_button("Confirm")

            # Submit logic
            if submit:
                if name:
                    st.session_state["page"]["data"]["processing_supplier"] = True
                    st.session_state["page"]["data"]["add_supplier"] = {
                        "name": name,
                        "website": website,
                        "description": description,
                        "notes": notes,
                    }
                    st.rerun()
                else:
                    st.error("Please provide the supplier name.")
    with tab2:
        uploaded_file = st.file_uploader(
            label="Choose CSV or Excel File", 
            accept_multiple_files=False,
            type=['csv', 'xlsx'],
        )
        if uploaded_file:
            with st.spinner("Processing..."):
                try:
                    # Determine file type and read accordingly
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:  # Excel file
                        df = pd.read_excel(uploaded_file)
                    
                    # Check if "Supplier Names" column exists
                    supplier_column = next((col for col in df.columns if col.lower() == "supplier names"), None)
                    if not supplier_column:
                        raise Exception("No \"Supplier Names\" column")
                        
                    # Check user_id and org_id from session data
                    session_data = st.session_state["page"]["data"]["session_data"]
                    user_id = session_data.get("localId")
                    org_id = session_data.get("org_id")
                    if not user_id or not org_id:
                        raise Exception("Missing user or organization information")
                    
                    # Get supplier names from upload and database, find duplicates
                    supplier_names_uploaded = df[supplier_column].dropna().tolist()
                    supplier_names_uploaded_lower = {supplier_name.lower() for supplier_name in supplier_names_uploaded}
                    suppliers_db = db.get_org_suppliers(org_id=org_id)
                    supplier_names_db_lower = {supplier.name.lower() for supplier in suppliers_db}
                    duplicates = supplier_names_uploaded_lower.intersection(supplier_names_db_lower)
                except Exception as e:
                    st.error(f"An error occurred while processing the file: {str(e)}")

            # Once processing is finished
            if duplicates:
                st.warning("The following companies already exist in the database:")
                with st.expander("Duplicates"):
                    for item in duplicates:
                        st.markdown(f":orange[{item}]")
                but1, but2 = st.columns([1, 1])
                with but1:
                    if st.button("Upload All", use_container_width=True):
                        task_id = db.create_task(user_id, org_id, list(supplier_names_uploaded))
                        st.success(f"Successfully extracted {len(supplier_names_uploaded)} supplier names and created task with ID: {task_id}")
                        time.sleep(2)
                        st.rerun()
                with but2:
                    if st.button("Upload Non-duplicates", use_container_width=True):
                        # Subtract duplicates from uploaded supplier names
                        supplier_names_uploaded_lower -= duplicates  # Remove duplicates from the set
                        task_id = db.create_task(user_id, org_id, list(supplier_names_uploaded_lower))
                        st.success(f"Successfully extracted {len(supplier_names_uploaded_lower)} supplier names and created task with ID: {task_id}")
                        time.sleep(2)
                        st.rerun()
            else:
                task_id = db.create_task(user_id, org_id, list(supplier_names_uploaded))
                st.success(f"Successfully extracted {len(supplier_names_uploaded)} supplier names and created task with ID: {task_id}")
                time.sleep(2)
                st.rerun()
        else:
            st.info("Please ensure your spreadsheet has a column named 'Supplier Names'.")
    with tab3:
        # Get org_id from session data
        org_id = st.session_state["page"]["data"]["session_data"]["org_id"]
        
        # Fetch tasks for the organization
        tasks = db.get_tasks_by_org(org_id)
        
        if not tasks:
            st.info("No upload tasks found for this organization.")
        else:
            for task in tasks:
                with st.expander(f"Task ID: :blue[{task['id']}] - {task['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    total_companies = len(task['companies'])
                    processed_companies = sum(1 for company in task['companies'] if company['status'] == 'success')
                    error_companies = sum(1 for company in task['companies'] if company['status'] == 'error')
                    
                    # Calculate progress percentage
                    progress_percentage = (processed_companies / total_companies) * 100 if total_companies > 0 else 0
                    
                    # Display progress bar
                    st.progress(progress_percentage / 100, text=f"Progress: {progress_percentage:.1f}%")
                    
                    # Display company details
                    st.write(f"Total Companies: {total_companies}")
                    st.write(f"Processed: {processed_companies}")
                    st.write(f"Errors: {error_companies}")
                    st.write(f"Remaining: {total_companies - processed_companies - error_companies}")
                    
                    # Display company list
                    if st.checkbox(f"Show Companies", key=f"show_companies_{task['id']}"):
                        for company in task['companies']:
                            status_color = {
                                'success': 'green',
                                'error': 'red',
                                'unprocessed': 'orange'
                            }.get(company['status'], 'gray')
                            st.markdown(f"- {company['name']}: <font color='{status_color}'>{company['status']}</font>", unsafe_allow_html=True)


def home_page():
    # Get org id from session state
    org_id = st.session_state["page"]["data"]["session_data"]["org_id"]

    # Get suppliers data from session state
    suppliers_data = db.get_org_suppliers(org_id=org_id)
    suppliers_data = sorted(suppliers_data, key=lambda supplier: supplier.name)

    # Check if in the middle of processing supplier
    if st.session_state["page"]["data"]["processing_supplier"]:
        add_supplier = st.session_state["page"]["data"]["add_supplier"]
        processing_dialog(
            name=add_supplier["name"], 
            website=add_supplier["website"], 
            description=add_supplier["description"],
            notes=add_supplier["notes"],
        )

    # Chat assistant sidebar
    chat_suppliers()

    # Title of page
    st.header("ESG Supplier Management System", anchor=False)
    
    # Create a container for buttons to display them side by side
    col1, col2 = st.columns(2)
    with col1:
        # Button to input new supplier info
        if st.button(label="Add New Supplier", use_container_width=True):
            add_dialog()
    with col2:
        # Button to download supplier info
        if st.button(label="Download Supplier Info", use_container_width=True):
            org_id = st.session_state["page"]["data"]["session_data"]["org_id"]
            suppliers = db.get_org_suppliers(org_id=org_id)
            suppliers_info = [(supplier.name, supplier.website, supplier.description, supplier.notes, supplier.esg.segment, supplier.esg) for supplier in suppliers]
            df = pd.DataFrame(suppliers_info, columns=["Supplier Names", "Website", "Description", "Notes", "ESG Rating", "ESG Data"])
            
            # Use BytesIO to create an in-memory buffer for the Excel file
            excel_file = BytesIO()
            df.to_excel(excel_file, index=False, engine='openpyxl')
            excel_file.seek(0)  # Move to the beginning of the BytesIO buffer
            
            # Ensure the download button uses the correct data type
            st.download_button(
                label="Download Excel",
                data=excel_file.getvalue(),  # Get the value of the BytesIO buffer
                file_name="supplier_info.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # Filtering UI
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        filter_rating = st.selectbox(
            label="Filter by ESG Rating", 
            options=["All", "High", "Medium", "Low"],
        )
    with col2:
        search = st.text_input(label="Filter by Supplier Name").strip()
    
    # Filtering logic
    if filter_rating == "All":
        filtered_suppliers = suppliers_data
    else:
        filtered_suppliers = [supplier for supplier in suppliers_data if supplier.esg.segment == filter_rating]
    if search:
        filtered_suppliers = fuzzy_search(search=search, suppliers=filtered_suppliers)

    # Display all suppliers
    for supplier in filtered_suppliers:
        supplier_display(supplier=supplier)
    if not filtered_suppliers:
        st.warning("No suppliers found.", icon="⚠️")
