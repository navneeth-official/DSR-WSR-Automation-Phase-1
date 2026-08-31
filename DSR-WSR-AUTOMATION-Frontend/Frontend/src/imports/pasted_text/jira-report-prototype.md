Create a prototype design for the following use cases:
 
The daily and weekly status reports for multiple teams under a client in a company is currently filled in manually by the developers and testers testers themselves. So what I am planning is to create a UI that accepts a JSON response from JIRA Tickets ( Created by Rovo AI for multiple people in a single day or for multiple days ) and then map the response to the format in which users can see how the response would look like (like preview use a table format) where users can edit and make changes to different attributes of the tickets. Then he can accept/submit it.
 
There is a second page where users can select filters like team/track name and assignee name, project id etc etc and filter out the tickets from the tickets that are saved in an easily readable tabular or card kind of format which ever suits well.
 
I will provide you with how the request to the Rovo AI looks like for a single day or multiple days as well as the JSON response format
 
 
Retrieve all Jira issues assigned to:
 
* Vignesh Krishnan
* Vineed Kaladharan
* Rishi Manoj
Include issues where any of the following occurred between 2026-04-30 and 2026-05-14:
 
* Issue created
* Issue updated
* Status transitioned
* Assignee changed
* Sprint changed
* Issue resolved
For each issue return the following fields exactly as shown:
 
json
{
  "project_key": "",
  "project_name": "",
  "sprint_name": "",
  "sprint_start_date": "",
  "sprint_end_date": "",
  "jira_key": "",
  "summary": "",
  "description": "",
  "issue_type": "",
  "priority": "",
  "assignee": "",
  "reporter": "",
  "status": "",
  "story_points": 0,
  "created_date": "",
  "updated_date": "",
  "resolved_date": "",
  "snapshot_date": ""
}
 
Rules:
Return one JSON object per Jira issue.
Include active and closed sprint information when available.
Include completed and incomplete issues.
Use null for unavailable values.
Set snapshot_date to today's date.
Return only issues modified between 2026-04-30 and 2026-05-14.
Output must be valid JSON.
 
Now a single day
 
Retrieve all Jira issues assigned to the following users:
 
* Vignesh Krishnan
* Vineed Kaladharan
* Rishi Manoj
Return only issues that have been created, updated, transitioned, reassigned, moved between sprints, or resolved during the last 24 hours.
 
For each issue return the following fields exactly as shown:
 
json
{
  "project_key": "",
  "project_name": "",
  "sprint_name": "",
  "sprint_start_date": "",
  "sprint_end_date": "",
  "jira_key": "",
  "summary": "",
  "description": "",
  "issue_type": "",
  "priority": "",
  "assignee": "",
  "reporter": "",
  "status": "",
  "story_points": 0,
  "created_date": "",
  "updated_date": "",
  "resolved_date": "",
  "snapshot_date": ""
}
 
 
* snapshot_date = current date
Requirements:
Return one record per Jira issue.
Include active and closed sprint information if available.
Include both completed and incomplete issues.
Return NULL when a field is unavailable.
Format output as JSON suitable for database ingestion into jira_issue_snapshot.
Include only issues modified during the last 24 hours.
Now the response format
 
A demo design ( dont take any untold details from the design like contents or unecessary design elements ) format is given below
 
[
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2750",
    "summary": "FAM | MFR | Offsite Warehouse List is sorted by Offsite Number instead of record creation date",
    "description": "As per the requirement, the table should be sorted by record creation date, but it is currently sorted by offsite number passed",
    "issue_type": "Bug",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Vinu Lilitha",
    "status": "Done",
    "story_points": null,
    "created_date": "2026-05-11",
    "updated_date": "2026-05-11",
    "resolved_date": "2026-05-11",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2749",
    "summary": "FAM | MFR | Status Column Displays 'X' for Offsite Warehouses with Status 'New – Under Construction'",
    "description": "The Status column in the Offsite Warehouse List shows 'X' when the offsite warehouse status is set to 'New – Under Construction' passed",
    "issue_type": "Bug",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Vinu Lilitha",
    "status": "Done",
    "story_points": null,
    "created_date": "2026-05-11",
    "updated_date": "2026-05-11",
    "resolved_date": "2026-05-11",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2744",
    "summary": "FAM | MFR | Changes to Offsite Warehouse - Create & Update (R)",
    "description": "As a developer, I would like to incorporate the changes mentioned in the acceptance criteria so that I am able to align the Offsite Warehouse features with the updated requirements. All acceptance criteria in LOC-2663 and LOC-2665 have been implemented. Updates to Offsite Warehouse Create and Edit pages are completed. Unit testing is complete. Changes are successfully deployed in CERT. Field changes include: Offsite Number (Editable on Create, Read-only on Edit), EXE No. renamed to EXE Whse Id, EXE DC No. and OMI No. remain editable, TMS No. changed from Numeric to Alphanumeric.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Suraj Seshadri",
    "status": "Done",
    "story_points": 1,
    "created_date": "2026-05-07",
    "updated_date": "2026-05-11",
    "resolved_date": "2026-05-11",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2742",
    "summary": "FAM | MFR | Validation issues: warehouse number length and tobacco permit mandatory flag",
    "description": "1. The minimum length for the Number field should be 3 digits, but it still accepts fewer than 3 digits and allows submission passed. 2. The tobacco permit field is currently mandatory; it should be non-mandatory and accept only numeric values passed.",
    "issue_type": "Bug",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Vinu Lilitha",
    "status": "Done",
    "story_points": null,
    "created_date": "2026-05-06",
    "updated_date": "2026-05-11",
    "resolved_date": "2026-05-11",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2739",
    "summary": "FAM | MFR | Selecting a warehouse from the list navigates the user to the edit page instead of the warehouse view page",
    "description": "Selecting a warehouse from the warehouse list navigates the user to the edit page instead of the warehouse view page passed",
    "issue_type": "Bug",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Vinu Lilitha",
    "status": "Done",
    "story_points": null,
    "created_date": "2026-05-05",
    "updated_date": "2026-05-07",
    "resolved_date": "2026-05-07",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2738",
    "summary": "FAM | MFR | Validation issues in Tobacco Permit and OMI Number fields on the Create Warehouse page",
    "description": "1. OMI Number accepts single digits and allows to submit passed. 2. The Tobacco Permit field accepts characters and special characters, but allows submission only for numeric values, and no validation message is displayed for invalid input.",
    "issue_type": "Bug",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Vinu Lilitha",
    "status": "Done",
    "story_points": null,
    "created_date": "2026-05-05",
    "updated_date": "2026-05-07",
    "resolved_date": "2026-05-07",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2724",
    "summary": "Document our current/developed VSAM/EMD integration - Main Warehouse and Offsite Warehouse (R)",
    "description": "As a developer, when documenting the VSAM integration for Main Warehouses and EMD integration for Main Warehouse and Offsite Warehouse, I want to outline the integration process so that the team understands how it works for Warehouses. As a project manager, when reviewing the documentation, I want to see edge cases and failure points so that we can prepare for potential issues during OMI/MF retirement. Acceptance criteria: Document the happy path views of the VSAM/EMD integration, include known edge cases, identify potential failure points.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vignesh Krishnan",
    "reporter": "Gilbert Trejo",
    "status": "Done",
    "story_points": 2,
    "created_date": "2026-04-27",
    "updated_date": "2026-05-11",
    "resolved_date": "2026-05-11",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2660",
    "summary": "FAM | MFR | Warehouse - Edit Offsite Warehouses - Save FAM-API (R)",
    "description": "As a Partner, when I edit an offsite warehouse, I want to save the information, so that the edited warehouse can be saved and offsite warehouse details are sent to the JavaDAO. Acceptance criteria: FAM API WarehouseOffsiteController handles PUT requests at /api/warehouse/offsite, calls OffsiteWarehouseService for REST calls to JavaDAO-Location with try-catch, saves audit logs, responds with 200 or ServiceException. Unit tests for controller PUT and service update method.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vignesh Krishnan",
    "reporter": "Sreejith Keeriyadathu Kalarikkal",
    "status": "Done",
    "story_points": 3,
    "created_date": "2026-03-30",
    "updated_date": "2026-05-04",
    "resolved_date": "2026-05-04",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2659",
    "summary": "FAM | MFR | Warehouse - Create Offsite Warehouse - Save FAM-API (R)",
    "description": "As a Partner, when I create a new Offsite Warehouse, I want to save the information to the main warehouse so that the warehouse data and offsite warehouse data can be sent down to the JavaDAO and saved to EMD. Acceptance criteria: FAM UI calls WarehouseOffsiteController at /api/warehouse/offsite with POST method, calls OffsiteWarehouseService for REST calls to JavaDAO-Location with try-catch, saves audit logs, responds with 200 or ServiceException. Unit tests for controller POST and service create method.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vignesh Krishnan",
    "reporter": "Sreejith Keeriyadathu Kalarikkal",
    "status": "Done",
    "story_points": 3,
    "created_date": "2026-03-30",
    "updated_date": "2026-05-04",
    "resolved_date": "2026-05-04",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.14 FY26 Fornax",
    "sprint_start_date": "2026-04-30",
    "sprint_end_date": "2026-05-14",
    "jira_key": "LOC-2630",
    "summary": "FAM | MFR | Analysis - Message sent to WPUD520 AND WPUD670",
    "description": "As a developer, I would like to analyse and understand the information and message format being sent by the Location Mainframe app used for warehouse management to WPUD520 and WPUD670, so that we are able to replicate the functionality in FAM. Acceptance criteria: The information sent to WPUD520 and WPUD670 by the existing location mainframe app has been documented, the message format used for communication is analyzed and understood, the solution approach has been determined and updated in LOC-2385.",
    "issue_type": "Spike",
    "priority": "Low",
    "assignee": "Vignesh Krishnan",
    "reporter": "Suraj Seshadri",
    "status": "Done",
    "story_points": 3,
    "created_date": "2026-03-16",
    "updated_date": "2026-05-08",
    "resolved_date": "2026-05-08",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "COST",
    "project_name": "Cost Core Service",
    "sprint_name": "Nacogdoches - 248",
    "sprint_start_date": "2026-03-18",
    "sprint_end_date": "2026-04-01",
    "jira_key": "COST-5385",
    "summary": "Replay `CST_ELEM` Messages to Capture all Buyer Adjustment (meat) Records",
    "description": "Based on research conducted in COST-5382, we need to capture all buyer adjustment records for all other related item class codes. Right now we only capture class code 2 (Meat Merchandise) into our buyer_adjustment table. Notes: See if a replay of our raw CST_ELEM messages will suffice. If not, request initial load from ICC.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Rishi Manoj",
    "reporter": "Danny Baggett",
    "status": "Done",
    "story_points": 1,
    "created_date": "2026-03-05",
    "updated_date": "2026-05-04",
    "resolved_date": "2026-03-24",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.13FY26 Eridanus",
    "sprint_start_date": "2026-04-16",
    "sprint_end_date": "2026-04-30",
    "jira_key": "LOC-2367",
    "summary": "FAM | MFR | Warehouse - Edit Warehouse - UI (R)",
    "description": "As a Partner, when I am on the warehouse view screen, I would like to have an update functionality, so that I am able to update the warehouse details in the FAM app. Acceptance criteria include: Warehouse-Admin role can click Edit, fields pre-populated with latest data, editable/non-editable fields per spec, hardcoded fields properly populated, mandatory fields marked, uses Mortar libraries, breadcrumbs, Save button updates warehouse and VSAM via PUT /api/warehouse, Cancel returns to View page. Fields include Type, Number, Location Name, Abbreviation, Status, Open/Close Date, Address, City, State, Zip, County, Phone, Contact, Email, Bill To fields, OMI No., Tobacco Permit, Facility ID, Organization ID.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Sreejith Keeriyadathu Kalarikkal",
    "status": "Done",
    "story_points": 3,
    "created_date": "2026-01-20",
    "updated_date": "2026-05-06",
    "resolved_date": "2026-04-24",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.13FY26 Eridanus",
    "sprint_start_date": "2026-04-16",
    "sprint_end_date": "2026-04-30",
    "jira_key": "LOC-2362",
    "summary": "FAM | MFR | Warehouse - Create Warehouse - UI (R)",
    "description": "As a Partner, when I need to create a new warehouse, I want to have a warehouse creation UI screen, so that I can easily input the required information to create a Warehouse in the FAM app. Acceptance criteria include: Warehouse-Admin can navigate to Create Warehouse, input fields per spec, validation on field values, hardcoded fields populated, mandatory fields marked, uses Mortar libraries, breadcrumbs, Submit creates warehouse via POST /api/warehouse, Cancel clears inputs and returns to Home. Fields include Type, Number, Location Name, Abbreviation, Status, Open/Close Date, Address, City, State, Zip, County, Phone, Contact, Email, Bill To fields, OMI No., Tobacco Permit, Facility ID, Organization ID.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Sreejith Keeriyadathu Kalarikkal",
    "status": "Done",
    "story_points": 3,
    "created_date": "2026-01-20",
    "updated_date": "2026-05-06",
    "resolved_date": "2026-04-24",
    "snapshot_date": "2026-06-11"
  },
  {
    "project_key": "LOC",
    "project_name": "LoCo",
    "sprint_name": "Q2.13FY26 Eridanus",
    "sprint_start_date": "2026-04-16",
    "sprint_end_date": "2026-04-30",
    "jira_key": "LOC-2357",
    "summary": "FAM | Mainframe retirement | Warehouse - List Page | UI (R)",
    "description": "As a user with permissions for warehouse management, when I view the warehouse list, I want to see all main warehouses, so that I am able to view the warehouse I am looking for. Acceptance criteria include: Warehouse List navigation added, new UI screen with breadcrumbs, table with WHSE#, Warehouse Name, Type, Address, City, State, Zip Code, Status. Search, Sort, and Pagination (default 15) similar to Store List. Click navigates to Warehouse details page. Data fetched via GET /api/warehouse/retrieve/all returning List<Warehouse>.",
    "issue_type": "Story",
    "priority": "Low",
    "assignee": "Vineed Kaladharan",
    "reporter": "Sreejith Keeriyadathu Kalarikkal",
    "status": "Done",
    "story_points": 3,
    "created_date": "2026-01-20",
    "updated_date": "2026-05-11",
    "resolved_date": "2026-04-21",
    "snapshot_date": "2026-06-11"
  }
]