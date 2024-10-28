// functions/index.js

const functions = require('firebase-functions');
const admin = require('firebase-admin');
const axios = require('axios'); // For making API calls

admin.initializeApp();

exports.onTaskCreate = functions.firestore
  .document('tasks/{taskId}')
  .onCreate(async (snap, context) => {
    // Wait for 10 seconds before proceeding
    await new Promise(resolve => setTimeout(resolve, 10000));
    
    const data = snap.data();
    const taskId = snap.id; // Store the document ID of the created document

    // Extract the org_id from the document
    const orgId = data["org_id"];
    if (!orgId) {
      console.error(`Error: org_id not found in task document ${taskId}`);
      return;
    }

    // Retrieve Cloud Run API URL
    const cloudRunApiUrl = "https://sls-prototype-task-api-228031574235.europe-north1.run.app/task_upload";

    // Get a reference to the companies subcollection
    const subcollectionRef = snap.ref.collection('companies');

    // Retrieve the companies documents
    const companiesSnapshot = await subcollectionRef.get();
    console.log(`Number of companies retrieved: ${companiesSnapshot.size}`);

    // Prepare API calls for each company
    const apiCalls = companiesSnapshot.docs.map((doc) => {
      const companyDocId = doc.id; // Updated to get the document ID from the reference
      const payload = { task_doc_id: taskId, company_doc_id: companyDocId, org_id: orgId };
      return axios.post(cloudRunApiUrl, payload)
        .then(response => {
          console.log(`Successfully called Cloud Run API for company ${companyDocId}: ${response.status}`);
        })
        .catch(error => {
          console.error(`Error calling Cloud Run API for company ${companyDocId}:`, error);
        });
    });

    try {
      // Make API calls concurrently
      await Promise.all(apiCalls);
    } catch (error) {
      console.error('Error making API calls:', error);
    }
  });
