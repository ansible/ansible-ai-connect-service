export const ORG_ID = "org-id";
export const MODEL_ID_FIELD = "model_id";

export const ERROR_DESCRIPTION = "Something went horribly wrong. I suggest you speak to the development team to try and figure out a solution.";

export const DELAY_MS = 1000;

export const delay = (ms: number) => {
    return new Promise(resolve => setTimeout(resolve, ms));
}
