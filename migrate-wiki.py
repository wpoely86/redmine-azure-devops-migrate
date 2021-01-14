#!/usr/bin/env python3

import json
import re
import sys


def main():
    if len(sys.argv) != 3:
        print("Need 2 arguments: <issue_map.json> <file.md>")

    # load issue map
    with open(sys.argv[1], "r") as json_in:
        issue_map = json.load(json_in)

    issue_re = re.compile("#(?P<id>[0-9]+)")

    with open(sys.argv[2], "r") as md_in:
        md_file_in = md_in.read()

    md_file_out = md_file_in

    for hit in issue_re.finditer(md_file_in):
        issue = hit.group("id")
        if issue not in issue_map:
            continue
        print(f"Found one {hit.group(0)} in {sys.argv[2]}, mapping to {issue_map[issue][0]}")
        md_file_out = re.sub(hit.group(0), f"#{issue_map[issue][0]}", md_file_out)

    with open(sys.argv[2], "w") as md_out:
        md_out.write(md_file_out)


if __name__ == "__main__":
    main()
