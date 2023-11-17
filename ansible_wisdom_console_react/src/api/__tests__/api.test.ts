import "@testing-library/jest-dom";
import {readCookie} from "../api";

describe("API",
    () => {

        it("Cookie extraction::Empty string",
            () => {
                document.cookie = "";
                const cookie = readCookie("csrftoken");
                expect(cookie).toBeNull();
            });

        it("Cookie extraction::Single::With whitespace",
            () => {
                document.cookie = "csrftoken = 12345   ";
                const cookie = readCookie("csrftoken");
                expect(cookie).toEqual("12345");
            });

        it("Cookie extraction::Single::Without whitespace",
            () => {
                document.cookie = "csrftoken=12345";
                const cookie = readCookie("csrftoken");
                expect(cookie).toEqual("12345");
            });

        it("Cookie extraction::Multiple::With whitespace",
            () => {
                document.cookie = "smurf = abcdef; csrftoken = 12345   ";
                const cookie = readCookie("csrftoken");
                expect(cookie).toEqual("12345");
            });

        it("Cookie extraction::Multiple::Without whitespace",
            () => {
                document.cookie = "smurf=abcdef;csrftoken=12345";
                const cookie = readCookie("csrftoken");
                expect(cookie).toEqual("12345");
            });

    });
