#!/usr/bin/env python3

# To use this script, you need to adjust the variables below the imports
# and the redmine issue filter in the main()
#
# It's *not* a fire-and-forgot script but a starting point to migrate your data
# from redmine to azure devops.

import datetime
import json
import os
import re
import tempfile

from redminelib import Redmine
import markdown

from msrest.authentication import BasicAuthentication
from azure.devops.connection import Connection
from azure.devops.v6_0.work_item_tracking import JsonPatchOperation, CommentCreate, Link, CommentUpdate

# will contain the mapping between id in redmine and azure devops,
# it will be dumped in a json file
issue_map = {}
# url to the redmine
redmine_url = "https://some.redmine.site.somewhere"
# api key for redmine
redmine_key = "REPLACE_WITH_REDMINE_API_KEY"
# azure organization
organization = "YOUR_AZURE_DEVOPS_ORGANIZATION"
# the project in azure devops
project = "YOUR_AZURE_DEVOPS_PROJECT"
# azure token
azure_token = "YOUR_AZURE_TOKEN"

# the mapping of redmine to azure states
state_map = {
    "Pending": "To Do",
    "In Progress": "Doing",
    "Completed": "Done",
}

# mapping of redmine usernames to azure devops usernames
author_map = {
    "John Doe": "John F. Doe",
}
# if the user is not in the above dict, use this (put to None to have nobody assigned):
default_user = "John F. Doe"


def fix_redmine_list_formatting(text):
    """
    Redmine markdown can make lists if the
    lists is not preceded by a empty line. The python
    markdown module does not accept this. We try to insert
    newlines before an list
    """
    list_text = text.split("\n")
    list_re = re.compile(r"\s*^[-*]")
    result = [list_text[0]]

    for num, line in enumerate(list_text[1:]):
        # the numbering of num is one-off because we start the enumerate at the second line
        if list_re.search(line) and not list_re.search(list_text[num]):
            result.append("")
        result.append(line)

    return "\n".join(result)


def create_work_item(work_client, issue):
    """
    :param work_client: the azure devops work client interface
    :param issue: a redmine issue
    """
    print(f"Start migration of {issue.id}")
    # we add a link to the original issue in azure devops
    orig_link = Link(
        rel="Hyperlink", url=f"{redmine_url}/issues/{issue.id}", attributes={"comment": "link to original issue"}
    )

    # convert issue markdown to html and add a table with data of the original issue
    footer = f"""\n
| Name | Value |
| ---- | -----: |
| Issue | [{issue.id}]({redmine_url}/issues/{issue.id}) |
| Tracker | { issue.tracker.name} |
| Priority | {issue.priority.name} |
| Author | {issue.author.name} |
| Assigned | {getattr(issue, 'assigned_to', 'Unassigned')} |
"""
    description = markdown.markdown(
        fix_redmine_list_formatting(issue.description) + footer, extensions=["pymdownx.magiclink", "pymdownx.extra"]
    )

    # first create a new workitem for the issue
    new_work_item = [
        JsonPatchOperation(op="Add", path="/fields/System.Tags", value="redmine"),
        JsonPatchOperation(op="Add", path="/relations/-", value=orig_link),
        JsonPatchOperation(op="Add", path="/fields/System.CreatedDate", value=issue.created_on),
        JsonPatchOperation(op="Add", path="/fields/System.Title", value=issue.subject),
        JsonPatchOperation(op="Add", path="/fields/System.Description", value=description),
        # we always create in the 'to do' state and later change it to the real value
        # because it gives errors otherwise...
        JsonPatchOperation(op="Add", path="/fields/System.State", value="To Do"),
    ]

    if str(getattr(issue, "assigned_to", "Unassigned")) in author_map:
        new_work_item.append(
            JsonPatchOperation(op="Add", path="/fields/System.AssignedTo", value=author_map[issue.assigned_to.name])
        )
    elif default_user:
        new_work_item.append(JsonPatchOperation(op="Add", path="/fields/System.AssignedTo", value=default_user))

    # bypass_rules is needed to create issues with a creation date in the past
    result = work_client.create_work_item(
        new_work_item, project, "Issue", bypass_rules=True, suppress_notifications=True
    )

    work_item_id = result.as_dict().get("id")
    issue_map[issue.id] = (work_item_id, result.as_dict().get("url"))

    # migrate the notes/comments on the issue
    for note in issue.journals:
        if not getattr(note, "notes", None):
            continue
        note_text = note.notes + f"\n\n\n*Original author: {note.user.name}*\n\n*Original date: {note.created_on}*"
        comment = CommentCreate(markdown.markdown(note_text, extensions=["pymdownx.magiclink", "pymdownx.extra"]))
        work_client.add_comment(comment, project, work_item_id)

    # migrate attachments:
    # - first download them from redmine
    # - upload it to azure devops
    # - link the upload file to the current work item
    # This is not tested with very large files.
    with tempfile.TemporaryDirectory(suffix=f"-{issue.id}") as tmpdir:
        for attachment in issue.attachments:
            attachment.download(savepath=tmpdir, filename=attachment.filename)
            with open(os.path.join(tmpdir, attachment.filename), "rb") as attachment_file:
                result_attach = work_client.create_attachment(attachment_file, project, file_name=attachment.filename)
            attach_link = Link(
                rel="AttachedFile",
                url=result_attach.as_dict().get("url"),
                attributes={"comment": attachment.description},
            )
            add_attachment_link = [JsonPatchOperation(op="Add", path="/relations/-", value=attach_link)]
            work_client.update_work_item(add_attachment_link, work_item_id, project)

    if issue.status.name in state_map and issue.status.name != "Pending":
        state = JsonPatchOperation(op="Add", path="/fields/System.State", value=state_map[issue.status.name])
        work_client.update_work_item([state], work_item_id, project)

    print(f"Migrated {issue.id} to {work_item_id}: {issue.subject}")


def get_all_comments(work_item_id, work_client):
    """Return a list of all comments on a work item"""
    comment_answer = work_client.get_comments(project, work_item_id)
    comments = comment_answer.as_dict().get("comments", [])

    while comment_answer.continuation_token:
        comment_answer = work_client.get_comments(continuation_token=comment_answer.continuation_token)
        comments.extend(comment_answer.as_dict().get("comments", []))

    return comments


def main():
    redmine = Redmine(redmine_url, key=redmine_key)
    # define a filter/list of the redmine issue you which to migrate
    issues = redmine.issue.filter(
        project_id="some_project",
        status_id="*",
        created_on=">=2017-01-01",
        sort="created_on",
        include="journals,attachments",
    )
    # issues = [redmine.issue.get(x, include='journals,attachments') for x in [1, 2, 4]]

    # Create a connection to the org
    credentials = BasicAuthentication("", azure_token)
    connection = Connection(base_url=f"https://dev.azure.com/{organization}", creds=credentials)

    # Get a client to the work item interface
    work_client = connection.clients_v6_0.get_work_item_tracking_client()

    # create work items + notes + attachments
    for issue in issues:
        create_work_item(work_client, issue)

    # save issue map
    with open(f"issue-mapping-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as json_out:
        json.dump(issue_map, json_out)

    # now create the relations between them
    for issue in issues:
        if not getattr(issue, "parent", None) or issue.id not in issue_map:
            continue
        print(f"Adding link: {issue.parent.id} -> {issue.id}")
        parent_link = Link(rel="System.LinkTypes.Hierarchy-Reverse", url=issue_map[issue.parent.id][1])
        parent_add_link = JsonPatchOperation(op="Add", path="/relations/-", value=parent_link)
        work_client.update_work_item([parent_add_link], issue_map[issue.id][0], project)

    # last, search and replace references to issue/work_items
    issue_re = re.compile("#(?P<id>[0-9]+)")
    for work_item_id, _ in issue_map.values():
        work_item = work_client.get_work_item(work_item_id, project).as_dict()
        new_description = work_item["fields"]["System.Description"]
        update_item = []

        for comment in get_all_comments(work_item_id, work_client):
            new_comment = comment["text"]
            for hit in issue_re.finditer(comment["text"]):
                issue = int(hit.group("id"))
                if issue not in issue_map:
                    continue
                print(f"Found one in {work_item_id}/{comment['id']}: {hit.group(0)} to {issue_map[issue][0]}")
                new_comment = re.sub(hit.group(0), f"#{issue_map[issue][0]}", new_comment)
                related_link = Link(rel="System.LinkTypes.Related", url=issue_map[issue][1])
                if issue_map[issue][0] != work_item_id:
                    update_item.append(JsonPatchOperation(op="Add", path="/relations/-", value=related_link))

            if new_comment != comment["text"]:
                work_client.update_comment(CommentUpdate(text=new_comment), project, work_item_id, comment["id"])

        for hit in issue_re.finditer(work_item["fields"]["System.Description"]):
            issue = int(hit.group("id"))
            if issue not in issue_map or issue_map[issue][0] == work_item_id:
                continue
            print(f"Found one in {work_item_id}: {hit.group(0)} to {issue_map[issue][0]}")
            new_description = re.sub(hit.group(0), f"#{issue_map[issue][0]}", new_description)

            related_link = Link(rel="System.LinkTypes.Related", url=issue_map[issue][1])
            if issue_map[issue][0] != work_item_id:
                update_item.append(JsonPatchOperation(op="Add", path="/relations/-", value=related_link))

        if update_item:
            update_item.append(
                JsonPatchOperation(op="Replace", path="/fields/System.Description", value=new_description)
            )
            work_client.update_work_item(update_item, work_item_id, project)


if __name__ == "__main__":
    main()
