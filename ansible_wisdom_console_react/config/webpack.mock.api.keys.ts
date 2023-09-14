import {delay, DELAY_MS, ORG_ID} from './webpack.mock.globals';

const webpackMockServer = require("webpack-mock-server");

export default webpackMockServer.add((app, helper) => {

    const KEY_FIELD = 'key';
    const LAST_UPDATED_FIELD = 'last_update';
    const keys = new Map<string, { key: string, last_update: Date }>();

    app.get("/api/v0/wca/apikey/",
        async (_req, res) => {
            await delay(DELAY_MS);
            if (keys.has(ORG_ID)) {
                // Key response only contains the Last Updated field
                const data = keys.get(ORG_ID);
                res.json({last_update: data[LAST_UPDATED_FIELD]});
            } else {
                res.sendStatus(404);
            }
        });

    app.get("/api/v0/wca/apikey/test/",
        async (_req, res) => {
            await delay(DELAY_MS);
            if (!keys.has(ORG_ID)) {
                res.sendStatus(404);
            } else {
                const data = keys.get(ORG_ID);
                const key = data[KEY_FIELD];
                if (key === "error-test") {
                    // Emulate a server-side error
                    throw new Error("An error occurred. Oops.");
                }
                if (key === "invalid-test") {
                    // Emulate an invalid API Key
                    res.sendStatus(400);
                    return;
                }
            }
            res.sendStatus(200);
        });

    app.post("/api/v0/wca/apikey/",
        async (_req, res) => {
            await delay(DELAY_MS);
            const key = _req.body['key'];
            if (key === "error") {
                // Emulate a server-side error
                throw new Error("An error occurred. Oops.");
            }
            if (key === "invalid") {
                // Emulate an invalid API Key
                res.sendStatus(400);
                return;
            }
            const entry = {key: key, last_update: new Date()};
            keys.set(ORG_ID, entry);
            res.sendStatus(200);
        });

})
