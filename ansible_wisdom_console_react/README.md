# Ansible Lightspeed Console UI

> **Warning:** `package.json homepage` setting.
>
> The `homepage` variable is set to `static/console` to replicate deployment within Django that uses its `static` loader mechanism to expose resources on the `<root>/static` context. The React Console UI is further exposed on the `console` leaf.  This allows a separation of Django and React applications.
>
> Change it at your peril!

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000/console](http://localhost:3000/console) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm run build`

Builds the app for production to the `ansible_wisdom/main/static/console` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.
