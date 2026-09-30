# Privacy Policy — jobhunt-ops

jobhunt-ops is a personal, self-hosted job-search tool. Each person runs
their own instance against their own accounts. There is no hosted service,
no telemetry, and no third party receiving data.

## Google user data

When you (the instance owner) connect Google APIs:

- **Gmail** is accessed with the readonly scope only. The tool reads message
  metadata and text from your own mailbox to surface job-application updates
  and unanswered recruiter email to you. It cannot send, modify, label, or
  delete mail. Message content is processed locally and is not stored beyond
  a local SQLite database of thread references on your own machine.
- **Google Sheets** access is used solely to write your own job-pipeline
  data into spreadsheets you own and designate.

All credentials (OAuth client files and tokens) are stored locally on your
own machines, are excluded from version control, and are never transmitted
anywhere except to Google's APIs.

## Data sharing and retention

No data leaves your own machines and accounts. Delete your data by deleting
your local data directory and revoking the app's access at
https://myaccount.google.com/permissions.

## Contact

Open an issue on this repository.
