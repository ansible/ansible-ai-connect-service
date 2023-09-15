import {WcaKeyRequest, WcaModelIdRequest} from "./types";
import axios from "axios";

export const API_WCA_KEY_PATH = "/api/v0/wca/apikey/";
export const API_WCA_MODEL_ID_PATH = "/api/v0/wca/modelid/";
export const API_WCA_KEY_TEST_PATH = "/api/v0/wca/apikey/test";
export const API_WCA_MODEL_ID_TEST_PATH = "/api/v0/wca/modelid/test";

const readCookie = (name: string) => {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') {
            c = c.substring(1, c.length);
        }
        if (c.indexOf(nameEQ) === 0) {
            return c.substring(nameEQ.length, c.length);
        }
    }
    return null;
}

export const getWcaKey = () => {
    return axios.get(API_WCA_KEY_PATH);
};

export const saveWcaKey = (wcaKey: WcaKeyRequest) => {
    const csrfToken = readCookie('csrftoken');
    return axios.post(API_WCA_KEY_PATH, wcaKey, {headers: {"X-CSRFToken": csrfToken}});
};

export const testWcaKey = () => {
    return axios.get(API_WCA_KEY_TEST_PATH);
};

export const getWcaModelId = () => {
    return axios.get(API_WCA_MODEL_ID_PATH);
};

export const saveWcaModelId = (wcaModelId: WcaModelIdRequest) => {
    const csrfToken = readCookie('csrftoken');
    return axios.post(API_WCA_MODEL_ID_PATH, wcaModelId, {headers: {"X-CSRFToken": csrfToken}});
};

export const testWcaModelId = () => {
    return axios.get(API_WCA_MODEL_ID_TEST_PATH);
};
