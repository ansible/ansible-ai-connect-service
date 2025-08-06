# Ansible AI Connect Chatbot UI

## Build from source

To start building the "Chatbot" project, you're going to need:

- node (`18.20.0` was used for development)
- npm (`10.5.0` was used for development)

For installing dependencies, **make sure that the current directory
is the `ansible_ai_connect_chatbot` sub-directory first**:
```commandline
 cd (your_git_work_directory)/ansible-ai-connect-service/ansible_ai_connect_chatbot
```

and run

```commandline
npm install
```

## Available Scripts

### npm start

Runs the app in the development mode. In the developing mode,
the UI attempts to connect to the local chatbot service
`http://localhost:8080/v1/query`.  If you need to connect
to a different URL, edit `useChatbot.ts`.

### npm run build

Builds bundled javascript/css files.

The bundled javascript/css files are copied to
`../ansible_ai_connect/main/static/chatbot` and the
`index.html` file is copied to
`../ansible_ai_connect/main/templates/chatbot/`.

### npm run test

Executes unit tests.

### npm run coverage

Executes unit tests with code coverage reports.
The text version of the report is shown on the console,
while the HTML version and the `lcov.info` file are saved
in the `coverage` sub-directory.

## Test Chatbot in Local environment

**Chatbot is enabled when all of
the following three parameters are defined:**

1. `ModelPipelineChatBot.config.inference_url` URL of the chat service to be used.
2. `ModelPipelineChatBot.config.model_id` Default AI model. It should be
one of models defined in the configuration used by the chat service.
3. `CHATBOT_DEFAULT_PROVIDER` Default AI model provider. It should be
   one of providers defined in the configuration used by the chat service.

```commandline
CHATBOT_DEFAULT_PROVIDER=wisdom
```
```json
{
  "ModelPipelineChatBot": {
    "config": {
      "inference_url": "http://127.0.0.1:8080",
      "model_id": "granite-3.3-8b-instruct"
    }
  }
}
```

## Releasing and publishing

Run the following GH workflows, in order:

1.- [AAP Chatbot - Release](../.github/workflows/ui_release_aap_chatbot.yml)
It validates the package by running tests, if successful, creates a new Pull Request with the package information.

2.- [AAP Chatbot - Publish](../.github/workflows/ui_publish_aap_chatbot.yml)
Should be run just after releasing. It validates the package by running tests, if successful, it builds, assembles and publishes the new [package version into npmjs](https://www.npmjs.com/package/@ansible/ansible-ai-connect-chatbot?activeTab=versions).

NOTE: Split the whole process into two different workflows so it gives a bit more flexibility on how to release and when to publish.
NOTE: Based on the [npmjs guideline for publishing new packages](https://docs.npmjs.com/updating-your-published-package-version-number).
