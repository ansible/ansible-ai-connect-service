# Ansible AI Connect "Admin Portal"

> **Warning:** `package.json homepage` setting.
>
> The `homepage` variable is set to `static/console` to replicate deployment within Django that uses its `static` loader mechanism to expose resources on the `<root>/static` context. The React "Admin Portal" is further exposed on the `console` leaf.  This allows a separation of Django and React applications.
>
> Change it at your peril!

## Build from source

To start building the "Admin Portal" project, you're going to need:

- Node `18.0.0` or higher
- npm `7.0.0` or higher

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.

Two entry-points are configured:

#### Admin Portal

Open [http://localhost:8888/console](http://localhost:8888/console) to view the Admin Portal in the browser.\
This uses a mock TypeScript service and not the _real_ Django service.

The page will reload if you make edits.\
You will also see any lint errors in the console.

#### [Access] Denied

Open [http://localhost:8888/static/console/denied.html](http://localhost:8888/static/console/denied.html) to view the alternative application that is served if the User lacks certain access permissions ("Organisation Administrator" and "Ansible Lightspeed License") but was able to log in and authenticate.

### `npm run build`

Builds the app for production to the `ansible_wisdom/main/static/console` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

## Running the "Admin Portal" with Django locally

If you want to integrate the "Admin Portal" into the Django application launched with `manage.py runserver` you need to ensure the React/TypeScript code is compiled and linked to Django's path.

This can be accomplished using `make admin-portal-bundle`.

## Packing into Docker images

The `wisdom-service.Containerfile` is configured to compile and link the "Admin Portal" into the container image. This is used by both the GitHub Action `Build_Push_Image.yml`, `make build-wisdom-container` and `make docker-compose`.

Container images built by our Continuous Integration pipeline on GitHub should therefore be pre-configured to include the "Admin Portal".
