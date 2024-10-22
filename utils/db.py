from typing import Optional, List, Any
from datetime import datetime

from pydantic import ValidationError
from firebase_admin import firestore
import firebase_admin
import json
import os
from google.cloud import secretmanager
from utils.supplier_data import Supplier


class DB():
    _instance = None
    firebase_admin_init = False

    def __new__(cls, *args, **kwargs):
        # If Firebase Admin has not been initalized, do it only once ever globally
        # This prevents a breaking bug since firebase_admin initialize
        # app cannot be run more than once globally.
        if not cls.firebase_admin_init:
            cls.init_firebase_admin()
            cls.firebase_admin_init = True
        if cls._instance is None:
            cls._instance = super(DB, cls).__new__(cls)
        return cls._instance


    def __init__(self) -> None:
        # Instantiate the firestore client
        self.client = firestore.client()


    @classmethod
    def init_firebase_admin(self):
        GCLOUD_PROJECT_NUMBER = os.getenv("GCLOUD_PROJECT_NUMBER")
        FIREBASE_SA_SECRET_NAME = os.getenv("FIREBASE_SA_SECRET_NAME")

        # Create credentials object then initialize the firebase admin client
        client = secretmanager.SecretManagerServiceClient()
        name = client.secret_version_path(project=GCLOUD_PROJECT_NUMBER, secret=FIREBASE_SA_SECRET_NAME, secret_version="latest")
        response = client.access_secret_version(name=name)
        service_account_info = json.loads(response.payload.data.decode('utf-8'))

        # build credentials with the service account dict
        creds = firebase_admin.credentials.Certificate(service_account_info)

        # initialize firebase admin
        firebase_admin.initialize_app(credential=creds)


    def create_user(self, uid: str, org_id: str) -> None:
        self.client.collection("users").document(uid).set({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "org_id": org_id,
        })
        

    def get_user(self, uid: str) -> Optional[dict]:
        doc_ref = self.client.collection("users").document(uid)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None


    def insert_supplier(
        self, 
        supplier: Supplier,
        org_id: str,
    ) -> None:
        # # Convert current time to MM_DD_YYYY format string
        # now = datetime.now()
        # date_format = now.strftime("%m_%d_%Y")

        supplier_id = supplier.id

        # Serialize the Supplier instance to a dictionary
        supplier_dict = supplier.model_dump()

        # Insert into Firestore
        doc_ref = self.client.collection("orgs").document(org_id).collection("suppliers").document(supplier_id)
        doc_ref.set(supplier_dict)

    
    def update_supplier(
        self, 
        supplier: Supplier,
        org_id: str,
    ) -> None:
        # # Convert current time to MM_DD_YYYY format string
        # now = datetime.now()
        # date_format = now.strftime("%m_%d_%Y")

        supplier_id = supplier.id

        # Serialize the Supplier instance to a dictionary
        supplier_dict = supplier.model_dump()

        # Update data
        doc_ref = self.client.collection("orgs").document(org_id).collection("suppliers").document(supplier_id)
        doc_ref.update(supplier_dict)

    
    def delete_supplier(
        self, 
        supplier_id: str,
        org_id: str
    ) -> None:
        # Reference to the supplier document
        doc_ref = self.client.collection("orgs").document(org_id).collection("suppliers").document(supplier_id)
        
        # Optional: Check if the document exists
        doc = doc_ref.get()
        if doc.exists:
            # Delete the document
            doc_ref.delete()


    def get_org_suppliers(
        self,
        org_id: str,
    ) -> List[Supplier]:
        # Reference to the 'suppliers' collection
        suppliers_ref = self.client.collection("orgs").document(org_id).collection("suppliers")

        # Retrieve all documents in the 'suppliers' collection
        docs = suppliers_ref.stream()

        # Initialize an empty list to hold Supplier instances
        supplier_list = []

        # Iterate over each document
        for doc in docs:
            data = doc.to_dict()
            try:
                # Deserialize Firestore data into a Supplier instance
                supplier = Supplier(**data)
                supplier_list.append(supplier)
            except ValidationError as e:
                print(f"Error parsing supplier {doc.id}: {e}")
        
        return supplier_list

db = DB()
