import {render, screen, waitForElementToBeRemoved} from "@testing-library/react";
import "@testing-library/jest-dom";
import {ModelSettings} from "../ModelSettings";
import axios from "axios";
import userEvent from "@testing-library/user-event";

jest.mock('axios',
    () => ({
        get: jest.fn(),
    }));

describe('ModelSettings',
    () => {

        beforeEach(() => jest.resetAllMocks());

        it('Loading API Key',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
                render(<ModelSettings/>);
                expect(screen.getByTestId("model-settings-overview__key-loading")).toBeInTheDocument();
                await waitForElementToBeRemoved(() => screen.queryByTestId("model-settings-overview__key-loading"));
            });

        it('Loading Model Id',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
                render(<ModelSettings/>);
                expect(screen.getByTestId("model-settings-overview__model-id-loading")).toBeInTheDocument();
                await waitForElementToBeRemoved(() => screen.queryByTestId("model-settings-overview__model-id-loading"));
            });

        it('API Key Loaded',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
                render(<ModelSettings/>);
                expect(await screen.findByTestId("model-settings-overview__key")).toBeInTheDocument();
            });

        it('API Key Not Found',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {}});
                render(<ModelSettings/>);
                expect(await screen.findByTestId("model-settings-overview__key-not-found")).toBeInTheDocument();
            });

        it('Model Id Loaded',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
                render(<ModelSettings/>);
                expect(await screen.findByTestId("model-settings-overview__model-id")).toBeInTheDocument();
            });

        it('Model Id Key Not Found',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {}});
                render(<ModelSettings/>);
                expect(await screen.findByTestId("model-settings-overview__model-id-not-found")).toBeInTheDocument();
            });

        it('Render::ModelSettingsKey',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
                render(<ModelSettings/>);
                expect(await screen.findByTestId("model-settings-overview__key")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__model-id")).toBeInTheDocument();

                // Emulate User clicking on "Update Key" button
                const editButton = await screen.findByTestId("model-settings-overview__update-key-button");
                await userEvent.click(editButton);

                // The ModelSettingsKey component should be rendered
                expect(await screen.findByTestId("model-settings-editor__editor")).toBeInTheDocument();
            });

        it('Render::ModelSettingsModelId',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
                render(<ModelSettings/>);
                expect(await screen.findByTestId("model-settings-overview__key")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__model-id")).toBeInTheDocument();

                // Emulate User clicking on "Update Model Id" button
                const editButton = await screen.findByTestId("model-settings-overview__update-model-id-button");
                await userEvent.click(editButton);

                // The ModelSettingsModelId component should be rendered
                expect(await screen.findByTestId("model-settings-editor__editor")).toBeInTheDocument();
            });

    });
