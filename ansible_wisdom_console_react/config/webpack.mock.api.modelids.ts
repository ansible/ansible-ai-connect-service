const webpackMockServer = require("webpack-mock-server");
export default webpackMockServer.add((app, helper) => {

    const ORG_ID = 'org-id';
    const MODEL_ID_FIELD = 'model_id';
    const modelIds = new Map<string, { model_id: string, last_update: Date }>();

    app.get("/api/v0/wca/modelid/",
        (_req, res) => {
            if (modelIds.has(ORG_ID)) {
                res.json(modelIds.get(ORG_ID));
            } else {
                res.sendStatus(404);
            }
        });

    app.get("/api/v0/wca/modelid/test/",
        (_req, res) => {
            if (!modelIds.has(ORG_ID)) {
                res.sendStatus(404);
            } else {
                const data = modelIds.get(ORG_ID);
                const modelId = data[MODEL_ID_FIELD];
                if (modelId === "error-test") {
                    // Emulate a server-side error
                    throw new Error("An error occurred. Oops.");
                }
                if (modelId === "invalid-test") {
                    // Emulate an invalid Model Id
                    res.sendStatus(400);
                }
            }
            res.sendStatus(200);
        });

    app.post("/api/v0/wca/modelid/",
        (_req, res) => {
            const modelId = _req.body['model_id'];
            if (modelId === "error") {
                // Emulate a server-side error
                throw new Error("An error occurred. Oops.");
            }
            if (modelId === "invalid") {
                // Emulate an invalid Model Id
                res.sendStatus(400);
            }
            const entry = {model_id: modelId, last_update: new Date()};
            modelIds.set(ORG_ID, entry);
            res.sendStatus(200);
        });

})
