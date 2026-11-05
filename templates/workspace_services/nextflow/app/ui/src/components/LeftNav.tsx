import React from "react";
import { INavLinkGroup, Nav } from "@fluentui/react";
import { useLocation, useNavigate } from "react-router-dom";

const groups: INavLinkGroup[] = [
  {
    links: [
      { name: "Runs", url: "/", key: "runs", icon: "Play" },
      { name: "Pipelines", url: "/pipelines", key: "pipelines", icon: "Flow" },
      { name: "Data", url: "/data", key: "data", icon: "FabricFolder" },
    ],
  },
];

function selectedKey(path: string): string {
  if (path.startsWith("/pipelines")) return "pipelines";
  if (path.startsWith("/data")) return "data";
  return "runs";
}

export const LeftNav: React.FunctionComponent = () => {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <Nav
      ariaLabel="Nextflow navigation"
      groups={groups}
      selectedKey={selectedKey(location.pathname)}
      onLinkClick={(e, item) => {
        e?.preventDefault();
        if (item?.url) navigate(item.url);
      }}
    />
  );
};
