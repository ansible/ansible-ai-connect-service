import {render, screen} from "@testing-library/react";
import "@testing-library/jest-dom";
import {TelemetrySettings} from "../TelemetrySettings";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import {API_TELEMETRY_PATH} from "../api/api";

jest.mock('axios',
    () => ({
        get: jest.fn(),
        post: jest.fn(),
    }));

describe('TelemetrySettings',
    () => {

        beforeEach(() => jest.resetAllMocks());

        it('Loading',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"optOut": "false"});
                render(
                    <TelemetrySettings/>
                );
                expect((axios.get as jest.Mock)).toBeCalledWith(API_TELEMETRY_PATH)
                expect(await screen.findByTestId("telemetry-settings__telemetry-loading")).toBeInTheDocument();
            });

        it('Loaded::Found',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"optOut": true}});
                render(
                    <TelemetrySettings/>
                );
                expect((axios.get as jest.Mock)).toBeCalledWith(API_TELEMETRY_PATH)
                expect(await screen.findByTestId("telemetry-settings__opt_out_checkbox")).toBeInTheDocument();
            });

        it('Click::Save::Success',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"optOut": false}});
                (axios.post as jest.Mock).mockResolvedValue({});

                render(
                    <TelemetrySettings/>
                );

                // Emulate click on "Opt In/Out" checkbox
                let optOutCheckbox: HTMLInputElement = await screen.findByTestId("telemetry-settings__opt_out_checkbox");
                expect(optOutCheckbox.checked).toEqual(false);
                await userEvent.click(optOutCheckbox);

                expect((axios.post as jest.Mock)).toBeCalledWith(API_TELEMETRY_PATH, {"optOut": true}, {"headers": {"X-CSRFToken": null}})

                optOutCheckbox = await screen.findByTestId("telemetry-settings__opt_out_checkbox");
                expect(optOutCheckbox.checked).toEqual(true);
            });

        it('Click::Save::Failure::Error',
            async () => {
                (axios.get as jest.Mock).mockResolvedValue({"data": {"optOut": false}});
                (axios.post as jest.Mock).mockRejectedValue({"response": {"status": 500}});

                render(
                    <TelemetrySettings/>
                );

                // Emulate click on "Opt In/Out" checkbox
                const optOutCheckbox: HTMLInputElement = await screen.findByTestId("telemetry-settings__opt_out_checkbox");
                expect(optOutCheckbox.checked).toEqual(false);
                await userEvent.click(optOutCheckbox);

                expect((axios.post as jest.Mock)).toBeCalledWith(API_TELEMETRY_PATH, {"optOut": true}, {"headers": {"X-CSRFToken": null}})

                // Modals are added to the 'document.body' so perform a basic check for a known field.
                expect(document.body).toHaveTextContent("TelemetryError")
            });

    });
