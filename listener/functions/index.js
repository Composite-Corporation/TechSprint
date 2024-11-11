// functions/index.js

const functions = require('firebase-functions');
const admin = require('firebase-admin');
const axios = require('axios'); // For making API calls

admin.initializeApp();

exports.onCompanyCreate = functions.firestore
  .document('tasks/{taskId}/companies/{companyId}')
  .onCreate(async (snap, context) => {
    // Wait for 10 seconds before proceeding
    await new Promise(resolve => setTimeout(resolve, 10000));
    
    const data = snap.data();
    const companyId = snap.id; // Store the document ID of the created company
    const taskId = context.params.taskId; // Get the task ID from the context

    // Extract the org_id from the parent task document
    const taskRef = admin.firestore().collection('tasks').doc(taskId);
    const taskSnap = await taskRef.get();
    const orgId = taskSnap.data()?.org_id;

    if (!orgId) {
      console.error(`Error: org_id not found in task document ${taskId}`);
      return;
    }

    // Retrieve Cloud Run API URL
    const cloudRunApiUrl = "https://sls-prototype-task-api-228031574235.europe-north1.run.app/task_upload";

    const payload = { task_doc_id: taskId, company_doc_id: companyId, org_id: orgId };

    // Make a single API call for the new company
    try {
      const response = await axios.post(cloudRunApiUrl, payload);
      console.log(`Successfully called Cloud Run API for company ${companyId}: ${response.status}`);
    } catch (error) {
      console.error(`Error calling Cloud Run API for company ${companyId}:`, error);
    }
  });
