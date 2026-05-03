I will describe here items I would like to see added/improved



I will try to show "Page" each time, if this is not mentioned then you have to decide where it makes more sense to do this



General Improvements



GEN 1) Documentation : Build a complete documentation of the app following best practices and complete with "Release Notes" where each new version will add its updates. Include a "User Manual" file with a section "what this app is for" followed  by sections that explain what functionality is available to a user for each page. Also include a tool documentation describing underlying setup, tables, linked fields etc.



GEN 2) Clarify the architecture of the tool, the location of any tables used (SQLite database I understand, unclear where it is saved, if I can maintain this locally and how to access) and files generated. Ideally all these would exist locally on my machine and would need to know how to modify directly.



GEN 3) ABILITY TO VIEW/EDIT UNDERLYING TABLES:

Under each page, would like to add the actual table in a form that resembles excel or Nocodb or similar so I can access directly when I need to copy or need to edit the underlying data. If this will only be for presentational/copy and not have ability to edit, provide the steps the user needs to do to edit the underlying table somehow. Given the table might become large, you might show a preselected number of records (or allow the user to select) and another option for "expand/show all". This applies to all tables. If you find it better practice, you can add a separate page that will show these tables (maybe this will be cleaner for typical use)



GEN 4) ABILITY FOR A PROJECT LEVEL OVERVIEW:

Required to have a view/page where I can see a full list of projects where things like client, client\_code, client\_suffices, budgets, invoiced, time charges, write offs and other related information is shown in a row, and all projects are shown. User can filter on any field or the first 5 or so.



Specific Pages



SP 1) Landing Page: Make it so the user does not need to drag down the line to see the available pages on the left of the column, they should all show from the start



SP 2) Authorisation: I expected that the login/psd in the first page before I sign in should be auto completed (given this is available functionality form my browser) but this does not seem to work for the app, can we fix this?



SP 3) Page "Generate Invoice": Two points here

SP 3a) Currently to start the process  the user needs to start by selecting a client and progressively move down. I would prefer to be able to alternatively select a project Instead sometimes. Or maybe a combined Client \_project Field  might be a practical third option. The two new suggestions will be in addition to the current process

SP 3b) Clarification:  When Clicking  "Generate invoice" I always get a note saying invoice generated and then have to click another button to download the actual file .  I would like to be clear what the process is. For example: does the first click generates the record and the second file?



SP 4) Page "Invoice Log": 

SP 4a) I would like the filters to be dynamic such that given a certain selection in a filter modifies available options for the remaining filters.

SP 4b) In the presentation of invoices show headers.

SP 4c) In the table presenting the invoices, include an expenses column

SP 4d)In the table presenting the invoices, the button next to each invoice indicating "PDF/DOCX", is that a link to a downloaded file or link to a file saved internally? will these links always work or can break if I move a generated invoice?



SP 5) Page "Pipeline / CRM"

SP 5a) There should be capacity to see organized tabular information on the pipeline projects (ones not approved/started/finished) (similarly to GEN 4 that applies to projects). This is frequently reviewed with the managers to understand the overall pace

SP 5B) Pipeline projects added should allow for "Min Budget", "Max Budget", "Est. Budget" and their probability of being accepted by the clients. The product of the probability with the amounts will be a very useful statistic to have in a dashboard style, which will indicate min-est.-max anticipated revenue. 



SP 6) Wherever we have presentation of Time charges, I would like to incorporate the additional break-down between "Local"/"ICEE"/"Other". Information provided from the time charges report include the person/consultant charging their time. We should now add a parameter table that shows by consultant the "Local"/"ICEE"/"Other" group each belongs to so we can the easily get rolled up time charges in terms of the sum of the time charges, the invoiced amounts (sum of net of VAT amounts in invoices to that project), as well as write offs 

