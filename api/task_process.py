# main.py

from fastapi import FastAPI, HTTPException
import asyncio
from utils.agent import Agent
from compositeai.tools import GoogleSerperApiTool, WebScrapeTool
from compositeai.drivers import OpenAIDriver
import json
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.cloud import firestore
from dotenv import load_dotenv
import os
import uuid
from compositeai.agents import AgentResult
from utils.supplier_data import DataSummary, ESGData
from datetime import datetime
import pytz

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
    return firestore.AsyncClient(project=GCLOUD_PROJECT_NUMBER, credentials=credentials)


# Use this in your FastAPI app startup
@app.on_event("startup")
async def startup_event():
    global db
    db = await initialize_firestore()


async def process_company(company_ref, org_id: str):
    """Process a single company name and update the Firestore document."""
    try:
        company_doc = await company_ref.get()
        company_data = company_doc.to_dict()
        company_name = company_data.get('name', '')
        company_id = str(uuid.uuid4())

        agent = Agent(
            driver=OpenAIDriver(
                model="gpt-4o-mini", 
                seed=1337,
            ), 
            description=f"""
            You are an analyst who searches the web for a company's sustainability and ESG information.

            Use the Google search tool to find relevant data sources and links.
            Then, use the Web scraping tool to analyze the content of links of interest.
            Cite quotes from the source to support your answer.
            Provide a link to the sources.

            BE AS CONCISE AS POSSIBLE.
            """,
            tools=[
                WebScrapeTool(),
                GoogleSerperApiTool(),
            ],
            max_iterations=20,
            response_format=DataSummary,
        )

        esg_data = ESGData()
        esg_score = 0

        async def run_agent(label, task):
            result = await agent.aexecute(task)
            if isinstance(result, AgentResult):
                data_summary = result.content
                if data_summary.available:
                    esg_score += 1
                return data_summary
            return DataSummary(available=False, summary="", sources=[])

        task_prefix = f"""
        Given the following info about a company:
        Name - {company_name}
        """

        # Scope 1 Emissions
        task_scope_1 = task_prefix + """
        Please find any data on THEIR OWN scope 1 emissions calculations.
        Scope 1 emissions are direct emissions from sources owned or controlled by a company.
        These include things like: on-site energy, fleet vehicles, process emissions, or accidental emissions.
        ONLY INCLUDE EXPLICIT MENTIONS OF "SCOPE 1" DATA.
        """
        esg_data.scope_1 = await run_agent("Scope 1 Emissions", task_scope_1)

        # Scope 2 Emissions
        task_scope_2 = task_prefix + """
        Please find any data on THEIR OWN scope 2 emissions calculations.
        Scope 2 emissions are indirect greenhouse gas (GHG) emissions that result from the generation of energy that an organization purchases and uses.
        These include things like the purchase of electricity from: steam, heat, cooling, etc.
        ONLY INCLUDE EXPLICIT MENTIONS OF "SCOPE 2" DATA.
        """
        esg_data.scope_2 = await run_agent("Scope 2 Emissions", task_scope_2)

        # Scope 3 Emissions
        task_scope_3 = task_prefix + """
        Please find any data on THEIR OWN scope 3 emissions calculations.
        Scope 3 emissions are greenhouse gas (GHG) emissions that are a result of activities that a company indirectly affects as part of its value chain, but that are not owned or controlled by the company.
        These include things like: supply chain emissions, use of sold products, waste disposal, employee travel, contracted waste disposal, etc.
        ONLY INCLUDE EXPLICIT MENTIONS OF "SCOPE 3" DATA.
        """
        esg_data.scope_3 = await run_agent("Scope 3 Emissions", task_scope_3)

        # Ecovadis Score
        task_ecovadis = task_prefix + "\nPlease find if this company has a publicly available Ecovadis score."
        esg_data.ecovadis = await run_agent("Ecovadis Score", task_ecovadis)

        # ISO 14001 Certification
        task_iso_14001 = task_prefix + "\nPlease find if this company has an ISO 14001 certification."
        esg_data.iso_14001 = await run_agent("ISO 14001 Certification", task_iso_14001)

        # Product LCA
        task_product_lca = task_prefix + "\nPlease find if this company has any products undergoing a Life Cycle Assessment, or LCA."
        esg_data.product_lca = await run_agent("Product LCAs", task_product_lca)

        # Determine ESG segment
        if esg_score <= 2:
            esg_data.segment = "Low"
        elif esg_score <= 4:
            esg_data.segment = "Medium"
        else:
            esg_data.segment = "High"

        esg_data.updated = datetime.now(pytz.timezone('UTC'))

        # Update the Firestore documents with the processing result and status
        supplier_ref = db.document(f"orgs/{org_id}/suppliers/{company_id}")
        await supplier_ref.set({
            'esg': esg_data.dict(),
        })
        await company_ref.update({
            'esg': esg_data.dict(),
            'processed': True,
            'status': 'success'
        })
        return esg_data.dict()

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
