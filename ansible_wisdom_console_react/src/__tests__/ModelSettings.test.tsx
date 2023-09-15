import {act, render, screen, waitForElementToBeRemoved} from "@testing-library/react";
import "@testing-library/jest-dom";
import {ModelSettings} from "../ModelSettings";
import axios from "axios";

jest.mock('axios',
    () => ({
        get: jest.fn(),
    }));

describe('ModelSettings', () => {

    beforeEach(() => jest.resetAllMocks());

    it('Debug alert is present',
        async () => {
            (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
            await act(async () => {
                render(<ModelSettings debug={true}/>);
            });
            expect(screen.queryByTestId("debug-alert")).toBeInTheDocument();
        });

    it('Debug alert is not present',
        async () => {
            (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
            await act(async () => {
                render(<ModelSettings debug={false}/>);
            });
            expect(screen.queryByTestId("debug-alert")).not.toBeInTheDocument();
        });

    it('Loading API Key',
        async () => {
            (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
            render(<ModelSettings debug={false}/>);
            expect(screen.queryByTestId("model-settings-overview__key-loading")).toBeInTheDocument();
            await waitForElementToBeRemoved(() => screen.queryByTestId("model-settings-overview__key-loading"));
        });

    it('Loading Model Id',
        async () => {
            (axios.get as jest.Mock).mockResolvedValue({"data": {"last_update": new Date()}});
            render(<ModelSettings debug={false}/>);
            expect(screen.queryByTestId("model-settings-overview__model-id-loading")).toBeInTheDocument();
            await waitForElementToBeRemoved(() => screen.queryByTestId("model-settings-overview__model-id-loading"));
        });

    it('API Key Loaded',
        async () => {
            (axios.get as jest.Mock).mockResolvedValue({"data": {}});
            await act(async () => {
                render(<ModelSettings debug={false}/>);
            });
            expect(screen.queryByTestId("model-settings-overview__key")).toBeInTheDocument();
        });

    it('API Key Not Found',
        async () => {
            (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 404}});
            await act(async () => {
                render(
                    <ModelSettings debug={false}/>
                );
            });
            expect(screen.queryByTestId("model-settings-overview__key-not-found")).toBeInTheDocument();
        });

    it('Model Id Loaded',
        async () => {
            (axios.get as jest.Mock).mockResolvedValue({"data": {}});
            await act(async () => {
                render(<ModelSettings debug={false}/>);
            });
            expect(screen.queryByTestId("model-settings-overview__model-id")).toBeInTheDocument();
        });

    it('Model Id Key Not Found',
        async () => {
            (axios.get as jest.Mock).mockRejectedValue({"response": {"status": 404}});
            await act(async () => {
                render(
                    <ModelSettings debug={false}/>
                );
            });
            expect(screen.queryByTestId("model-settings-overview__key-not-found")).toBeInTheDocument();
        });

});
