import { createContext } from "react";

export interface ThemeContextValue {
  isDarkMode: boolean;
  toggleTheme: () => void;
}

// Default values are not used in practice since useTheme throws an error if context is undefined.
// These values are only for the createContext call.
export const ThemeContext = createContext<ThemeContextValue>({
  isDarkMode: false,
  toggleTheme: () => {},
});
