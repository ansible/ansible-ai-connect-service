import {render, screen} from "@testing-library/react";
import "@testing-library/jest-dom";
import {ModelSettingsKey} from "../ModelSettingsKey";
import {WcaKey} from "../api/types";
import userEvent from "@testing-library/user-event";
import axios from "axios";

jest.mock('axios',
    () => ({
        get: jest.fn(),
        post: jest.fn(),
    }));

describe('ModelSettingsKey',
    () => {

        const mockReload = jest.fn();
        const mockCancel = jest.fn();

        beforeEach(() => jest.resetAllMocks());

        it('Loaded',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};

                render(
                    <ModelSettingsKey
                        wcaKey={wcaKey}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );
                expect(await screen.findByTestId("model-settings-key__bread-crumbs")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-key__editor")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-key__save-button")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-key__cancel-button")).toBeInTheDocument();
            });

        it('Click::Save::Success',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                (axios.post as jest.Mock).mockResolvedValue({});

                render(
                    <ModelSettingsKey
                        wcaKey={wcaKey}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate a key being entered
                const keyTextbox = await screen.findByTestId("model-settings-key__key_textbox");
                await userEvent.type(keyTextbox, "a-new-key");

                // Emulate click on "Save" button
                const saveButton = await screen.findByTestId("model-settings-key__save-button");
                await userEvent.click(saveButton);

                expect(mockReload).toBeCalled();
            });

        it('Click::Save::Failure',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                (axios.post as jest.Mock).mockRejectedValue({"response": {"status": 400}});

                render(
                    <ModelSettingsKey
                        wcaKey={wcaKey}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate a key being entered
                const keyTextbox = await screen.findByTestId("model-settings-key__key_textbox");
                await userEvent.type(keyTextbox, "a-new-key");

                // Emulate click on "Save" button
                const saveButton = await screen.findByTestId("model-settings-key__save-button");
                await userEvent.click(saveButton);

                const alert = await screen.findByTestId("model-settings-key__alert-key-invalid");
                expect(alert).toBeInTheDocument();
            });

        it('Click::Save::Failure::Error',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                (axios.post as jest.Mock).mockRejectedValue({"response": {"status": 500}});

                render(
                    <ModelSettingsKey
                        wcaKey={wcaKey}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate a key being entered
                const keyTextbox = await screen.findByTestId("model-settings-key__key_textbox");
                await userEvent.type(keyTextbox, "a-new-key");

                // Emulate click on "Save" button
                const saveButton = await screen.findByTestId("model-settings-key__save-button");
                await userEvent.click(saveButton);

                // Modals are added to the 'document.body' so perform a basic check for a known field.
                expect(document.body).toHaveTextContent("KeyError")
            });

        it('Click::Cancel',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};

                render(
                    <ModelSettingsKey
                        wcaKey={wcaKey}
                        reload={mockReload}
                        cancel={mockCancel}
                    />
                );

                // Emulate click on "Cancel" button
                const cancelButton = await screen.findByTestId("model-settings-key__cancel-button");
                await userEvent.click(cancelButton);

                expect(mockCancel).toBeCalled();
            });

    });
