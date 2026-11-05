import React from "react";
import { getTheme, Icon, Link as FluentLink, mergeStyles, Persona, PersonaSize, Stack } from "@fluentui/react";
import { Link } from "react-router-dom";
import { Me } from "../types";

// Mirrors the Azure TRE portal's top navigation.
export const TopNav: React.FunctionComponent<{ me?: Me }> = ({ me }) => (
  <div className={barClass}>
    <Stack horizontal verticalAlign="center">
      <Stack.Item grow>
        <Link to="/" className="nf-home-link">
          <Icon iconName="TestBeakerSolid" className="nf-home-icon" />
          <h5>Azure TRE</h5>
          <span className="nf-home-divider">|</span>
          <span>{me?.service_name ?? "Nextflow"}</span>
        </Link>
      </Stack.Item>
      {me && (
        <Stack horizontal verticalAlign="center" tokens={{ childrenGap: 16 }} className="nf-user">
          <Persona text={me.name} secondaryText={me.roles.join(", ")} size={PersonaSize.size32} />
          <FluentLink href="/auth/logout" className="nf-signout">
            Sign out
          </FluentLink>
        </Stack>
      )}
    </Stack>
  </div>
);

const theme = getTheme();
const barClass = mergeStyles({
  backgroundColor: theme.palette.themeDark,
  color: theme.palette.white,
  lineHeight: "50px",
  padding: "0 10px",
  boxShadow: "0 1px 2px 0px #033d68",
});
