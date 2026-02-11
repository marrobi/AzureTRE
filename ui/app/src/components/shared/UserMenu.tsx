import React from "react";
import {
  IContextualMenuProps,
  Persona,
  PersonaSize,
  PrimaryButton,
} from "@fluentui/react";
import { useAccount, useMsal } from "@azure/msal-react";
import { useTheme } from "../../hooks/useTheme";

export const UserMenu: React.FunctionComponent = () => {
  const { instance, accounts } = useMsal();
  const account = useAccount(accounts[0] || {});
  const { isDarkMode, toggleTheme } = useTheme();

  const menuProps: IContextualMenuProps = {
    shouldFocusOnMount: true,
    directionalHint: 6, // bottom right edge
    items: [
      {
        key: "darkMode",
        text: isDarkMode ? "Light Mode" : "Dark Mode",
        iconProps: { iconName: isDarkMode ? "Sunny" : "ClearNight" },
        onClick: () => {
          toggleTheme();
        },
      },
      {
        key: "logout",
        text: "Logout",
        iconProps: { iconName: "SignOut" },
        onClick: () => {
          instance.logout(); // will use MSAL to logout and redirect to the /logout page
        },
      },
    ],
  };

  return (
    <div className="tre-user-menu">
      <PrimaryButton
        menuProps={menuProps}
        style={{ background: "none", border: "none" }}
      >
        <Persona
          text={account?.name}
          size={PersonaSize.size32}
          imageAlt={account?.name}
        />
      </PrimaryButton>
    </div>
  );
};
