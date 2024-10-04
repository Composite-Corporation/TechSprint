import uuid
import time
import pytz
import streamlit as st
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

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
    updated: datetime


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
def supplier_obtain_esg_data(label: str, task: str, response_format: BaseModel) -> BaseModel:
    agent = Agent(
        driver=OpenAIDriver(
            model="gpt-4o-mini", 
            seed=1337,
        ),
        description=f"""
        You are an analyst searches the web for a company's sustainability and ESG information.

        Use the Google search tool to find relevant data sources and links.
        Then, use the Web scraping tool to analyze the content of links of interest.

        BE AS CONCISE AS POSSIBLE.
        """,
        tools=[
            WebScrapeTool(),
            GoogleSerperApiTool(),
        ],
        max_iterations=20,
        response_format=response_format,
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
    expander.subheader(body="**Overview**", anchor=False)
    expander.write(data_summary.summary)

    if available:
        expander.divider()
        expander.subheader(body="**Sources**", anchor=False)
        for source in data_summary.sources:
            expander.markdown(f"""              
            Key Quote: "{source.key_quote}"\n
            URL: {source.link}
            """)


# HELPER COMPONENT
# Used exclusively by supplier_details page to display dialog of updating ESG info
@st.dialog(title="Updating ESG Data...", width="large")
def update_dialog(supplier: Supplier):
    task_prefix = f"""
    Given the following info about a company:
        Name - {supplier.name}
        Website - {supplier.website}
        Description - {supplier.description}
        Notes - {supplier.notes}
    """
    esg_score = 0

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

    task_iso_14001 = task_prefix + "\nPlease find if this company has an ISO 14001 certification."
    data_iso_14001 = supplier_obtain_esg_data(label="ISO 14001 Certification", task=task_iso_14001, response_format=DataSummary)
    esg_score += 1 if data_iso_14001.available else 0

    task_product_lca = task_prefix + "\nPlease find if this company has any products undergoing a Life Cycle Assessment, or LCA."
    data_product_lca = supplier_obtain_esg_data(label="Product LCAs", task=task_product_lca, response_format=DataSummary)
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
    supplier.esg.updated = datetime.now(pytz.timezone('Europe/London'))
    st.success(body=f"Successfully updated ESG data for {supplier.name}!")
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
    new_notes = st.text_area("Notes", supplier.notes)
    if st.button("Save Changes"):
        supplier.name = new_name
        supplier.website = new_website
        supplier.description = new_description
        supplier.notes = new_notes
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
    update_date = supplier.esg.updated.strftime('%m/%d/%Y, %H:%M:%S %Z')
    st.write(f"**Last Updated**: {update_date}")
    supplier_esg_expander(property="Scope 1 Emissions", data_summary=supplier.esg.scope_1)
    supplier_esg_expander(property="Scope 2 Emissions", data_summary=supplier.esg.scope_2)
    supplier_esg_expander(property="Scope 3 Emissions", data_summary=supplier.esg.scope_3)
    supplier_esg_expander(property="Ecovadis Score", data_summary=supplier.esg.ecovadis)
    supplier_esg_expander(property="ISO 14001 Compliance", data_summary=supplier.esg.iso_14001)
    supplier_esg_expander(property="Life Cycle Assessments (LCA)", data_summary=supplier.esg.product_lca)
    if st.button("Run Automatic Update"):
        update_dialog(supplier=supplier)


# Initial supplier data
suppliers_data = [
    Supplier(
        id=str(uuid.uuid4()),
        name="Honeywell",
        website="https://www.honeywell.com/us/en",
        description="Go-to brand for research chemicals.",
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
            updated=datetime.now(pytz.timezone('Europe/London')),
        )
    ),
    Supplier(
        id=str(uuid.uuid4()),
        name="3M",
        website="https://www.3m.com/",
        description="3M Company is an American multinational conglomerate operating in the fields of industry, worker safety, healthcare, and consumer goods.",
        esg=ESGData(
            scope_1=DataSummary(
                available=True,
                summary="3M has been calculating its Scope 1 and Scope 2 greenhouse gas (GHG) emissions annually since 2002. The company has achieved a 68.1% reduction in these emissions while expanding its business. Scope 1 emissions include all direct emissions from sources owned or controlled by 3M, such as facilities and vehicles. The company aims to further reduce its Scope 1 and 2 emissions by at least 50% by 2030, 80% by 2040, and achieve carbon neutrality by 2050.",
                sources=[
                    Source(
                        key_quote="Since 2002, 3M’s EHS (Environment, Health and Safety) Laboratory has calculated the company’s Scope 1 and Scope 2 emissions on an annual basis, and 3M has reduced its overall Scope 1 and 2 emissions by 68.1% while growing our business.", 
                        link="https://news.3m.com/Taking-inventory-of-greenhouse-gas-emissions",
                    ),
                    Source(
                        key_quote="To achieve carbon neutrality by 2050, 3M aims to reduce Scope 1 and Scope 2 market-based GHG emissions by at least 50% by 2030.", 
                        link="https://multimedia.3m.com/mws/media/2391591O/pdf-document-to-describe-3ms-carbon-reduction-plan-for-uk.pdf",
                    ),
                ]
            ),
            scope_2=DataSummary(
                available=True,
                summary="3M has committed to reducing its Scope 2 emissions by at least 50% from a 2019 baseline by 2030, and aims for carbon neutrality in its operations by 2050. The company calculates its Scope 2 emissions annually through its Environment, Health and Safety (EHS) Laboratory, which has been doing so since 2002. The latest reports indicate a significant reduction in greenhouse gas emissions, with a 43.2% reduction since 2019.",
                sources=[
                    Source(
                        key_quote="We are committed to reduce Scope 1 and 2 market-based GHG emissions from our 2019 baseline by at least 50% by 2030.", 
                        link="https://multimedia.3m.com/mws/media/2300331O/na.pdf",
                    ),
                    Source(
                        key_quote="Since 2002, 3M's EHS Laboratory has calculated the company's Scope 1 and Scope 2 emissions on an annual basis.", 
                        link="https://news.3m.com/Taking-inventory-of-greenhouse-gas-emissions",
                    ),
                    Source(
                        key_quote="To achieve carbon neutrality by 2050, 3M aims to reduce Scope 1 and Scope 2 market-based GHG emissions by at least 50% by 2030.", 
                        link="https://multimedia.3m.com/mws/media/2391591O/pdf-document-to-describe-3ms-carbon-reduction-plan-for-uk.pdf",
                    ),
                ]
            ),
            scope_3=DataSummary(
                available=True,
                summary="3M has explicitly mentioned their Scope 3 emissions calculations in several sources. They aim to reduce absolute Scope 3 emissions by 42% by 2030 from a 2021 baseline. In 2021, their Scope 3 emissions were reported to be 11,900,000 metric tons (CO2e), covering categories 1-9. They have also engaged in initiatives to calculate and manage these emissions as part of their sustainability goals.",
                sources=[
                    Source(
                        key_quote="Reduce absolute scope 3 emissions by 42% by 2030 from a 2021 baseline.", 
                        link="https://news.3m.com/2024-10-03-3M-achieves-Science-Based-Targets-initiative-validation,-strengthening-commitment-to-decarbonization-and-customer-innovation",
                    ),
                    Source(
                        key_quote="The Scope 3 emissions for 2021 are 11,900,000 metric tons (CO2e) and include categories 1-9.", 
                        link="https://multimedia.3m.com/mws/media/2300331O/na.pdf",
                    ),
                    Source(
                        key_quote="Scope 3 emissions are all indirect emissions that occur in the value chain of the reporting company, including both upstream and downstream emissions.", 
                        link="https://multimedia.3m.com/mws/media/1261344O/bonding-tapes-sustainability-flyer-hires.pdf",
                    ),
                ]
            ),
            ecovadis=DataSummary(
                available=True,
                summary="3M has received a Gold Recognition Level from EcoVadis, indicating that it is in the 98th percentile of suppliers assessed for sustainability and corporate social responsibility.",
                sources=[
                    Source(
                        key_quote="EcoVadis awarded 3M a Gold Recognition Level for achievements in the 98th percentile of suppliers assessed in 2021.", 
                        link="https://multimedia.3m.com/mws/media/2030547O/3mtm-2021-nordic-sustainability-report.pdf",
                    ),
                    Source(
                        key_quote="3M earned a perfect score of 100% and, along with it, the Gold Recognition Level from EcoVadis.", 
                        link="https://multimedia.3m.com/mws/media/1836747O/2020-sustainability-report.pdf",
                    ),
                ]
            ),
            iso_14001=DataSummary(
                available=True,
                summary="3M has ISO 14001 certification, confirming their compliance with international standards for environmental management systems.",
                sources=[
                    Source(
                        key_quote="ISO 14001:2015 certification for 3M Company.", 
                        link="https://www.dqsglobal.com/intl/customer-database/3m-company11",
                    ),
                    Source(
                        key_quote="Proof has been furnished by means of an audit that the requirements of ISO 14001:2015 are met.", 
                        link="https://multimedia.3m.com/mws/media/1563980O/180328-tuv-certificate-14001-en.PDF",
                    ),
                    Source(
                        key_quote="Every 3M Automotive OEM manufacturing facility has certifications in ISO 14001 for environmental systems.", 
                        link="https://www.3m.co.id/3M/en_ID/oem-tier-id/resources/certifications-and-regulatory/",
                    ),
                ]
            ),
            product_lca=DataSummary(
                available=True,
                summary="3M conducts Life Cycle Assessments (LCA) for select products as part of their sustainability initiatives. They utilize LCA to evaluate the environmental impacts of their products throughout their life cycle, which is integrated into their Life Cycle Management (LCM) process.",
                sources=[
                    Source(
                        key_quote="3M follows a Life Cycle Management (LCM) process to identify environmental, health and safety opportunities, manage risks and ensure regulatory compliance.", 
                        link="https://transformationalcompany.ca/case-study/3m-utilizes-life-cycle-assessment-lca-to-influence-value-chain/",
                    ),
                    Source(
                        key_quote="The LCM system applies to all 3M products. In addition, for select products we conduct Life Cycle Assessments (LCAs), Environmental Product.", 
                        link="https://multimedia.3m.com/mws/media/2292786O/3m-2023-global-impact-report.pdf",
                    ),
                    Source(
                        key_quote="3M has long taken a life cycle thinking approach and carry out analysis on products to help us understand their environmental impact.", 
                        link="https://www.linkedin.com/pulse/how-3m-combines-innovation-sustainability-romy-kenyon",
                    ),
                ]
            ),
            segment="High",
            updated=datetime.now(pytz.timezone('Europe/London')),
        )
    ),
    Supplier(
        id=str(uuid.uuid4()),
        name="Azenta Life Sciences",
        website="https://www.azenta.com/",
        description="Azenta Life Sciences stands as a prominent provider of state-of-the-art laboratory solutions, granting access to esteemed brands including Biocision, FluidX, Ziath, FreezerPro, and 4titude.",
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
            updated=datetime.now(pytz.timezone('Europe/London')),
        )
    )
]