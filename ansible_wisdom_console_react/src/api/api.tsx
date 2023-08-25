import {httpClient} from "./httpClient";
import {AxiosRequestConfig} from "axios";
import {WcaKeyRequest, WcaModelIdRequest} from "./types";

const API_WCA_KEY_PATH = "/api/v0/wca/apikey/";
const API_WCA_MODEL_ID_PATH = "/api/v0/wca/modelid/";
const API_WCA_KEY_TEST_PATH = "/api/v0/wca/apikey/test";
const API_WCA_MODEL_ID_TEST_PATH = "/api/v0/wca/modelid/test";

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
    const getExecConfig: AxiosRequestConfig = {
        url: API_WCA_KEY_PATH,
        method: "get"
    };
    return httpClient(getExecConfig);
};

export const saveWcaKey = (wcaKey: WcaKeyRequest) => {
    const csrfToken = readCookie('csrftoken');
    const getExecConfig: AxiosRequestConfig = {
        url: API_WCA_KEY_PATH,
        method: "post",
        data: wcaKey,
        headers: {"X-CSRFToken": csrfToken}
    };
    return httpClient(getExecConfig);
};

export const testWcaKey = () => {
    const getExecConfig: AxiosRequestConfig = {
        url: API_WCA_KEY_TEST_PATH,
        method: "get",
    };
    return httpClient(getExecConfig);
};

export const getWcaModelId = () => {
    const getExecConfig: AxiosRequestConfig = {
        url: API_WCA_MODEL_ID_PATH,
        method: "get",
    };
    return httpClient(getExecConfig);
};

export const saveWcaModelId = (wcaModelId: WcaModelIdRequest) => {
    const csrfToken = readCookie('csrftoken');
    const getExecConfig: AxiosRequestConfig = {
        url: API_WCA_MODEL_ID_PATH,
        method: "post",
        data: wcaModelId,
        headers: {"X-CSRFToken": csrfToken}
    };
    return httpClient(getExecConfig);
};

export const testWcaModelId = () => {
    const getExecConfig: AxiosRequestConfig = {
        url: API_WCA_MODEL_ID_TEST_PATH,
        method: "get",
    };
    return httpClient(getExecConfig);
};
