import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { DataModeProvider } from "./data/dataMode";
import { SessionControlProvider } from "./data/sessionControl";
import { AppRouter } from "./router/AppRouter";
import { initializeTheme } from "./theme/themes";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

initializeTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <DataModeProvider>
        <SessionControlProvider>
          <BrowserRouter>
            <AppRouter />
          </BrowserRouter>
        </SessionControlProvider>
      </DataModeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
