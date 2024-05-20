#!/usr/bin/env python3

# this script will download a redmine wiki and create a set of files
# and directories that can be copied to the git repo of a Azure DevOps wiki

import os
import re

from redminelib import Redmine

# url to the redmine
redmine_url = "https://some.redmine.site.somewhere"
# api key for redmine
redmine_key = "REPLACE_WITH_REDMINE_API_KEY"


def main():
    redmine = Redmine(redmine_url, key=redmine_key)

    a_project_id = "some_project"
    project = redmine.project.get(a_project_id)

    all_pages = dict()

    # first, build a dict with all pages and their full path
    for page in project.wiki_pages:
        print(f"{page.title}")
        comments = getattr(page, "comment", None)
        uploads = getattr(page, "uploads", [])
        if comments or uploads:
            print(f"{page.title} has comments and/or attachments which we ignore")

        parent = getattr(page, "parent", None)
        full_path = []
        while parent:
            full_path.append(parent.title)
            parent_page = redmine.wiki_page.get(parent.title, project_id=a_project_id)
            parent = getattr(parent_page, "parent", None)
        full_path.reverse()

        all_pages[page.title] = (page, full_path)

    for current in all_pages:
        path = all_pages[current][1]
        page = all_pages[current][0]
        if path:
            os.makedirs(os.sep.join(path), exist_ok=True)

        output_file = os.path.join(os.sep.join(path), f"{page.title}.md")
        content = page.text

        for link in re.finditer(r"\[\[(?P<link>[^]]+)\]\]", content):
            link_new = link.group("link").replace(" ", "_").replace("/", "")
            # we want uppercase on first letter
            link_new = link_new[0].upper() + link_new[1:]
            if link_new not in all_pages:
                continue
            new_path = os.path.join(os.sep.join(all_pages.get(link_new)[1]), f"{link_new}.md")
            content = re.sub(rf"\[\[{link.group('link')}\]\]", f"[{link.group('link')}](/{new_path})", content)

        content = re.sub("{{toc}}", "[[_TOC_]]", content)
        with open(output_file, "w") as output:
            output.write(content)


if __name__ == "__main__":
    main()
