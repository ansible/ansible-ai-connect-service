import {delay, DELAY_MS} from './webpack.mock.globals';

const webpackMockServer = require("webpack-mock-server");

export default webpackMockServer.add((app, helper) => {

    let optOut = false;

    app.get("/api/v0/telemetry/",
        async (_req, res) => {
            await delay(DELAY_MS);
            res.json({optOut: optOut});
        });

    app.post("/api/v0/telemetry/",
        async (_req, res) => {
            await delay(DELAY_MS);
            const _optOut = _req.body['optOut'];
            optOut = _optOut;
            res.sendStatus(200);
        });

})
