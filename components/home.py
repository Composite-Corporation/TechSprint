import streamlit as st
from fuzzywuzzy import fuzz, process
from typing import List
from components.supplier import supplier_display, Supplier


# Function to perform fuzzy search on company names and return results with ids
def fuzzy_search(search: str, suppliers: List[Supplier], threshold: int = 70):
    company_names = [supplier.name for supplier in suppliers]
    results = process.extract(search, company_names, scorer=fuzz.token_set_ratio)
    
    # Filter results based on the threshold and get the corresponding company objects
    matches = [supplier for supplier, score in zip(suppliers, [result[1] for result in results]) if score >= threshold]
    return matches


def home_page():
    # Get suppliers data from session state
    suppliers_data = st.session_state["suppliers_data"]

    # Sidebar with more options
    with st.sidebar:
        # Display CompositeAI logo
        st.image("static/composite.png", output_format="PNG", width=300)

        # Filtering UI
        st.title(body="**Filtering**")
        filter_rating = st.selectbox(
            label="ESG Rating", 
            options=["All", "High", "Medium", "Low"],
        )
        search = st.text_input(label="Search Supplier Name")

        # Filtering logic
        if filter_rating == "All":
            filtered_suppliers = suppliers_data
        else:
            filtered_suppliers = [supplier for supplier in suppliers_data if supplier.esg.segment == filter_rating]
        if search:
            filtered_suppliers = fuzzy_search(search=search, suppliers=filtered_suppliers)

        # Add supplier button
        st.title(body="**Supplier Data**")
        if st.button(label="Add Supplier", use_container_width=True):
            pass

    # Main portion of the page
    st.header("ESG Supplier Management System", anchor=False)
    for supplier in filtered_suppliers:
        supplier_display(supplier=supplier)
    if not filtered_suppliers:
        st.warning("No suppliers found.", icon="⚠️")