import {delay, DELAY_MS, ORG_ID} from './webpack.mock.globals';

const webpackMockServer = require("webpack-mock-server");
export default webpackMockServer.add((app, helper) => {

    const MODEL_ID_FIELD = 'model_id';
    const modelIds = new Map<string, { model_id: string, last_update: Date }>();

    app.get("/api/v0/wca/modelid/",
        async (_req, res) => {
            await delay(DELAY_MS);
            if (modelIds.has(ORG_ID)) {
                res.json(modelIds.get(ORG_ID));
            } else {
                res.sendStatus(404);
            }
        });

    app.get("/api/v0/wca/modelid/test/",
        async (_req, res) => {
            await delay(DELAY_MS);
            if (!modelIds.has(ORG_ID)) {
                res.sendStatus(404);
                return;
            } else {
                const data = modelIds.get(ORG_ID);
                const modelId = data[MODEL_ID_FIELD];
                if (modelId === "error-test") {
                    // Emulate a server-side error
                    res.sendStatus(500);
                    return;
                }
                if (modelId === "invalid-test") {
                    // Emulate an invalid Model Id
                    res.sendStatus(400);
                    return;
                }
            }
            res.sendStatus(200);
        });

    app.post("/api/v0/wca/modelid/",
        async (_req, res) => {
            await delay(DELAY_MS);
            const modelId = _req.body['model_id'];
            if (modelId === "error") {
                // Emulate a server-side error
                res.sendStatus(500);
                return;
            }
            if (modelId === "invalid") {
                // Emulate an invalid Model Id
                res.sendStatus(400);
                return;
            }
            const entry = {model_id: modelId, last_update: new Date()};
            modelIds.set(ORG_ID, entry);
            res.sendStatus(200);
        });

})
