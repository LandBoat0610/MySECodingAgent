import { createBrowserRouter } from "react-router";
import { IDEPage } from "./pages/IDEPage";
import { DashboardPage } from "./pages/DashboardPage";
import { RootLayout } from "./components/RootLayout";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: RootLayout,
    children: [
      { index: true, Component: IDEPage },
      { path: "dashboard", Component: DashboardPage },
    ],
  },
]);
