import "./fabricConfig";
import React from "react";
import ReactDOM from "react-dom/client";
import { initializeIcons } from "@fluentui/react";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./App.css";

initializeIcons();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
