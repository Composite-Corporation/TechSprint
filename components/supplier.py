import uuid
import time
import streamlit as st
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from agent import Agent
from compositeai.tools import GoogleSerperApiTool, WebScrapeTool
from compositeai.drivers import OpenAIDriver
from compositeai.agents import AgentResult


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
    website: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    esg: ESGData


class AgentSupplier(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None


# HELPER COMPONENT
# Runs structured output agent to process a task and display expander of results
# e.g. "Find scope 1 emissions for company"
def supplier_obtain_esg_data(label: str, task: str):
    agent = Agent(
        driver=OpenAIDriver(
            model="gpt-4o-mini", 
            seed=1337,
        ),
        description=f"""
        You are an analyst searches the web for a company's sustainability and ESG information.

        Use the Google search tool to find relevant data sources and links.
        Then, use the Web scraping tool to analyze the content of links of interest.
        """,
        tools=[
            WebScrapeTool(),
            GoogleSerperApiTool(),
        ],
        max_iterations=20,
    )
    with st.status(f"Finding {label}...") as status:
        for chunk in agent.execute(task, stream=True):
            if isinstance(chunk, AgentResult):
                agent_result = chunk.content
                status.update(label=f"Completed Search on {label}.", state="complete", expanded=False)
            else:
                with st.container(border=True):
                    st.markdown(chunk.content)
        return agent_result


# HELPER COMPONENT
# Used exclusively by supplier_display component to display dialog form for deleting a supplier
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


# HELPER COMPONENT
# Card to display supplier information and buttons to view details/delete
def supplier_display(supplier: Supplier):
    # Set up supplier card
    container = st.container(border=True)

    # Set up subheader and buttons
    col1, col2, col3 = container.columns([0.6, 0.18, 0.23])
    with col1:    
        st.subheader(body=f"**{supplier.name}**", anchor=False)
    with col2:
        # Button to change to supplier details page
        if st.button(key=f"{supplier.id}_details", label="View Details"):
            # Update page state and rerun
            st.session_state["page"] = {
                "name": "Supplier Details", 
                "data": {
                    "supplier": supplier,
                },
            }
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


# HELPER COMPONENT
# Expander to display summary if one piece of ESG data
# e.g. Scope 1 emissions for a company
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


# HELPER COMPONENT
# Used exclusively by supplier_details page to display dialog of updating ESG info
@st.dialog("Updating ESG Data...")
def delete_dialog(supplier: Supplier):
    task_prefix = f"""
    Given the following info about a company:
        Name - {supplier.name}
        Website - {supplier.website}
        Description - {supplier.description}
        Notes - {supplier.notes}
    """
    esg_score = 0

    task_scope_1 = task_prefix + "\nPlease any data on THEIR OWN scope 1 emissions calculations."
    data_scope_1 = supplier_obtain_esg_data(label="Scope 1 Emissions", task=task_scope_1)
    esg_score += 1 if data_scope_1.available else 0

    task_scope_2 = task_prefix + "\nPlease any data on THEIR OWN scope 2 emissions calculations."
    data_scope_2 = supplier_obtain_esg_data(label="Scope 2 Emissions", task=task_scope_2)
    esg_score += 1 if data_scope_2.available else 0

    task_scope_3 = task_prefix + "\nPlease any data on THEIR OWN scope 3 emissions calculations."
    data_scope_3 = supplier_obtain_esg_data(label="Scope 3 Emissions", task=task_scope_3)
    esg_score += 1 if data_scope_3.available else 0

    task_ecovadis = task_prefix + "\nPlease find if this company has a publicly available Ecovadis score."
    data_ecovadis = supplier_obtain_esg_data(label="Ecovadis Score", task=task_ecovadis)
    esg_score += 1 if data_ecovadis.available else 0

    task_iso_14001 = task_prefix + "\nPlease find if this company has an ISO 14001 certification."
    data_iso_14001 = supplier_obtain_esg_data(label="ISO 14001 Certification", task=task_iso_14001)
    esg_score += 1 if data_iso_14001.available else 0

    task_product_lca = task_prefix + "\nPlease find if this company has any products undergoing a Life Cycle Assessment, or LCA."
    data_product_lca = supplier_obtain_esg_data(label="Product LCAs", task=task_product_lca)
    esg_score += 1 if data_product_lca.available else 0

    if esg_score <= 2:
        segment = "Low"
    elif esg_score <= 4:
        segment = "Medium"
    else:
        segment = "High"
    supplier.esg.scope_1 = data_scope_1
    supplier.esg.scope_2 = data_scope_2
    supplier.esg.scope_3 = data_scope_3
    supplier.esg.ecovadis = data_ecovadis
    supplier.esg.iso_14001 = data_iso_14001
    supplier.esg.product_lca = data_product_lca
    supplier.esg.segment = segment
    supplier.esg.updated = date.today()
    time.sleep(2)
    st.rerun()


# PAGE
# Display supplier data and editing forms
def supplier_details():
    # Retrieve supplier data class and display name as title
    supplier = st.session_state["page"]["data"]["supplier"]
    st.title(body=f"**{supplier.name}**", anchor=False)

    # Supplier details edit form
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.subheader(body="Supplier Details", anchor=False)
    with col2:
        if st.button("Return to Home"):
            st.session_state["page"] = {
                "name": "Home", 
                "data": {
                    "processing_supplier": False,
                },
            }
            st.rerun()
    new_name = st.text_input("Name", supplier.name)
    new_website = st.text_input("Website", supplier.website)
    new_description = st.text_input("Description", supplier.description)
    new_description = st.text_area("Notes", supplier.notes)
    if st.button("Save Changes"):
        supplier.name = new_name
        supplier.website = new_website
        supplier.description = new_description
        st.success(f"Supplier details updated!")
        time.sleep(2)
        st.rerun()

    st.divider()

    # ESG information section
    st.subheader(body="ESG Data", anchor=False)
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
    if st.button("Run Automatic Update"):
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