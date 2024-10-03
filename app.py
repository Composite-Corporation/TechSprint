import streamlit as st
from components import (
    home_page,
    supplier_details,
    suppliers_data,
)


# Set up page session state
if "page" not in st.session_state:
    st.session_state["page"] = {
        "name": "Home",
        "data": None,
    }
if "suppliers_data" not in st.session_state:
    st.session_state["suppliers_data"] = suppliers_data


# Main app function
if __name__=="__main__":
    st.set_page_config(page_title="Composite.ai", page_icon="♻️")

    if st.session_state["page"]["name"] == "Home":
        home_page()
    elif st.session_state["page"]["name"] == "Supplier Details":
        supplier_details()