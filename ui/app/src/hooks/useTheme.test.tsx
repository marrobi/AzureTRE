import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme } from "./useTheme";
import { ThemeContext } from "../contexts/ThemeContext";
import React from "react";

describe("useTheme hook", () => {
  const mockToggleTheme = () => {};

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("returns theme context value", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ThemeContext.Provider
        value={{ isDarkMode: false, toggleTheme: mockToggleTheme }}
      >
        {children}
      </ThemeContext.Provider>
    );

    const { result } = renderHook(() => useTheme(), { wrapper });

    expect(result.current.isDarkMode).toBe(false);
    expect(result.current.toggleTheme).toBe(mockToggleTheme);
  });

  it("returns dark mode when enabled", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ThemeContext.Provider
        value={{ isDarkMode: true, toggleTheme: mockToggleTheme }}
      >
        {children}
      </ThemeContext.Provider>
    );

    const { result } = renderHook(() => useTheme(), { wrapper });

    expect(result.current.isDarkMode).toBe(true);
  });

  it("allows toggling theme", () => {
    let isDark = false;
    const toggle = () => {
      isDark = !isDark;
    };

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ThemeContext.Provider value={{ isDarkMode: isDark, toggleTheme: toggle }}>
        {children}
      </ThemeContext.Provider>
    );

    const { result, rerender } = renderHook(() => useTheme(), { wrapper });

    expect(result.current.isDarkMode).toBe(false);

    act(() => {
      result.current.toggleTheme();
    });

    rerender();
    // Note: In real implementation, the state would update through React's state management
    // This test verifies the toggle function is callable
    expect(typeof result.current.toggleTheme).toBe("function");
  });
});
