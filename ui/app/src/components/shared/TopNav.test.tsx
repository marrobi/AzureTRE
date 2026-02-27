import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { TopNav } from "./TopNav";

// Mock child components
vi.mock("./UserMenu", () => {
  const UserMenu = () => <div data-testid="user-menu">User Menu</div>;
  UserMenu.displayName = "UserMenu";
  return { UserMenu };
});

vi.mock("./notifications/NotificationPanel", () => {
  const NotificationPanel = () => (
    <div data-testid="notification-panel">Notifications</div>
  );
  NotificationPanel.displayName = "NotificationPanel";
  return { NotificationPanel };
});

// Mock config.json
vi.mock("../../config.json", () => ({
  default: {
    uiSiteName: "Test TRE Environment",
  },
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe("TopNav Component", () => {
  it("renders the GDS header with banner role", () => {
    renderWithRouter(<TopNav />);

    const header = screen.getByRole("banner");
    expect(header).toBeInTheDocument();
    expect(header.tagName).toBe("HEADER");
    expect(header).toHaveClass("govuk-header");
  });

  it("renders the GOV.UK logo link", () => {
    renderWithRouter(<TopNav />);

    const homepageLink = screen.getByRole("link");
    expect(homepageLink).toHaveAttribute("href", "/");
    expect(homepageLink).toHaveClass("govuk-header__homepage-link");
  });

  it("renders the service/product name", () => {
    renderWithRouter(<TopNav />);

    expect(screen.getByText("Test TRE Environment")).toBeInTheDocument();
  });

  it("renders the GOV.UK logotype SVG", () => {
    renderWithRouter(<TopNav />);

    // The SVG has aria-label="GOV.UK"
    const svg = screen.getByRole("img", { name: "GOV.UK" });
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("govuk-header__logotype");
  });

  it("renders child components (notifications and user menu)", () => {
    renderWithRouter(<TopNav />);

    expect(screen.getByTestId("notification-panel")).toBeInTheDocument();
    expect(screen.getByTestId("user-menu")).toBeInTheDocument();
  });

  it("uses full-width container class", () => {
    renderWithRouter(<TopNav />);

    const container = document
      .querySelector(".govuk-header__container--full-width");
    expect(container).toBeInTheDocument();
  });
});

