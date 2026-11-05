import React, { useEffect, useState } from "react";
import { MessageBar, MessageBarType, Stack } from "@fluentui/react";
import { Route, Routes } from "react-router-dom";
import { api } from "./api";
import { LeftNav } from "./components/LeftNav";
import { TopNav } from "./components/TopNav";
import { DataPage } from "./pages/DataPage";
import { LaunchPage } from "./pages/LaunchPage";
import { PipelinesPage } from "./pages/PipelinesPage";
import { RunPage } from "./pages/RunPage";
import { RunsPage } from "./pages/RunsPage";
import { Me } from "./types";

export const App: React.FunctionComponent = () => {
  const [me, setMe] = useState<Me>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    api
      .get<Me>("/api/me")
      .then((m) => {
        setMe(m);
        document.title = `${m.service_name} | Azure TRE`;
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <Stack className="nf-root">
      <TopNav me={me} />
      <Stack horizontal className="nf-body">
        <Stack.Item className="nf-left-nav">
          <LeftNav />
        </Stack.Item>
        <Stack.Item grow className="nf-content">
          {error && (
            <MessageBar messageBarType={MessageBarType.error} isMultiline>
              {error}
            </MessageBar>
          )}
          <Routes>
            <Route path="/" element={<RunsPage />} />
            <Route path="/runs/:runId" element={<RunPage />} />
            <Route path="/pipelines" element={<PipelinesPage />} />
            <Route path="/pipelines/:pipelineId/launch" element={<LaunchPage />} />
            <Route path="/data" element={<DataPage me={me} />} />
            <Route path="*" element={<h1>Page not found</h1>} />
          </Routes>
        </Stack.Item>
      </Stack>
    </Stack>
  );
};
