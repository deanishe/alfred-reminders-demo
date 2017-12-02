Alfred Reminders Demo
=====================

A simple (and heavily-commented) demo workflow for [Alfred][alfredapp] that shows and filters your Reminders.app lists. Actioning a list will open it in Reminders.app.

The default keyword is `.rem`.


How it works
------------

The workflow uses AppleScript to talk to Reminders.app and a Script Filter to display the lists to the user.

As talking to other applications via AppleScript is *very* slow, and Alfred runs Script Filters (more or less) every time the query changes, the workflow caches the reminders list for some minutes.

The workflow demonstrates a common idiom in workflows of working from the cached data while fetching fresh data from Reminders.app in the background. It uses Alfred 3's `rerun` feature to refresh the results as soon as the new data has been fetched from Reminders.app.

It also demonstrates how to use [Alfred-Workflow's][aw] API for [updating your workflow from GitHub releases][self-update].

Configuration
-------------

By default, the workflow caches the list of reminders for 10 minutes. You can adjust this setting in the workflow's configuration sheet (open the workflow in Alfred Preferences and hit the `[𝒙]` button) by changing the value of the `CACHE_MINUTES` variable.

Lists from all accounts are shown by default. You can change this by editing the `settings.json` file and adding the names of the accounts you'd like to use to the `accounts` array:

```json
{
  "accounts": ["iCloud", "On My Mac"]
}
```

You can quickly access this file by entering `.rem workflow:opendata` in Alfred, which will open the workflow's data directory in Finder.


Other stuff
-----------

This workflow is based on [Alfred-Workflow][aw].


[alfredapp]: https://www.alfredapp.com/
[aw]: http://www.deanishe.net/alfred-workflow/
[self-update]: http://www.deanishe.net/alfred-workflow/guide/update.html
