import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { Footer } from "./Footer";

// Mock the API hook
const mockApiCall = vi.fn();
vi.mock("../../hooks/useAuthApiCall", () => ({
  useAuthApiCall: () => mockApiCall,
  HttpMethod: { Get: "GET" },
}));

// Mock the config
vi.mock("../../config.json", () => ({
  default: {
    uiFooterText: "Test Footer Text",
    version: "1.0.0",
  },
}));

// Mock API endpoints
vi.mock("../../models/apiEndpoints", () => ({
  ApiEndpoint: {
    Metadata: "/api/metadata",
    Health: "/api/health",
  },
}));

describe("Footer Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiCall.mockResolvedValue({});
  });

  it("renders a GDS footer landmark", async () => {
    await act(async () => {
      render(<Footer />);
    });

    const footer = screen.getByRole("contentinfo");
    expect(footer).toBeInTheDocument();
    expect(footer.tagName).toBe("FOOTER");
    expect(footer).toHaveClass("govuk-footer");
  });

  it("renders the Open Government Licence link", async () => {
    await act(async () => {
      render(<Footer />);
    });

    const oglLink = screen.getByRole("link", {
      name: /open government licence/i,
    });
    expect(oglLink).toBeInTheDocument();
    expect(oglLink).toHaveAttribute(
      "href",
      "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    );
  });

  it("renders the Crown copyright link", async () => {
    await act(async () => {
      render(<Footer />);
    });

    const copyrightLink = screen.getByRole("link", {
      name: /crown copyright/i,
    });
    expect(copyrightLink).toBeInTheDocument();
  });

  it("renders footer text from config", async () => {
    await act(async () => {
      render(<Footer />);
    });

    expect(screen.getByText("Test Footer Text")).toBeInTheDocument();
  });

  it("renders system info button", async () => {
    await act(async () => {
      render(<Footer />);
    });

    const infoButton = screen.getByRole("button", {
      name: /system information/i,
    });
    expect(infoButton).toBeInTheDocument();
    expect(infoButton).toHaveAttribute("aria-expanded", "false");
  });

  it("shows info callout when system info button is clicked", async () => {
    mockApiCall
      .mockResolvedValueOnce({ api_version: "2.0.0" })
      .mockResolvedValueOnce({
        services: [
          { service: "API", status: "OK" },
          { service: "Database", status: "OK" },
        ],
      });

    await act(async () => {
      render(<Footer />);
    });

    const infoButton = screen.getByRole("button", { name: /system information/i });

    await act(async () => {
      fireEvent.click(infoButton);
    });

    await waitFor(() => {
      expect(screen.getByText("Azure TRE")).toBeInTheDocument();
    });

    expect(screen.getByText("UI Version:")).toBeInTheDocument();
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
  });

  it("shows API version in callout", async () => {
    mockApiCall
      .mockResolvedValueOnce({ api_version: "2.0.0" })
      .mockResolvedValueOnce({ services: [] });

    await act(async () => {
      render(<Footer />);
    });

    const infoButton = screen.getByRole("button", { name: /system information/i });

    await act(async () => {
      fireEvent.click(infoButton);
    });

    await waitFor(() => {
      expect(screen.getByText("API Version:")).toBeInTheDocument();
    });

    expect(screen.getByText("2.0.0")).toBeInTheDocument();
  });

  it("shows service health status", async () => {
    mockApiCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({
        services: [
          { service: "API", status: "OK" },
          { service: "Database", status: "ERROR" },
        ],
      });

    await act(async () => {
      render(<Footer />);
    });

    const infoButton = screen.getByRole("button", { name: /system information/i });

    await act(async () => {
      fireEvent.click(infoButton);
    });

    await waitFor(() => {
      expect(screen.getByText("API:")).toBeInTheDocument();
    });

    expect(screen.getByText("OK")).toBeInTheDocument();
    expect(screen.getByText("Database:")).toBeInTheDocument();
    expect(screen.getByText("ERROR")).toBeInTheDocument();
  });

  it("calls API endpoints on mount", async () => {
    await act(async () => {
      render(<Footer />);
    });

    expect(mockApiCall).toHaveBeenCalledWith("/api/metadata", "GET");
    expect(mockApiCall).toHaveBeenCalledWith("/api/health", "GET");
  });

  it("handles missing health services gracefully", async () => {
    mockApiCall
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({});

    await act(async () => {
      render(<Footer />);
    });

    const infoButton = screen.getByRole("button", { name: /system information/i });

    await act(async () => {
      fireEvent.click(infoButton);
    });

    await waitFor(() => {
      expect(screen.getByText("Azure TRE")).toBeInTheDocument();
    });

    expect(screen.getByText("UI Version:")).toBeInTheDocument();
  });
});

