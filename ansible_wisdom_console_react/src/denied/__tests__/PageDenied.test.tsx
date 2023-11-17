import {render, screen} from "@testing-library/react";
import "@testing-library/jest-dom";
import {PageDenied} from "../PageDenied";

describe('App',
    () => {

        it('Basic rendering',
            async () => {
                render(<PageDenied titleKey={"titleKey"} captionKey={"captionKey"}/>);
                const title = await screen.findByTestId("page-denied__title");
                expect(title).toBeInTheDocument();
                expect(title).toHaveTextContent("titleKey");
                const caption = await screen.findByTestId("page-denied__caption");
                expect(caption).toBeInTheDocument();
                expect(caption).toHaveTextContent("captionKey");
            });

    });
