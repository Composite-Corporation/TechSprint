import uuid
import time
import streamlit as st
from pydantic import BaseModel
from typing import List
from datetime import date
from components.chat import Chat, chat_bubble


class Source(BaseModel):
    key_quote: str
    link: str


class DataSummary(BaseModel):
    available: bool
    summary: str
    sources: List[Source]


class ESGData(BaseModel):
    scope_1: DataSummary
    scope_2: DataSummary
    scope_3: DataSummary
    ecovadis: DataSummary
    iso_14001: DataSummary
    product_lca: DataSummary
    segment: str
    updated: date


class Supplier(BaseModel):
    id: str
    name: str
    website: str
    description: str
    esg: ESGData


@st.dialog("Delete Supplier?")
def delete_dialog(supplier: Supplier):
    st.write(f"{supplier.name} and all its data will be removed.")
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        if st.button(label="Confirm", type="primary"):
            supplier_id = supplier.id
            num_suppliers = len(st.session_state["suppliers_data"])
            for i in range(num_suppliers):
                if supplier_id == st.session_state["suppliers_data"][i].id:
                    st.session_state["suppliers_data"].pop(i)
                    break
            st.rerun()
    with col2:
        if st.button(label="Cancel"):
            st.rerun()


def supplier_display(supplier: Supplier):
    # Set up supplier card
    container = st.container(border=True)

    # Set up subheader and buttons
    col1, col2, col3 = container.columns([0.6, 0.18, 0.23])
    with col1:    
        st.subheader(body=supplier.name, anchor=False)
    with col2:
        # Button to change to supplier details page
        if st.button(key=f"{supplier.id}_details", label="View Details"):
            st.session_state["page"] = {"name": "Supplier Details", "data": {"supplier": supplier}}
            st.rerun()
    with col3:
        # Button to delete supplier from database
        if st.button(key=f"{supplier.id}_delete", label="Delete Supplier", type="primary"):
            delete_dialog(supplier=supplier)

    # Display supplier info on card
    if supplier.esg.segment == "High":
        color = "green"
    elif supplier.esg.segment == "Medium":
        color = "orange"
    elif supplier.esg.segment == "Low":
        color = "red"
    container.write(f"**Website**: {supplier.website}")
    container.write(f"**Description**: {supplier.description}")
    container.write(f"**ESG Segment**: :{color}[{supplier.esg.segment}]")


def supplier_esg_expander(property: str, data_summary: DataSummary):
    available = data_summary.available
    emoji = "✅" if available else "❌"
    label = f"{emoji} {property}"
    expander = st.expander(label=label, expanded=False)
    expander.write(data_summary.summary)

    if available:
        for source in data_summary.sources:
            expander.markdown(f"""              
            Key Quote: "{source.key_quote}"\n
            Source Link: {source.link}
            """)


def supplier_details():
    # Retrieve supplier data class and display name as title
    supplier = st.session_state["page"]["data"]["supplier"]
    st.title(body=supplier.name, anchor=False)

    # Setup sidebar chat
    with st.sidebar:
        st.title("**ESG Assisstant**")
        with st.container(height=550, border=False):
            chat_bubble(
                chat=Chat(
                    name="assisstant", 
                    content=f"Hi! I can help you any additional questiont you might have about {supplier.name}.",
                ),
            )
        if user_input := st.chat_input(placeholder="Ask any question here"):
            pass

    # Supplier details edit form
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.subheader(body="Supplier Details")
    with col2:
        if st.button("Return to Home"):
            st.session_state["page"] = {"name": "Home", "data": None}
            st.rerun()
    new_name = st.text_input("Name", supplier.name)
    new_website = st.text_input("Website", supplier.website)
    new_description = st.text_input("Description", supplier.description)
    if st.button("Save Changes"):
        supplier.name = new_name
        supplier.website = new_website
        supplier.description = new_description
        st.success(f"Supplier details updated!")
        time.sleep(2)
        st.rerun()

    st.divider()

    # ESG information section
    st.subheader(body="ESG Data")
    if supplier.esg.segment == "High":
        color = "green"
    elif supplier.esg.segment == "Medium":
        color = "orange"
    elif supplier.esg.segment == "Low":
        color = "red"
    st.write(f"**Overall Segment**: :{color}[{supplier.esg.segment}]")
    update_date = supplier.esg.updated.strftime(format="%d/%m/%Y, %H:%M:%S")
    st.write(f"**Last Updated**: {update_date}")
    supplier_esg_expander(property="Scope 1 Emissions", data_summary=supplier.esg.scope_1)
    supplier_esg_expander(property="Scope 2 Emissions", data_summary=supplier.esg.scope_2)
    supplier_esg_expander(property="Scope 3 Emissions", data_summary=supplier.esg.scope_3)
    supplier_esg_expander(property="Ecovadis Score", data_summary=supplier.esg.ecovadis)
    supplier_esg_expander(property="ISO 14001 Compliance", data_summary=supplier.esg.iso_14001)
    supplier_esg_expander(property="Life Cycle Assessments (LCA)", data_summary=supplier.esg.product_lca)
    if st.button("Automatic Update"):
        st.success(f"Supplier ESG data updated!")


# Initial supplier data
suppliers_data = [
    Supplier(
        id=str(uuid.uuid4()),
        name="Honeywell",
        website="https://www.honeywell.com/us/en",
        description="Something supplier of something.",
        esg=ESGData(
            scope_1=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            scope_2=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            scope_3=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            ecovadis=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            iso_14001=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            product_lca=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            segment="High",
            updated=date.today(),
        )
    ),
    Supplier(
        id=str(uuid.uuid4()),
        name="3M",
        website="https://www.3m.com/",
        description="Something supplier of something.",
        esg=ESGData(
            scope_1=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            scope_2=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            scope_3=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            ecovadis=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            iso_14001=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            product_lca=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            segment="High",
            updated=date.today(),
        )
    ),
    Supplier(
        id=str(uuid.uuid4()),
        name="Azenta Life Sciences",
        website="https://www.azenta.com/",
        description="Something supplier of something.",
        esg=ESGData(
            scope_1=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            scope_2=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            scope_3=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            ecovadis=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            iso_14001=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            product_lca=DataSummary(
                available=True,
                summary="Testing testing testing.",
                sources=[
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                    Source(key_quote="Testing testing.", link="https://www.composite-corp.com/"),
                ]
            ),
            segment="High",
            updated=date.today(),
        )
    )
]