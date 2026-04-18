I will describe the current situation and setup we have and will ask specific assistance.

Target:
Our target is to build an easy to use robust app or executable that will manage information on projects, invoices, while offering capacity for issuing invoices and some basic dashboards.
Main areas would include:
# Invoice generation (reads from underlying tables, excel or NocoDB or other)
# Invoice log with filters / search
# Client management (CRUD)
# Project management (CRUD)
# Pipeline / CRM view
# Revenue / billing dashboards

Would rather I maintain ability to easily open in excel as well in case I need to perform a task there or simply run a quick summary or pivot off the data. Also very useful to have an app-like experience or exe where things can be further automated (adding a project with ability to select a client from the list and other info to be brought in automatically, to introduce a new subset of the project, to issue an invoice where by selecting only a few fields (can see in the repository but most would be project, sub-project if relevant, amount and most other fields would auto compete, would save in both word and pdf with auto re-numbering and records in the tables auto-updated.) and others)
Ability to have underlying tables consistently and safely interact in a robust error-free way became apparent with the nocodedb attempt,  

Historical Approach:
First set of sttempt - STREAMLIT
In the various repositories you can find much of the work performed in building this on streamlit with excel in the background. This had a numbr of issues in the versions, most of which had to do with being able dynamically updating the background file vs. simply losing new edits.
Pros: Streamlit was easy to access and complete, also good to have excel background (if we could get it to work properly). Also quite dynamic in updating
Cons: Rerunning all code all the time was the root cause of many issues, introducing the "State" conditions helped but created others. Generally had trouble maintianing active link with excel data and sometimes was tedious to keep up with the platforms updates in newer versions that would break the existing strucutre (i.e. icons lost functions not working etc.)

Second attampt - NoCodeDB
Pros: robust structure
Cons: Not very interactive, feels like maintaining a DB (so why not simply get a cleaner excel?), no friendly UX, STILL NEEDS FURTHER INTEGRATION FOR FRONT-END AND AUTOMATIONS (LIKE invoicing etc.)

Document "InvoiceApp_Improvement_Plan" is a structured plan if we were to build further on this approach. Claude developed this after reviewing the above.

What I need yu to do now:
I would suggest that you first try to understand the flows and interactions of previous development, by analysing the repositories and the "InvoiceApp_Improvement_Plan" document.
Then first suggest an envisioned structure (platforms / architecture / UX / Main Functionalities) for optimal implementation based on my specific circumstances. Also propose an alternative option as well where we would re-use much of the current structures in a way to make them functional.

Once I review these I will select the way forward.