import {
  delay,
  DELAY_MS,
  ERROR_DESCRIPTION,
  ORG_ID,
} from "./webpack.mock.globals";

const webpackMockServer = require("webpack-mock-server");

export default webpackMockServer.add((app, helper) => {
  const KEY_FIELD = "key";
  const MODEL_ID_FIELD = "model_id";
  const LAST_UPDATED_FIELD = "last_update";

  const keys = new Map<string, { key: string; last_update: Date }>();
  const modelIds = new Map<string, { model_id: string; last_update: Date }>();

  //API KEY RELATED ENDPOINTS
  app.get("/api/v1/wca/apikey/", async (_req, res) => {
    await delay(DELAY_MS);
    if (keys.has(ORG_ID)) {
      // Key response only contains the Last Updated field
      const data = keys.get(ORG_ID);
      res.json({ last_update: data[LAST_UPDATED_FIELD] });
    } else {
      res.json({});
    }
  });

  app.get("/api/v1/wca/apikey/test/", async (_req, res) => {
    await delay(DELAY_MS);
    if (!keys.has(ORG_ID)) {
      res.sendStatus(404);
      return;
    } else {
      const data = keys.get(ORG_ID);
      const key = data[KEY_FIELD];
      if (key === "error-test") {
        // Emulate a server-side error
        res.status(500).json({ detail: ERROR_DESCRIPTION });
        return;
      }
      if (key === "invalid-test") {
        // Emulate an invalid API Key
        res.sendStatus(400);
        return;
      }
    }
    res.sendStatus(200);
  });

  app.post("/api/v1/wca/apikey/", async (_req, res) => {
    await delay(DELAY_MS);
    const key = _req.body["key"];
    if (key === "error") {
      // Emulate a server-side error
      res.status(500).json({ detail: ERROR_DESCRIPTION });
      return;
    }
    if (key === "invalid") {
      // Emulate an invalid API Key
      res.sendStatus(400);
      return;
    }
    const entry = { key: key, last_update: new Date() };
    keys.set(ORG_ID, entry);
    res.sendStatus(200);
  });

  app.delete("/api/v1/wca/apikey/", async (_req, res) => {
    await delay(DELAY_MS);
    if (keys.has(ORG_ID)) {
      keys.delete(ORG_ID);
      if (modelIds.has(ORG_ID)) {
        modelIds.delete(ORG_ID);
      }
      res.sendStatus(204);
    } else {
      res.sendStatus(400);
    }
  });

  //MODEL ID RELATED ENDPOINTS
  app.get("/api/v1/wca/modelid/", async (_req, res) => {
    await delay(DELAY_MS);
    if (modelIds.has(ORG_ID)) {
      res.json(modelIds.get(ORG_ID));
    } else {
      res.json({});
    }
  });

  app.get("/api/v1/wca/modelid/test/", async (_req, res) => {
    await delay(DELAY_MS);
    if (!modelIds.has(ORG_ID)) {
      res.sendStatus(404);
      return;
    } else {
      const data = modelIds.get(ORG_ID);
      const modelId = data[MODEL_ID_FIELD];
      if (modelId === "error-test") {
        // Emulate a server-side error
        res.status(500).json({ detail: ERROR_DESCRIPTION });
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

  app.post("/api/v1/wca/modelid/", async (_req, res) => {
    await delay(DELAY_MS);
    const modelId = _req.body[MODEL_ID_FIELD];
    if (modelId === "error") {
      // Emulate a server-side error
      res.status(500).json({ detail: ERROR_DESCRIPTION });
      return;
    }
    if (modelId === "invalid") {
      // Emulate an invalid Model Id
      res.sendStatus(400);
      return;
    }
    const entry = { model_id: modelId, last_update: new Date() };
    modelIds.set(ORG_ID, entry);
    res.sendStatus(200);
  });
});
