# Redmine to Azure DevOps Migration

This repo has a couple of scripts that can help you to migrate from redmine
to Azure DevOps. It is **not** a fire and forgot kind of script but acts as
a starting point for your own migration.

## Issues

The script `migrate.py` will migrate your Redmine issues to Azure DevOps work items.

To use it you have to:

- install the dependencies in `requirements.txt`
- adjust the constants at the top of the script (redmine url, tokens, etc)
- adjust the filter of redmine issue at the top of main()

After that you can try it. I highly recommend to first try it on a test project.

It does not migrate everything perfectly. Caveats:

- Comments always have the authorship of the Azure token owner (the API doesn't allow you to change it).
- Tracker information is not used in Azure. We add it in a table at the bottom of the work item.
- Redmine markdown is not 100% standard compliant (or at least not with the python markdown module).
  You may lose a bit of the formatting

The script will also dump a json file with the mapping between redmine issue ids and azure work item ids.

## wiki

The script `wiki.py` will 'download' all the wiki pages and put them in a directory
structure. This can then be added to the git repo of a Azure DevOps wiki. To find
the git repo for a wiki, read [this](https://docs.microsoft.com/en-us/azure/devops/project/wiki/wiki-create-repo?view=azure-devops&tabs=browser#how-can-i-go-to-the-git-repository).


### change issue numbers

With the script `migrate-wiki.py` you can change the issue references in the wikipages to the
'new' work item id in Azure DevOps. You need to use the json file dumped by the issue migration
script. Example:

```
find -name '*.md' -print0 | xargs -L1 -0 python3 migrate-wiki.py issue-mapping.json
```
