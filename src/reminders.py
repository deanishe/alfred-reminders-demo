#!/usr/bin/python
# encoding: utf-8
#
# Copyright (c) 2016 Dean Jackson <deanishe@deanishe.net>
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2016-03-12
#


"""reminders.py [options] <command> [<query>]

Show Reminders.app lists. Open app with specified list selected.

Usage:
    reminders.py list [<query>]
    reminders.py open <list>
    reminders.py (-h|--version)

Options:
    --version      Show version number and exit.
    -h, --help     Show this message and exit.

"""

from __future__ import print_function, unicode_literals, absolute_import


from collections import namedtuple
import subprocess
import sys

from workflow import Workflow, ICON_WARNING

log = None


# Allow user to specify only certain accounts to consider,
# e.g. "iCloud" or "On My Mac".
DEFAULT_SETTINGS = {
    'accounts': [],
}

UPDATE_SETTINGS = {
    'github_slug': 'deanishe/alfred-reminders-demo',
}
HELP_URL = 'https://github.com/deanishe/alfred-reminders-demo/'


#                            oo            dP
#                                          88
# .d8888b. .d8888b. 88d888b. dP 88d888b. d8888P .d8888b.
# Y8ooooo. 88'  `"" 88'  `88 88 88'  `88   88   Y8ooooo.
#       88 88.  ... 88       88 88.  .88   88         88
# `88888P' `88888P' dP       dP 88Y888P'   dP   `88888P'
#                               88
#                               dP

AS_LISTS = """
(*
Output a list of the individual lists in Reminders.app
Each line is a tab-separated sequence of:

Account Name, List Name, List ID
*)
property tabChar : (ASCII character 9)
tell application "Reminders"
    set output to ""
    repeat with theAccount in accounts
        set accName to (name of theAccount)
        repeat with theList in lists of theAccount
            set listName to missing value
            set listId to missing value
            try
                set listName to (name of theList)
                set listId to (id of theList)
            on error errMsg number errNo
                log "[" & (errNo as text) & "] " & errMsg
            end try
            if listName is not missing value and listId is not missing value then
                if output is not "" then
                    set output to output & linefeed
                end if
                set output to output & accName & tabChar & listName & tabChar & listId
            end if
        end repeat
    end repeat
    return output
end tell
"""


AS_OPEN = """
(*
Open list with the specified ID in Reminders.app.
*)
on openList(listId)
    tell application "Reminders"
        set ok to false
        repeat with theList in lists
            if (id of theList) is listId then
                show theList
                activate
                set ok to true
                exit repeat
            end if
        end repeat
    end tell
    return ok
end openList

on run (argv)
    set listId to first item of argv
    set ok to openList(listId)
    if ok is not true then
        return "Failed to open list " & listId
    end if
end run

"""


# dP                dP
# 88                88
# 88d888b. .d8888b. 88 88d888b. .d8888b. 88d888b. .d8888b.
# 88'  `88 88ooood8 88 88'  `88 88ooood8 88'  `88 Y8ooooo.
# 88    88 88.  ... 88 88.  .88 88.  ... 88             88
# dP    dP `88888P' dP 88Y888P' `88888P' dP       `88888P'
#                      88
#                      dP

# The remarkably complex data model
List = namedtuple('List', 'account_name list_name list_id')


def run_as(script, *args):
    """Run an AppleScript and return the output.

    Args:
        script (str): The AppleScript to run.
        *args: Additional arguments to `/usr/bin/osascript`.

    Returns:
        str: The output (on STDOUT) of the executed script.
    """
    cmd = ('/usr/bin/osascript', '-l', 'AppleScript', '-e', script) + args
    return subprocess.check_output(cmd)


def get_reminders_lists():
    """Get list details from Reminders.app.

    Returns:
        list: Sequence of `List` tuples.
    """
    output = wf.decode(run_as(AS_LISTS))

    lists = []

    for line in [s.strip() for s in output.split('\n') if s.strip()]:
        cells = line.split('\t')
        if len(cells) != 3:
            log.warning('Invalid line : %r', line)
            continue
        lists.append(List(*cells))

    return lists


def open_reminders_list(list_id):
    """Open the specified list in Reminders.app.

    Args:
        list_id (str): ID of the Reminders list.

    Raises:
        ValueError: Raised if list can't be opened.
    """
    err = wf.decode(run_as(AS_OPEN, list_id))
    if err:
        raise ValueError(err)


#                     dP   oo
#                     88
# .d8888b. .d8888b. d8888P dP .d8888b. 88d888b. .d8888b.
# 88'  `88 88'  `""   88   88 88'  `88 88'  `88 Y8ooooo.
# 88.  .88 88.  ...   88   88 88.  .88 88    88       88
# `88888P8 `88888P'   dP   dP `88888P' dP    dP `88888P'

def do_list(wf, args):
    """List/filter Reminders.app lists in Alfred.

    Args:
        wf (workflow.Workflow): Active Workflow object.
        args (docopt.Args): Script arguments parsed by `docopt`.
    """
    query = wf.decode(args.get('<query>') or "")

    # Load lists from cache or Reminders.app
    lists = wf.cached_data('reminders-lists', get_reminders_lists, max_age=10)

    # If `accounts` are set in `settings.json`, only show lists from
    # those accounts. Otherwise, show the lists from all accounts.
    accounts = wf.settings.get('accounts', [])
    if accounts:
        lists = [l for l in lists if l.account_name in accounts]

    # Filter lists by query on list name.
    if query:
        lists = wf.filter(query, lists, lambda l: l.list_name, min_score=30)

    # No lists found or no lists match `query`
    if not lists:
        wf.add_item('No matching lists',
                    'Try a different query.',
                    icon=ICON_WARNING)

    # Generate results for Alfred
    for l in lists:
        wf.add_item(l.list_name,
                    '{} > {}'.format(l.account_name, l.list_name),
                    # We'll pass the ID to the follow-up action
                    # (this script called with `open`) to avoid issues
                    # with multiple lists having the same name.
                    arg=l.list_id,
                    valid=True,
                    uid=l.list_id,
                    copytext=l.list_name)

    # Send XML to Alfred
    wf.send_feedback()


def do_open(wf, args):
    """Open the specifed list in Reminders.app.

    Args:
        wf (workflow.Workflow): Active Workflow object.
        args (docopt.Args): Script arguments parsed by `docopt`.
    """
    list_id = args.get('<list>')
    log.debug('Opening list %r ...', list_id)
    open_reminders_list(list_id)


def main(wf):
    """Run the workflow.

    Args:
        wf (workflow.Workflow): Active Workflow object.
    """
    from docopt import docopt

    # Parse command-line arguments and call appropriate
    # command function.
    args = docopt(__doc__, wf.args, version=wf.version)

    log.debug('args=%r', args)

    if args.get('list'):
        return do_list(wf, args)

    if args.get('open'):
        return do_open(wf, args)


if __name__ == '__main__':
    wf = Workflow(
        default_settings=DEFAULT_SETTINGS,
        update_settings=UPDATE_SETTINGS,
        help_url=HELP_URL,
    )
    log = wf.logger
    sys.exit(wf.run(main))
