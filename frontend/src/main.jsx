import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import { STATIC } from "./api.js";
import App from "./App.jsx";
import "./styles.css";

// GitHub Pages has no server-side routing -> hash URLs in the static demo
const Router = STATIC ? HashRouter : BrowserRouter;

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Router>
      <App />
    </Router>
  </React.StrictMode>
);
