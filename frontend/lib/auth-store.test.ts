import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "./auth-store";

describe("auth store", () => {
  beforeEach(() => {
    useAuthStore.getState().clearSession();
    localStorage.clear();
  });

  it("starts empty", () => {
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("setSession populates token and user", () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    expect(useAuthStore.getState().token).toBe("u_7");
    expect(useAuthStore.getState().user).toEqual({ id: 7, username: "alice" });
  });

  it("clearSession resets state", () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    useAuthStore.getState().clearSession();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("persists token to localStorage under knowledgedeck-auth", () => {
    useAuthStore.getState().setSession("u_42", { id: 42, username: "carol" });
    const raw = localStorage.getItem("knowledgedeck-auth");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!).state.token).toBe("u_42");
  });
});
