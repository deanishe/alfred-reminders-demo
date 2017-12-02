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

Show Reminders.app lists in Alfred. Actioning a list opens it in the app.

Usage:
    reminders.py list [<query>]
    reminders.py open <list>
    reminders.py update
    reminders.py (-h|--version)

Options:
    --version      Show version number and exit.
    -h, --help     Show this message and exit.

"""

from __future__ import print_function, absolute_import


from collections import namedtuple
import os
import subprocess
import sys

from workflow import Workflow3, ICON_INFO, ICON_SYNC, ICON_WARNING
from workflow.background import run_in_background, is_running

log = None


# Allow user to specify only certain accounts to consider,
# e.g. "iCloud" or "On My Mac".
DEFAULT_SETTINGS = {
    'accounts': [],
}

# The GitHub repo from whose releases newer versions of the workflow
# can be downloaded.
UPDATE_SETTINGS = {
    'github_slug': 'deanishe/alfred-reminders-demo',
}

# Online docs for the workflow. This URL is shown in the debugger/log
# if the workflow encounters an error.
HELP_URL = 'https://github.com/deanishe/alfred-reminders-demo/'

# Name of cache file
CACHE_NAME = 'reminders'
# How long to cache the reminders list for. The value is read from
# the `CACHE_AGE` workflow variable specified in the workflow
# configuration sheet.
CACHE_AGE = int(os.getenv('CACHE_MINUTES', '10')) * 60


#                            oo            dP
#                                          88
# .d8888b. .d8888b. 88d888b. dP 88d888b. d8888P .d8888b.
# Y8ooooo. 88'  `"" 88'  `88 88 88'  `88   88   Y8ooooo.
#       88 88.  ... 88       88 88.  .88   88         88
# `88888P' `88888P' dP       dP 88Y888P'   dP   `88888P'
#                               88
#                               dP

# AppleScript to fetch lists from Reminders.app and print them as
# tab-separated values. JXA would be *much* better for this, as it
# can output JSON, but unfortunately the JXA support in Reminders.app
# is absolute dog shit.
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

# AppleScript to tell Reminders.app to open a specific list.
# The ID of the list is passed as a command-line argument when calling
# the script.
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
        unicode: The output (on STDOUT) of the executed script.
    """
    args = [s.encode('utf-8') for s in args if isinstance(s, unicode)]
    cmd = ['/usr/bin/osascript', '-l', 'AppleScript', '-e', script] + args
    return wf.decode(subprocess.check_output(cmd))


def get_reminders_lists():
    """Get list details from Reminders.app.

    Executes the ``AS_LISTS`` AppleScript and parses the results.

    Returns:
        list: Sequence of `List` tuples.
    """
    output = run_as(AS_LISTS)

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
        list_id (unicode): ID of the Reminders list.

    Raises:
        ValueError: Raised if list can't be opened.
    """
    err = run_as(AS_OPEN, list_id)
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
    query = args.get('<query>') or u""

    # --------------------------------------------------------
    # Workflow update

    # Flag to prevent adding UIDs to results. Alfred sorts results
    # based on the UID, so disabling them ensures that results
    # are shown in the order you emit them.
    send_uids = True

    # Show a message if an update is available and user hasn't
    # entered a query. If there is a query, the user probably isn't
    # interested in updating right now...
    if wf.update_available and not query:
        send_uids = False
        wf.add_item('A new version of the workflow is available',
                    u'↩ or ⇥ to install the update',
                    autocomplete='workflow:update',
                    valid=False,
                    icon=ICON_INFO)

    # --------------------------------------------------------
    # Load data

    # Trigger update if cache is too old or doesn't exist
    if not wf.cached_data_fresh(CACHE_NAME, max_age=CACHE_AGE):
        run_in_background('update', ['/usr/bin/python', sys.argv[0], 'update'])

    # Tell Alfred to run the Script Filter again in 0.5 seconds if
    # list of reminders is currently being updated
    if is_running('update'):
        wf.rerun = 0.5

    # Load lists from cache & show a "loading" message if there are
    # not yet any data in the cache.
    lists = wf.cached_data(CACHE_NAME, None, max_age=0)
    if lists is None:
        wf.add_item(u'Loading lists from Reminders.app …',
                    u'Results will refresh momentarily',
                    valid=False,
                    icon=ICON_SYNC)
        wf.send_feedback()
        return

    # --------------------------------------------------------
    # Filter lists

    # If `accounts` are set in `settings.json`, only show lists from
    # those accounts. Otherwise, show the lists from all accounts.
    accounts = wf.settings.get('accounts', [])
    if accounts:
        lists = [l for l in lists if l.account_name in accounts]

    # Filter against user query if there is one
    if query:
        lists = wf.filter(query, lists, lambda l: l.list_name, min_score=30)

    # --------------------------------------------------------
    # Generate results for Alfred

    # No lists found or no lists match `query`
    # It's a good idea to return a "no results" message, as if
    # your Script Filter returns no items, Alfred will show its fallback
    # searches. This isalso what it does when your workflow fails, so
    # sending a "no results" item makes it clear to the user that
    # the workflow didn't fail.
    if not lists:
        wf.add_item('No matching lists',
                    'Try a different query.',
                    icon=ICON_WARNING)

    for l in lists:
        wf.add_item(l.list_name,
                    u'{} > {}'.format(l.account_name, l.list_name),
                    # We'll pass the ID to the follow-up action
                    # (this script called with `open`) to avoid issues
                    # with multiple lists having the same name.
                    arg=l.list_id,
                    valid=True,
                    uid=l.list_id if send_uids else None,
                    copytext=l.list_name)

    # Send JSON to Alfred
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


def do_update(wf, args):
    """Fetch lists from Reminders.app and cache them.

    Args:
        wf (workflow.Workflow): Active Workflow object.
        args (docopt.Args): Script arguments parsed by `docopt`.
    """
    log.info('[update] fetching lists from Reminders.app ...')
    lists = get_reminders_lists()
    for l in lists:
        log.debug(l)
    wf.cache_data(CACHE_NAME, lists)
    log.info('[update] %d lists(s) cached', len(lists))


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

    if args.get('update'):
        return do_update(wf, args)


if __name__ == '__main__':
    wf = Workflow3(
        default_settings=DEFAULT_SETTINGS,
        update_settings=UPDATE_SETTINGS,
        help_url=HELP_URL,
    )
    log = wf.logger
    sys.exit(wf.run(main))
