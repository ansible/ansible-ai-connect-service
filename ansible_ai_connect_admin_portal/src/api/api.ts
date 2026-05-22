import { TelemetryRequest, WcaKeyRequest, WcaModelIdRequest } from "./types";
import axios from "axios";

export const API_TELEMETRY_PATH = "/api/v1/telemetry/";
export const API_WCA_KEY_PATH = "/api/v1/wca/apikey/";
export const API_WCA_MODEL_ID_PATH = "/api/v1/wca/modelid/";
export const API_WCA_KEY_TEST_PATH = "/api/v1/wca/apikey/test/";
export const API_WCA_MODEL_ID_TEST_PATH = "/api/v1/wca/modelid/test/";

export const readCookie = (name: string): string | null => {
  const nameEQ = name + "=";
  const ca = document.cookie.split(";");
  for (let c of ca) {
    const cookie = c.trim();
    if (cookie.startsWith(nameEQ)) {
      return cookie.substring(nameEQ.length, cookie.length);
    }
  }
  return null;
};

// In cross-origin proxy deployments (e.g. OAuth via AAP gateway), the browser
// may not send the CSRF cookie due to domain mismatch. The Django template
// embeds the token in a hidden DOM element as a reliable fallback.
export const readCsrfCookie = (): string | null =>
  readCookie("__Host-csrftoken") ??
  document.getElementById("csrf_token")?.textContent?.trim() ??
  readCookie("csrftoken") ??
  null;

export const getWcaKey = () => {
  return axios.get(API_WCA_KEY_PATH);
};

export const saveWcaKey = (wcaKey: WcaKeyRequest) => {
  const csrfToken = readCsrfCookie();
  return axios.post(API_WCA_KEY_PATH, wcaKey, {
    headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
  });
};

export const deleteWcaKey = () => {
  const csrfToken = readCsrfCookie();
  return axios.delete(API_WCA_KEY_PATH, {
    headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
  });
};

export const testWcaKey = () => {
  return axios.get(API_WCA_KEY_TEST_PATH);
};

export const getWcaModelId = () => {
  return axios.get(API_WCA_MODEL_ID_PATH);
};

export const saveWcaModelId = (wcaModelId: WcaModelIdRequest) => {
  const csrfToken = readCsrfCookie();
  return axios.post(API_WCA_MODEL_ID_PATH, wcaModelId, {
    headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
  });
};

export const testWcaModelId = () => {
  return axios.get(API_WCA_MODEL_ID_TEST_PATH);
};

export const getTelemetrySettings = () => {
  return axios.get(API_TELEMETRY_PATH);
};

export const saveTelemetrySettings = (telemetry: TelemetryRequest) => {
  const csrfToken = readCsrfCookie();
  return axios.post(API_TELEMETRY_PATH, telemetry, {
    headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
  });
};
