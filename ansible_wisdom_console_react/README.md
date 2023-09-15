# Ansible Lightspeed "Admin Portal"

> **Warning:** `package.json homepage` setting.
>
> The `homepage` variable is set to `static/console` to replicate deployment within Django that uses its `static` loader mechanism to expose resources on the `<root>/static` context. The React "Admin Portal" is further exposed on the `console` leaf.  This allows a separation of Django and React applications.
>
> Change it at your peril!

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:8888/console](http://localhost:8888/console) to view it in the browser.\
This uses a mock TypeScript service and not the _real_ Django service.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm run build`

Builds the app for production to the `ansible_wisdom/main/static/console` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

## Running the "Admin Portal" with Django locally

If you want to integrate the "Admin Portal" into the Django application launched with `manage.py runserver` you need to ensure the React/TypeScript code is compiled and linked to Django's path.

This can be accomplished using `make create-application-ui-react`.

## Packing into Docker images

The `wisdom-service.Containerfile` is configured to compile and link the "Admin Portal" into the container image. This is used by both the GitHub Action `Build_Push_Image.yml`, `make build-wisdom-container` and `make docker-compose`.

Ansible Lightspeed container images built by our Continuous Integration pipeline on GitHub should therefore be pre-configured to include the "Admin Portal".
