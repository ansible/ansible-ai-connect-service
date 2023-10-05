import {render, screen} from "@testing-library/react";
import "@testing-library/jest-dom";
import {ModelSettingsModelId} from "../ModelSettingsModelId";
import {WcaModelId} from "../api/types";
import userEvent from "@testing-library/user-event";
import axios from "axios";

jest.mock('axios',
    () => ({
        get: jest.fn(),
        post: jest.fn(),
    }));

describe('ModelSettingsModelId',
    () => {

        const mockReload = jest.fn();
        const mockCancel = jest.fn();

        beforeEach(() => jest.resetAllMocks());

        it('Loaded',
            async () => {
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};

                render(
                    <ModelSettingsModelId
                        wcaModelId={wcaModelId}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );
                expect(await screen.findByTestId("model-settings-editor__bread-crumbs")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-editor__editor")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-editor__save-button")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-editor__cancel-button")).toBeInTheDocument();
            });

        it('Click::Save::Success',
            async () => {
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.post as jest.Mock).mockResolvedValue({});

                render(
                    <ModelSettingsModelId
                        wcaModelId={wcaModelId}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate a key being entered
                const keyTextbox = await screen.findByTestId("model-settings-editor__input");
                await userEvent.type(keyTextbox, "a-new-key");

                // Emulate click on "Save" button
                const saveButton = await screen.findByTestId("model-settings-editor__save-button");
                await userEvent.click(saveButton);

                expect(mockReload).toBeCalled();
            });

        it('Click::Save::Failure',
            async () => {
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.post as jest.Mock).mockRejectedValue({"response": {"status": 400}});

                render(
                    <ModelSettingsModelId
                        wcaModelId={wcaModelId}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate a key being entered
                const keyTextbox = await screen.findByTestId("model-settings-editor__input");
                await userEvent.type(keyTextbox, "a-new-key");

                // Emulate click on "Save" button
                const saveButton = await screen.findByTestId("model-settings-editor__save-button");
                await userEvent.click(saveButton);

                const alert = await screen.findByTestId("model-settings-editor__alert-invalid");
                expect(alert).toBeInTheDocument();
            });

        it('Click::Save::Failure::Error',
            async () => {
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.post as jest.Mock).mockRejectedValue({"response": {"status": 500}});

                render(
                    <ModelSettingsModelId
                        wcaModelId={wcaModelId}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate a key being entered
                const keyTextbox = await screen.findByTestId("model-settings-editor__input");
                await userEvent.type(keyTextbox, "a-new-key");

                // Emulate click on "Save" button
                const saveButton = await screen.findByTestId("model-settings-editor__save-button");
                await userEvent.click(saveButton);

                // Modals are added to the 'document.body' so perform a basic check for a known field.
                expect(document.body).toHaveTextContent("ModelIdError")
            });

        it('Click::Cancel',
            async () => {
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};

                render(
                    <ModelSettingsModelId
                        wcaModelId={wcaModelId}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate click on "Cancel" button
                const cancelButton = await screen.findByTestId("model-settings-editor__cancel-button");
                await userEvent.click(cancelButton);

                expect(mockCancel).toBeCalled();
            });

    });
