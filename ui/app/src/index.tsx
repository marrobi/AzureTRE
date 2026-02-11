import { App } from "./App";
import { mergeStyles, ThemeProvider, createTheme, PartialTheme } from "@fluentui/react";
import reportWebVitals from "./reportWebVitals";
import { BrowserRouter } from "react-router-dom";
import { pca } from "./authConfig";
import { MsalProvider } from "@azure/msal-react";
import { Provider } from "react-redux";
import { store } from "./store/store";
import { createRoot } from "react-dom/client";
import { ThemeContext } from "./contexts/ThemeContext";
import { useState, useEffect } from "react";

// Inject some global styles
mergeStyles({
  ":global(body,html)": {
    margin: 0,
    padding: 0,
    height: "100vh",
  },
});

const root = createRoot(document.getElementById("root") as HTMLElement);

const THEME_STORAGE_KEY = "tre-ui-theme";

// Light theme (default FluentUI theme)
const lightTheme: PartialTheme = createTheme({});

// Dark theme
const darkTheme: PartialTheme = createTheme({
  palette: {
    themePrimary: "#0078d4",
    themeLighterAlt: "#eff6fc",
    themeLighter: "#deecf9",
    themeLight: "#c7e0f4",
    themeTertiary: "#71afe5",
    themeSecondary: "#2b88d8",
    themeDarkAlt: "#106ebe",
    themeDark: "#005a9e",
    themeDarker: "#004578",
    neutralLighterAlt: "#1c1c1c",
    neutralLighter: "#252525",
    neutralLight: "#343434",
    neutralQuaternaryAlt: "#3d3d3d",
    neutralQuaternary: "#454545",
    neutralTertiaryAlt: "#656565",
    neutralTertiary: "#c8c8c8",
    neutralSecondary: "#d0d0d0",
    neutralPrimaryAlt: "#dadada",
    neutralPrimary: "#ffffff",
    neutralDark: "#f4f4f4",
    black: "#f8f8f8",
    white: "#0f0f0f",
  },
});

const AppWrapper = () => {
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    return savedTheme === "dark";
  });

  useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, isDarkMode ? "dark" : "light");
  }, [isDarkMode]);

  const toggleTheme = () => {
    setIsDarkMode((prev) => !prev);
  };

  return (
    <ThemeProvider theme={isDarkMode ? darkTheme : lightTheme}>
      <ThemeContext.Provider value={{ isDarkMode, toggleTheme }}>
        <MsalProvider instance={pca}>
          <BrowserRouter>
            <Provider store={store}>
              <App />
            </Provider>
          </BrowserRouter>
        </MsalProvider>
      </ThemeContext.Provider>
    </ThemeProvider>
  );
};

root.render(<AppWrapper />);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
