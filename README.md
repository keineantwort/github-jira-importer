# github-jira-importer
 
This script imports JIRA issues from an export from JIRA 8.0.0 to any GitHub repository. 
I will not maintain this script, but feel free to fork this repo.

## usage

```
py main.py --github_token=<token> --github_repo=<github_account>/<repo> --github_user=<assignee username> -v <file>
```

## example output

```
Importing into "keineantwort/github-jira-importer" from "test.xml"
importing: ...
parsed 3 Issues
... with 3 issues
... with 2 milestones
... with 2 types
... with 2 statuses
... with 2 resolutions
... with 1 priorities
... with 0 components
... with 2 issuesWithLinks
... with 2 closedIssues
SolidValue(solidValueId=0, title='3.6.8') created as Milestone(title="3.6.8", number=1)
SolidValue(solidValueId=1, title='3.6.7') created as Milestone(title="3.6.7", number=2)
types: "SolidValue(solidValueId='6', title='Email')" created as Label(name="Email")
!!! types: "Bug" already exists as Label(name="bug")
priorities: "SolidValue(solidValueId='3', title='Schwer')" created as Label(name="prio Schwer")
resolutions: "SolidValue(solidValueId='-1', title='Nicht erledigt')" created as Label(name="Nicht erledigt")
resolutions: "SolidValue(solidValueId='10000', title='Fertig')" created as Label(name="Fertig")


creating 3 issues: 
fetching existing issues
Importing: ...

created 3 issues
restoring links for 2 issues: ..

 closing 2 issues with states "['Erledigt', 'Geschlossen']": ..

closed 2 issues
```

## example issues
The result of the example import can be found [here](https://github.com/keineantwort/github-jira-importer/issues).