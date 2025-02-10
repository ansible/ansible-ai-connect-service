// https://stackoverflow.com/questions/63329331/mocking-the-navigator-object
export const setClipboard = (s: string) => navigator.clipboard?.writeText(s);
