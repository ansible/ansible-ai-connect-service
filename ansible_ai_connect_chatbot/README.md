# Ansible AI Connect Chatbot

## Build from source

To start building the "Admin Portal" project, you're going to need:

- node (`18.20.0` was used for development)
- npm (`10.5.0` was used for development)

For installing dependencies, run

```commandline
npm install
```

## Available Scripts

### npm start

Runs the app in the development mode. In the developing mode,
the UI attempts to connect to the local chatbot service
`http://localhost:8080/v1/query`.  If you need to connect
to a differnt URL, edit `useChatbot.ts`.

### npm run build

Builds bundled javascript/css files.

The bundled javascript/css files are copied to
`../ansible_ai_connect/main/static/chatbot` and the
`index.html` file is copied to
`../ansible_ai_connect/main/templates/chatbot/`.

### npm run test

Executes unit tests.

### npm run coverage

Executes unit tests with code coverage reports. A text report are
displayed on console and an HTML report is saved in the `coverage`
subdirectory.

## Test Chatbot in Local environment

Chatbot is enabled when the following three environment variables
are defined:

1. `CHATBOT_URL` URL of the chat service to be used.
2. `CHATBOT_DEFAULT_PROVIDER` Default AI model provider. It should be
one of providers defined in the configuration used by the chat service.
3. `CHATBOT_DEFAULT_MODEL` Default AI model. It should be
one of models defined in the configuration used by the chat service.

```commandline
CHATBOT_URL=http://127.0.0.1:8080
CHATBOT_DEFAULT_PROVIDER=wisdom
CHATBOT_DEFAULT_MODEL=granite-8b
```

You also need to configure Red Hat SSO authentication on your local
AI Connect service.
