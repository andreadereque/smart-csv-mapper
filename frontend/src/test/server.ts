import { setupServer } from "msw/node";

// The network boundary for every frontend test. Each test adds the handlers it needs,
// and any request without a handler fails the test (onUnhandledRequest: "error").
export const server = setupServer();
