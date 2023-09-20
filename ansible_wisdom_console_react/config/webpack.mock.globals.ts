export const ORG_ID = 'org-id';
export const MODEL_ID_FIELD = 'model_id';

export const DELAY_MS = 1000;

export const delay = (ms: number) => {
    return new Promise(resolve => setTimeout(resolve, ms));
}
