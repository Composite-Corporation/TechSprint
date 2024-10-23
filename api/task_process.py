# main.py

from fastapi import FastAPI, HTTPException
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.cloud import firestore
from dotenv import load_dotenv
from datetime import datetime
from compositeai.tools import GoogleSerperApiTool, WebScrapeTool
from compositeai.drivers import OpenAIDriver
from compositeai.agents import AgentResult
from pydantic import BaseModel
import pytz
import os
import uuid
import json
from supplier_data import DataSummary, ESGData, Supplier, AgentSupplier
from agent import Agent

load_dotenv()
 
app = FastAPI()

# Initialize Firestore client
async def initialize_firestore():
    GCLOUD_PROJECT_NUMBER = os.getenv("GCLOUD_PROJECT_NUMBER")
    FIREBASE_SA_SECRET_NAME = os.getenv("FIREBASE_SA_SECRET_NAME")

    # Create credentials object then initialize the firebase admin client
    client = secretmanager.SecretManagerServiceClient()
    name = client.secret_version_path(project=GCLOUD_PROJECT_NUMBER, secret=FIREBASE_SA_SECRET_NAME, secret_version="latest")
    response = client.access_secret_version(name=name)
    service_account_info = json.loads(response.payload.data.decode('UTF-8'))

    # Create credentials object
    credentials = service_account.Credentials.from_service_account_info(service_account_info)

    # Initialize Firestore client with the credentials
    return firestore.AsyncClient(credentials=credentials)


# Use this in your FastAPI app startup
@app.on_event("startup")
async def startup_event():
    global db
    db = await initialize_firestore()


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
    for chunk in agent.execute(task, stream=True):
        if isinstance(chunk, AgentResult):
            agent_result = chunk.content
    return agent_result


async def process_company(company_ref, org_id: str):
    """Process a single company name and update the Firestore document."""
    try:
        company_doc = await company_ref.get()
        company_data = company_doc.to_dict()
        company_name = company_data.get('name', '')
        company_id = str(uuid.uuid4())

        task_prefix = f"""
        Given the following info about a company:
            Name - {company_name}
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

        processed_supplier = Supplier(
            id=company_id,
            name=data_basic_info.name,
            website=data_basic_info.website,
            description=data_basic_info.description,
            esg=ESGData(
                scope_1=data_scope_1,
                scope_2=data_scope_2,
                scope_3=data_scope_3,
                ecovadis=data_ecovadis,
                iso_14001=data_iso_14001,
                product_lca=data_product_lca,
                segment=segment,
                updated=datetime.now(pytz.timezone('Europe/London')),
            )
        )

        supplier_ref = db.document(f"orgs/{org_id}/suppliers/{company_id}")
        supplier_dict = processed_supplier.model_dump()
        await supplier_ref.set(supplier_dict)
        await company_ref.update({
            'processed': True,
            'status': 'success'
        })
        return processed_supplier.dict()

    except Exception as e:
        # Update the Firestore document with error status
        await company_ref.update({
            'processed': True,
            'status': 'error',
            'error_message': str(e)
        })
        return None


@app.post("/task_upload")
async def task_upload(data: dict):
    task_doc_id = data.get('task_doc_id')
    company_doc_id = data.get('company_doc_id')
    org_id = data.get('org_id')
    if not task_doc_id or not company_doc_id or not org_id:
        raise HTTPException(status_code=400, detail="task_doc_id, company_doc_id, and org_id are required in the JSON body.")

    try:
        # Get the task document reference
        task_doc_ref = db.collection('tasks').document(task_doc_id)

        # Get the company document reference
        company_ref = task_doc_ref.collection('companies').document(company_doc_id)

        # Process the company
        result = await process_company(company_ref, org_id)

        return {'company': company_doc_id, 'result': result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing company: {str(e)}")
