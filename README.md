Redmine -> Azure DevOps Migration
=================================

This repo has a script `migrate.py` that can you to migrate your Redmine issue
to Azure DevOps work items.

It is *not* a fire and forgot kind of script but acts as a starting point
for your own migration. To use it you have to:

- install the dependencies in `requirements.txt`
- adjust the constants at the top of the script (redmine url, tokens, etc)
- adjust the filter of redmine issue at the top of main()

After that you can try it. I highly recommend to first try it on a test project.

It does not migrate everything perfectly. Caveats:

- Comments always have the authorship of the Azure token owner (the API doesn't allow you to change it).
- Tracker information is not used in Azure. We add it in a table at the bottom of the work item.
- Redmine markdown is not 100% standard compliant (or at least not with the python markdown module).
  You may lose a bit of the formatting
