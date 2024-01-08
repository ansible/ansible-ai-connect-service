import {render, screen} from "@testing-library/react";
import "@testing-library/jest-dom";
import {ModelSettingsOverview} from "../ModelSettingsOverview";
import {WcaKey, WcaModelId} from "../api/types";
import userEvent from "@testing-library/user-event";
import axios from "axios";

jest.mock('axios',
    () => ({
        get: jest.fn(),
    }));

describe('ModelSettingsOverview',
    () => {

        const setModeToKey = jest.fn();
        const setModeToModelId = jest.fn();

        beforeEach(() => jest.resetAllMocks());

        it('Loading',
            async () => {
                const wcaKey: WcaKey = {status: "LOADING"};
                const wcaModelId: WcaModelId = {status: "LOADING"};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );
                expect(await screen.findByTestId("model-settings-overview__key-loading")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__model-id-loading")).toBeInTheDocument();
            });

        it('Loaded::Not found',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS_NOT_FOUND"};
                const wcaModelId: WcaModelId = {status: "SUCCESS_NOT_FOUND"};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );
                expect(await screen.findByTestId("model-settings-overview__key-not-found")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__add-key-button")).toBeInTheDocument();

                expect(await screen.findByTestId("model-settings-overview__model-id-not-found")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__add-model-id-button")).toBeInTheDocument();
            });

        it('Loaded::Found',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );
                expect(await screen.findByTestId("model-settings-overview__key")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__update-key-button")).toBeInTheDocument();

                expect(await screen.findByTestId("model-settings-overview__model-id")).toBeInTheDocument();
                expect(await screen.findByTestId("model-settings-overview__update-model-id-button")).toBeInTheDocument();
            });

        it('Add::Key',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS_NOT_FOUND"};
                const wcaModelId: WcaModelId = {status: "SUCCESS_NOT_FOUND"};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Add Key" button
                const addKeyButton = await screen.findByTestId("model-settings-overview__add-key-button");
                await userEvent.click(addKeyButton);

                expect(setModeToKey).toBeCalled();
            });

        it('Update::Key',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Update Key" button
                const updateKeyButton = await screen.findByTestId("model-settings-overview__update-key-button");
                await userEvent.click(updateKeyButton);

                expect(setModeToKey).toBeCalled();
            });

        it('Add::ModelId::APIKeyFound',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS_NOT_FOUND"};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Add Model ID" button
                const addModelIdButton = await screen.findByTestId("model-settings-overview__add-model-id-button");
                await userEvent.click(addModelIdButton);

                expect(setModeToModelId).toBeCalled();
            });

        it('Add::ModelId::APIKeyNotFound',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS_NOT_FOUND"};
                const wcaModelId: WcaModelId = {status: "SUCCESS_NOT_FOUND"};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                const alert = await screen.findByTestId("model-settings-overview__model-id-set-api-key-first");
                expect(alert).toHaveTextContent("NoModelIdNoAPIKey");

                const addModelIdButton = await screen.findByTestId("model-settings-overview__add-model-id-button");
                expect(addModelIdButton).toBeDisabled();
            });

        it('Update::ModelId',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Update Model ID" button
                const updateModelIdButton = await screen.findByTestId("model-settings-overview__update-model-id-button");
                await userEvent.click(updateModelIdButton);

                expect(setModeToModelId).toBeCalled();
            });

        it('Validate::Key::Success',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockResolvedValue({});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [Key]" button
                const testKeyButton = await screen.findByTestId("model-settings-overview__key-test-button");
                await userEvent.click(testKeyButton);

                const alert = await screen.findByTestId("alert");
                expect(alert).toHaveTextContent("KeyValidationSuccess");
            });

        it('Validate::Key::Failure',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 400}});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [Key]" button
                const testKeyButton = await screen.findByTestId("model-settings-overview__key-test-button");
                await userEvent.click(testKeyButton);

                const alert = await screen.findByTestId("model-settings-overview__alert-key-invalid");
                expect(alert).toBeInTheDocument();
            });

        it('Validate::Key::Failure::Error',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 500}});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [Key]" button
                const testKeyButton = await screen.findByTestId("model-settings-overview__key-test-button");
                await userEvent.click(testKeyButton);

                // Modals are added to the 'document.body' so perform a basic check for a known field.
                expect(document.body).toHaveTextContent("KeyValidationError")
            });

        it('Validate::ModelId::Success',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockResolvedValue({});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [ModelId]" button
                const testModelIdButton = await screen.findByTestId("model-settings-overview__model-id-test-button");
                await userEvent.click(testModelIdButton);

                const alert = await screen.findByTestId("alert");
                expect(alert).toHaveTextContent("ModelIdValidationSuccess");
            });

        it('Validate::ModelId::Failure',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 400}});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [ModelId]" button
                const testModelIdButton = await screen.findByTestId("model-settings-overview__model-id-test-button");
                await userEvent.click(testModelIdButton);

                const alert = await screen.findByTestId("model-settings-overview__alert-model-id-invalid");
                expect(alert).toBeInTheDocument();
            });

        it('Validate::ModelId::TrialExpired',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 403}});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [ModelId]" button
                const testKeyButton = await screen.findByTestId("model-settings-overview__model-id-test-button");
                await userEvent.click(testKeyButton);

                // Modals are added to the 'document.body' so perform a basic check for a known field.
                expect(document.body).toHaveTextContent("ModelIdValidationTrialExpired")
            });

        it('Validate::ModelId::Failure::Error',
            async () => {
                const wcaKey: WcaKey = {status: "SUCCESS", data: {lastUpdate: new Date()}};
                const wcaModelId: WcaModelId = {status: "SUCCESS", data: {lastUpdate: new Date(), model_id: "model_id"}};
                (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 500}});

                render(
                    <ModelSettingsOverview
                        wcaKey={wcaKey}
                        wcaModelId={wcaModelId}
                        setModeToKey={setModeToKey}
                        setModeToModelId={setModeToModelId}
                    />
                );

                // Emulate click on "Test [ModelId]" button
                const testKeyButton = await screen.findByTestId("model-settings-overview__model-id-test-button");
                await userEvent.click(testKeyButton);

                // Modals are added to the 'document.body' so perform a basic check for a known field.
                expect(document.body).toHaveTextContent("ModelIdValidationError")
            });

    });
