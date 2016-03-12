Alfred Reminders Demo
=====================

A very simple workflow for [Alfred 2][alfredapp] that shows and filters your Reminders.app lists. Actioning a list will open it in Reminders.app.

The default keyword is `.rem`.

Uses AppleScript to talk to Reminders.app and a Script Filter to display the lists to the user.

By default, the workflow shows lists from all accounts. You can change this by editing the `settings.json` file and adding the names of the accounts you'd like to use to the `accounts` array:

```json
{
  "accounts": ["iCloud", "On My Mac"]
}
```

You can quickly access this file by entering `.rem workflow:opendata` in Alfred, which will open the workflow's data directory in Finder.

This workflow is based on [Alfred-Workflow][aw].


[alfredapp]: https://www.alfredapp.com/
[aw]: http://www.deanishe.net/alfred-workflow/
