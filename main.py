from github import Github
from lxml import etree
from io import StringIO, BytesIO
from dataclasses import dataclass
from typing import List
import argparse
from markdownify import markdownify as md
import time
import re

LABELS = {
    "types" : {"prefix": "", "color" : "4287f5"},
    "priorities" : {"prefix": "prio ", "color" : "d62424"},
    "components" : {"prefix": "", "color" : "62e36a"},
    "resolutions" : {"prefix": "", "color" : "de52d7"}
}

CLOSED_STATES = ["Erledigt", "Geschlossen"]

@dataclass(eq=True, frozen=True)
class SolidValue:
    solidValueId: int
    title: str

@dataclass
class Comment:
    author: str
    created: str
    text: str

@dataclass
class Link:
    issueKey: str
    description: str

@dataclass
class Issue:
    key: str 
    summary: str
    issuetype: SolidValue
    fixversion: SolidValue
    status: SolidValue
    resolution: SolidValue
    description: str
    priority: SolidValue
    comments: List[Comment]
    components: List[SolidValue]
    links: List[Link]

args = None

values = {
    "issues" : {},
    "milestones" : {},
    "types" : {},
    "statuses" : {},
    "resolutions" : {},
    "priorities" : {},
    "components" : {},
    "issuesWithLinks" : [],
    "closedIssues" : []
}

# 
# Parsing
#
def parseIssues(): 
    tree = etree.parse(args.filename)
    channel = tree.getroot()[0]
    items = values["issues"]

    print("importing: ", end='', flush=True)
    for itemElement in channel.iter("item"):
        issue = parseItem(itemElement)
        if len(issue.links) > 0:
            values["issuesWithLinks"].append(issue)
        if issue.status.title in CLOSED_STATES:
            values["closedIssues"].append(issue)
        items[issue.key] = issue
        print(".", end='', flush=True)
    
    print("\nparsed {} Issues".format(len(items)))
    if args.verbose:
        for value in values:
            print("... with {} {}".format(len(values[value]), value))

def parseItem(itemElement):
    return Issue(itemElement.find(".//key").text, 
                itemElement.find(".//summary").text,
                parseSolidValue(itemElement, "type", values["types"]),
                parseSolidValue(itemElement, "fixVersion", values["milestones"]),
                parseSolidValue(itemElement, "status", values["statuses"]),
                parseSolidValue(itemElement, "resolution", values["resolutions"]),
                itemElement.find(".//description").text,
                parseSolidValue(itemElement, "priority", values["priorities"]),
                parseComments(itemElement),
                parseComponents(itemElement),
                parseLinks(itemElement))

def parseLinks(itemElement):
    issueLinkTypeElements = itemElement.findall(".//issuelinktype")
    links = []

    parent = parseParent(itemElement)
    if parent is not None:
        links.append(parent)

    for issuelinktypeElement in issueLinkTypeElements:
        linksElements = issuelinktypeElement.findall(".//inwardlinks")
        linksElements.extend(issuelinktypeElement.findall(".//outwardlinks"))

        for linkElement in linksElements:
            description = linkElement.get("description")

            for issuekey in linkElement.findall(".//issuekey"):
                links.append(Link(issuekey.text, description))

    return links


def parseComponents(itemElement):
    componentElements = itemElement.findall(".//component")
    components = []
    for componentElement in componentElements:
        components.append(createSolidElement(componentElement, values["components"]))


def parseComments(itemElement):
    commentElements = itemElement.findall(".//comment")
    comments = []
    for commentElement in commentElements:
        comments.append(Comment(commentElement.get("author"),
                                commentElement.get("created"),
                                commentElement.text))
    return comments

def parseParent(itemElement):
    parent = None
    parentElement = itemElement.find(".//parent")
    if parentElement is not None:
        parent = Link(parentElement.text, "is child of")
    return parent

def parseSolidValue(itemElement, name, dict):
    val = None
    valElement = itemElement.find(".//{}".format(name))
    if valElement is not None:
        val = createSolidElement(valElement, dict)
    return val

def createSolidElement(valElement, dict):
    id = len(dict)
    useText = True
    if "id" in valElement.attrib:
        id = valElement.get("id")
        useText = False

    val = SolidValue(id, valElement.text)
    id = val.solidValueId
    if useText:
        id = val.title
    if id not in dict:
        dict[id] = val
    else:
        val = dict[id]
    return val

#
# GitHub creation
#

def createGitHubIssues():
    g = Github(args.github_token)
    
    repo = g.get_repo(args.github_repo)
    milestones = createMilestones(repo)
    labels = createLabels(repo)

    print("\n\ncreating {} issues: ".format(len(values["issues"])), flush=True)
    assignee = g.get_user(args.github_user)
    createdIssues = {}
    print("fetching existing issues")
    allExistingIssues = repo.get_issues(state="all")
    for existingIssue in allExistingIssues:
        summary = existingIssue.title
        m = re.search('IMZP-([0-9]){1,3}', summary)
        if m is not None:
            createdIssues[m.group(0)] = existingIssue

    if len(createdIssues) > 0:
        print("!!!{} issues already exist. Skipping these.".format(len(createdIssues)))
    print("Importing: ", end='', flush=True)
    for issuekey in values["issues"]:
        issue = values["issues"][issuekey]
        if issuekey not in createdIssues:
            summary = "[{}] {}".format(issue.key, issue.summary)
            issueLabels = []
            if issue.issuetype is not None:
                issueLabels.append(labels[issue.issuetype])
            if issue.priority is not None:
                issueLabels.append(labels[issue.priority])
            if issue.resolution is not None:
                issueLabels.append(labels[issue.resolution])
            if issue.components is not None:
                for component in issue.components:
                    issueLabels.append(labels[component])
            
            issueBody = "{}\n\n##################\n\n**IMPORTED FROM JIRA**\n\n".format(md(issue.description))
            
            if issue.fixversion is not None:
                createdIssues[issue.key] = repo.create_issue(summary, body=issueBody, assignee=assignee, milestone=milestones[issue.fixversion], labels=issueLabels)
            else:
                createdIssues[issue.key] = repo.create_issue(summary, body=issueBody, assignee=assignee, labels=issueLabels)
            time.sleep(1)

            # creating comments
            for comment in issue.comments:
                body = "({}) {}:\n{}".format(
                    comment.created,
                    comment.author,
                    md(comment.text)
                )
                createdIssues[issue.key].create_comment(body)
                time.sleep(1)
                print(",", end='', flush=True)
            print(".", end='', flush=True)
            if len(createdIssues) % 10 == 0:
                print("|", end='', flush=True)

    print("\n\ncreated {} issues".format(len(createdIssues)))
    print("restoring links for {} issues: ".format(len(values["issuesWithLinks"])), end='', flush=True)
    for issueWithLinks in values["issuesWithLinks"]:
        githubIssue = createdIssues[issueWithLinks.key]
        body = githubIssue.body
        for link in issueWithLinks.links:
            linkedIssue = createdIssues[link.issueKey]
            body = body + "{} #{}\n".format(link.description, linkedIssue.number)
            githubIssue.edit(body=body)
            time.sleep(1)
            print(".", end='', flush=True)

    print("\n\n closing {} issues with states \"{}\": ".format(len(values["closedIssues"]), CLOSED_STATES), end='', flush=True)
    for closedIssue in values["closedIssues"]:
        githubIssue = createdIssues[closedIssue.key]
        if githubIssue.state != "closed":
            githubIssue.edit(state="closed")
        time.sleep(1)
        print(".", end='', flush=True)
    print("\n\nclosed {} issues".format(len(values["closedIssues"])))

## Labels
def createLabels(repo):
    existingLabels = repo.get_labels()
    labels = {}
    for l in LABELS:
        labelMeta = LABELS[l]
        for v in values[l]:
            val = values[l][v]
            labelName = "{}{}".format(labelMeta["prefix"], val.title)
            existingLabel = findLabel(existingLabels, labelName)
            if existingLabel is None:
                createdLabel = repo.create_label(labelName, labelMeta["color"])
                time.sleep(1)
                if args.verbose:
                    print("{}: \"{}\" created as {}".format(l, val, createdLabel))
                labels[val] = createdLabel
            else:
                print("!!! {}: \"{}\" already exists as {}".format(l, labelName, existingLabel))
                labels[val] = existingLabel
    return labels

def findLabel(list, title):
    val = None
    for l in list:
        if l.name.casefold() == title.casefold():
            return l
    return val

## Milestones
def createMilestones(repo):
    existingMilestones = repo.get_milestones()
    milestones = {}
    for m in values["milestones"]:
        milestone = values["milestones"][m]
        existingMilestone = findMilestone(existingMilestones, milestone.title)
        if existingMilestone is None:
            createdMilestone = repo.create_milestone(title=milestone.title)
            time.sleep(1)
            if args.verbose:
                print("{} created as {}".format(milestone, createdMilestone))
            milestones[milestone] = createdMilestone
        else:
            print("!!! \"{}\" already exists as {}".format(milestone.title, existingMilestone))
            milestones[milestone] = existingMilestone
    return milestones

def findMilestone(list, title):
    val = None
    for m in list:
        if m.title == title:
            return m
    return val
#
# MAIN
#
def parse_args():
    parser = argparse.ArgumentParser(
        description='Imports the Jira issues from the given XML-Export into the given GitHub Repo as Issues.'
    )
    parser.set_defaults(
        verbose=False,
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable additional debug output",
    )
    parser.add_argument(
        '--github_token',
        help="yout GitHub accesstoken",
    )
    parser.add_argument(
        '--github_repo',
        help="the repo to import the issues into like \"mygithub/myrepo\"",
    )
    parser.add_argument(
        '--github_user',
        help="the github user to assign all issues to",
    )
    parser.add_argument(
        'filename',
        type=argparse.FileType('r'),
        help="the XML file, which contains the JIRA issues",
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    if args.verbose:
        print("Importing into \"{}\" from \"{}\"".format(args.github_repo, args.filename.name))
    
    parseIssues()
    createGitHubIssues()
    