import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";
import { api } from "../../lib/api";
import { useAuthStore } from "../../lib/auth-store";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: pushMock }),
}));

describe("LoginPage", () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
    useAuthStore.getState().clearSession();
    localStorage.clear();
    pushMock.mockClear();
  });

  afterEach(() => mock.restore());

  it("submits credentials and stores session on success", async () => {
    mock.onPost("/auth/login").reply(200, {
      token: "u_7",
      user: { id: 7, username: "alice" },
    });
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "alice");
    await userEvent.type(screen.getByLabelText(/password/i), "hunter2");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    await waitFor(() => expect(useAuthStore.getState().token).toBe("u_7"));
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("shows the invalid_credentials error on 401", async () => {
    mock.onPost("/auth/login").reply(401, { detail: "invalid_credentials" });
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "alice");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    expect(await screen.findByTestId("login-error")).toHaveAttribute(
      "data-error-key",
      "auth.error.invalid_credentials",
    );
    expect(useAuthStore.getState().token).toBeNull();
  });
});
