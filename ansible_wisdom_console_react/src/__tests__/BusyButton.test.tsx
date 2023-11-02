import {render, screen} from "@testing-library/react";
import "@testing-library/jest-dom";
import {BusyButton} from "../BusyButton";

describe('BusyButton',
    () => {

        it('Rendering::When busy',
            async () => {
                render(<BusyButton isBusy={true} data-testid="busy-button"/>);
                const element = screen.getByTestId("busy-button");
                expect(element).toBeInTheDocument();
                expect(element.className).toContain("pf-m-in-progress");
            });

        it('Rendering::When not busy',
            async () => {
                render(<BusyButton isBusy={false} data-testid="busy-button"/>);
                const element = screen.getByTestId("busy-button");
                expect(element).toBeInTheDocument();
                expect(element.className).not.toContain("pf-m-in-progress");
            });

    });
