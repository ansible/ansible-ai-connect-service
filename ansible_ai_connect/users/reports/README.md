# Ansible AI Connect :: User Trials reports


This folder contains code to generate "User Trials" reports:
- "Trials" a report of Users starting a trial
- "Marketing" a report of Users starting a trial that have accepted to receive marketing

## Configuration

Set `settings.ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN` to one of the following. Related additional configuration should be set in `settings.ANSIBLE_AI_ONE_CLICK_REPORTS_CONFIG`:
- `none` (default) No reports are generated


- `stdout` Reports are logged (to the `INFO` level)


- `slack-webhook` Reports are written to a Slack Channel
  ```json
  {
    "slack-webhook-url": "<webhook url>"
  }
  ```
  The "Incoming WebHooks" application should be added to the target channel. See https://redhat-external.slack.com/apps/A0F7XDUAZ-incoming-webhooks


- `slack-webapi` Reports are written to a Slack Application
  ```json
  {
    "slack-token": "<api token>",
    "slack-channel-id": "<channel id>"
  }
  ```
- `google-drive` Reports are written to a Google Drive folder
  ```json
  {
    "gdrive-folder-name": "<folder name>",
    "gdrive-project-id": "<project id>>",
    "gdrive-private-key-id": "<private key id>",
    "gdrive-private-key": "<private key>",
    "gdrive-client-email": "<client email>",
    "gdrive-client-id": "<client id>",
  }
  ```
  A Google Service Account will need to be created and the target folder shared with the generated account. The values in the report configuration can be copied from the JSON credentials file generated when creating the Service Account. See https://source.redhat.com/departments/it/devit/it-infrastructure/itcloudservices/itpubliccloudpage/cloud/docs/consumer/gcp_accessing_google_workspace_services_using_gcp_service_accounts
