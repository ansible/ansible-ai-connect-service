export default jest.mock("react-i18next",
    () => ({
        useTranslation: () => {
            return {
                t: (str: String) => str,
            };
        },
    }));
